/**
 * SPDX-License-Identifier: Apache-2.0
 * @defgroup mpix_protocol_c stream/mpix_protocol.c
 * @brief MPIX Camera Streaming Protocol Implementation
 * @{
 */

#include <string.h>
#include <errno.h>

#include <mpix/protocol.h>
#include <mpix/port.h>
#include <mpix/op_jpeg.h>
#include <mpix/auto.h>
#include <mpix/stats.h>

/* Internal helper functions */
static int protocol_handle_sensor_cmd(struct mpix_protocol_context *ctx,
                                      uint8_t cmd_type,
                                      const uint8_t *payload,
                                      size_t payload_size);

static int protocol_handle_isp_cmd(struct mpix_protocol_context *ctx,
                                   uint8_t cmd_type,
                                   const uint8_t *payload,
                                   size_t payload_size);

static int protocol_handle_auto_cmd(struct mpix_protocol_context *ctx,
                                    uint8_t cmd_type,
                                    const uint8_t *payload,
                                    size_t payload_size);

static int protocol_handle_stream_cmd(struct mpix_protocol_context *ctx,
                                      uint8_t cmd_type,
                                      const uint8_t *payload,
                                      size_t payload_size);

static int protocol_handle_system_cmd(struct mpix_protocol_context *ctx,
                                      uint8_t cmd_type,
                                      const uint8_t *payload,
                                      size_t payload_size);

static int mpix_protocol_recover_sync(struct mpix_protocol_context *ctx);

uint16_t mpix_protocol_checksum(const uint8_t *data, size_t size)
{
    uint32_t sum = 0;
    for (size_t i = 0; i < size; i++)
    {
        sum += data[i];
    }
    return (uint16_t)(sum & 0xFFFF);
}

int mpix_protocol_init(struct mpix_protocol_context *ctx,
                       struct mpix_sensor *sensor,
                       struct mpix_transport *transport)
{
    if (!ctx || !sensor || !transport)
    {
        return -EINVAL;
    }

    memset(ctx, 0, sizeof(*ctx));

    ctx->sensor = sensor;
    ctx->transport = transport;
    ctx->streaming = false;
    ctx->stream_mode = MPIX_STREAM_MODE_JPEG;
    ctx->frame_counter = 0;
    ctx->error_counter = 0;
    ctx->sequence_counter = 0;
    ctx->ae_enabled = true;
    ctx->awb_enabled = true;
    ctx->ablc_enabled = true;

    /* Initialize ISP correction controls - all enabled by default */
    ctx->black_level_correction_enabled = true;
    ctx->gamma_correction_enabled = true;
    ctx->white_balance_correction_enabled = true;
    ctx->color_matrix_correction_enabled = true;
    ctx->denoise_filter_enabled = true;

    /* Set default JPEG quality */
    ctx->jpeg_quality = 85;

    /* Allocate rx buffer only */
    ctx->rx_buffer_size = 1024;
    ctx->rx_buffer = mpix_port_alloc(ctx->rx_buffer_size);

    if (!ctx->rx_buffer)
    {
        mpix_protocol_deinit(ctx);
        return -ENOMEM;
    }

    /* Initialize auto algorithms */
    if (mpix_auto_exposure_init(&ctx->auto_ctrls, sensor) != 0)
    {
        mpix_protocol_deinit(ctx);
        return -EIO;
    }

    /* Set default ISP settings */
    ctx->auto_ctrls.ae_target = 36;
    ctx->auto_ctrls.correction.gamma.level = 12 << 5;
    ctx->auto_ctrls.correction.black_level.level = 16;

    /* Default color matrix for 4650K */
    ctx->auto_ctrls.correction.color_matrix.levels[0] = 2235;
    ctx->auto_ctrls.correction.color_matrix.levels[1] = -726;
    ctx->auto_ctrls.correction.color_matrix.levels[2] = -484;
    ctx->auto_ctrls.correction.color_matrix.levels[3] = -719;
    ctx->auto_ctrls.correction.color_matrix.levels[4] = 2830;
    ctx->auto_ctrls.correction.color_matrix.levels[5] = -1088;
    ctx->auto_ctrls.correction.color_matrix.levels[6] = -257;
    ctx->auto_ctrls.correction.color_matrix.levels[7] = -737;
    ctx->auto_ctrls.correction.color_matrix.levels[8] = 2018;

    return 0;
}

void mpix_protocol_deinit(struct mpix_protocol_context *ctx)
{
    if (!ctx)
    {
        return;
    }

    if (ctx->streaming)
    {
        mpix_protocol_stop_streaming(ctx);
    }

    if (ctx->rx_buffer)
    {
        mpix_port_free(ctx->rx_buffer);
    }

    memset(ctx, 0, sizeof(*ctx));
}

int mpix_protocol_send_response(struct mpix_protocol_context *ctx,
                                uint8_t cmd_type,
                                enum mpix_protocol_status status,
                                const void *payload,
                                size_t payload_size)
{
    if (!ctx || !ctx->transport)
    {
        return -EINVAL;
    }

    if (payload_size > MPIX_PROTOCOL_MAX_PAYLOAD)
    {
        return -E2BIG;
    }

    struct mpix_protocol_header header = {
        .magic_start = MPIX_PROTOCOL_MAGIC_START,
        .version = MPIX_PROTOCOL_VERSION,
        .cmd_type = cmd_type | 0x80, /* Response flag */
        .sequence = ctx->sequence_counter++,
        .payload_length = (uint16_t)(1 + payload_size), /* status + payload */
        .checksum = 0};

    /* Calculate header checksum */
    header.checksum = mpix_protocol_checksum((uint8_t *)&header,
                                             sizeof(header) - sizeof(header.checksum));

    struct mpix_protocol_footer footer = {
        .magic_end = MPIX_PROTOCOL_MAGIC_END};

    /* Send header */
    int ret = mpix_transport_send(ctx->transport, (uint8_t *)&header, sizeof(header));
    if (ret < 0)
    {
        return ret;
    }

    /* Send status */
    uint8_t status_byte = (uint8_t)status;
    ret = mpix_transport_send(ctx->transport, &status_byte, 1);
    if (ret < 0)
    {
        return ret;
    }

    /* Send payload if any */
    if (payload && payload_size > 0)
    {
        ret = mpix_transport_send(ctx->transport, (const uint8_t *)payload, payload_size);
        if (ret < 0)
        {
            return ret;
        }
    }

    /* Send footer */
    ret = mpix_transport_send(ctx->transport, (uint8_t *)&footer, sizeof(footer));
    return ret;
}

int mpix_protocol_process(struct mpix_protocol_context *ctx)
{
    if (!ctx || !ctx->transport)
    {
        return -EINVAL;
    }

    /* Check if data is available */
    if (!mpix_transport_is_recv_ready(ctx->transport))
    {
        return -EAGAIN; /* No data available */
    }

    /* Read header */
    struct mpix_protocol_header header;
    int ret = mpix_transport_recv(ctx->transport, (uint8_t *)&header, sizeof(header));
    if (ret < (int)sizeof(header))
    {
        if (ret < 0)
        {
            /* Transport error */
            return ret;
        }
        else if (ret == 0)
        {
            /* No data available after all */
            return -EAGAIN;
        }
        else
        {
            /* Partial header received - this is problematic */
            /* TODO: We should implement a state machine to handle partial packets */
            return -EAGAIN;
        }
    }

/* Debug: Print received header for diagnosis */
#ifdef DEBUG_PROTOCOL
    printf("[PROTOCOL] Received header: magic=0x%08X, version=%d, cmd=0x%02X, len=%d, checksum=0x%04X\n",
           header.magic_start, header.version, header.cmd_type, header.payload_length, header.checksum);
#endif

    /* Validate header magic */
    if (header.magic_start != MPIX_PROTOCOL_MAGIC_START)
    {
        ctx->error_counter++;
#ifdef DEBUG_PROTOCOL
        printf("[PROTOCOL] Invalid magic start: expected 0x%08X, got 0x%08X\n",
               MPIX_PROTOCOL_MAGIC_START, header.magic_start);
#endif
        /* Try to recover by searching for the next magic start */
        return mpix_protocol_recover_sync(ctx);
    }

    /* Validate version */
    if (header.version != MPIX_PROTOCOL_VERSION)
    {
        ctx->error_counter++;
#ifdef DEBUG_PROTOCOL
        printf("[PROTOCOL] Invalid version: expected %d, got %d\n",
               MPIX_PROTOCOL_VERSION, header.version);
#endif
        return -EBADMSG;
    }

    /* Validate payload length */
    if (header.payload_length > MPIX_PROTOCOL_MAX_PAYLOAD)
    {
        ctx->error_counter++;
#ifdef DEBUG_PROTOCOL
        printf("[PROTOCOL] Payload too large: %d > %d\n",
               header.payload_length, MPIX_PROTOCOL_MAX_PAYLOAD);
#endif
        return -EBADMSG;
    }

    /* Verify header checksum */
    uint16_t calc_checksum = mpix_protocol_checksum((uint8_t *)&header,
                                                    sizeof(header) - sizeof(header.checksum));
    if (calc_checksum != header.checksum)
    {
        ctx->error_counter++;
#ifdef DEBUG_PROTOCOL
        printf("[PROTOCOL] Header checksum mismatch: expected 0x%04X, got 0x%04X\n",
               calc_checksum, header.checksum);
#endif
        return -EBADMSG;
    }

    /* Read payload */
    uint8_t *payload = NULL;
    if (header.payload_length > 0)
    {
        if (header.payload_length > ctx->rx_buffer_size)
        {
            ctx->error_counter++;
            return -E2BIG;
        }

        payload = ctx->rx_buffer;
        ret = mpix_transport_recv(ctx->transport, payload, header.payload_length);
        if (ret < (int)header.payload_length)
        {
            if (ret < 0)
            {
                return ret;
            }
            else
            {
/* Partial payload received */
#ifdef DEBUG_PROTOCOL
                printf("[PROTOCOL] Partial payload: expected %d, got %d\n",
                       header.payload_length, ret);
#endif
                return -EAGAIN;
            }
        }
    }

    /* Read footer */
    struct mpix_protocol_footer footer;
    ret = mpix_transport_recv(ctx->transport, (uint8_t *)&footer, sizeof(footer));
    if (ret < (int)sizeof(footer))
    {
        return ret < 0 ? ret : -EAGAIN;
    }

    if (footer.magic_end != MPIX_PROTOCOL_MAGIC_END)
    {
        ctx->error_counter++;
        return -EBADMSG;
    }

    /* Process command */
    switch (header.cmd_type & 0xF0)
    {
    case 0x10: /* Sensor commands */
        return protocol_handle_sensor_cmd(ctx, header.cmd_type, payload, header.payload_length);
    case 0x20: /* ISP commands */
        return protocol_handle_isp_cmd(ctx, header.cmd_type, payload, header.payload_length);
    case 0x30: /* Auto algorithm commands */
        return protocol_handle_auto_cmd(ctx, header.cmd_type, payload, header.payload_length);
    case 0x40: /* Streaming commands */
        return protocol_handle_stream_cmd(ctx, header.cmd_type, payload, header.payload_length);
    case 0x50: /* System commands */
        return protocol_handle_system_cmd(ctx, header.cmd_type, payload, header.payload_length);
    default:
        return mpix_protocol_send_response(ctx, header.cmd_type,
                                           MPIX_STATUS_INVALID_CMD, NULL, 0);
    }
}

static int protocol_handle_sensor_cmd(struct mpix_protocol_context *ctx,
                                      uint8_t cmd_type,
                                      const uint8_t *payload,
                                      size_t payload_size)
{
    switch (cmd_type)
    {
    case MPIX_CMD_SENSOR_GET_CAPS:
    {
        struct mpix_sensor_caps caps;
        int ret = mpix_sensor_get_capabilities(ctx->sensor, &caps);
        if (ret < 0)
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_ERROR, NULL, 0);
        }

        struct mpix_protocol_sensor_caps proto_caps = {
            .fourcc = caps.fourcc,
            .max_width = (uint16_t)caps.max_width,
            .max_height = (uint16_t)caps.max_height,
            .min_width = (uint16_t)caps.min_width,
            .min_height = (uint16_t)caps.min_height,
            .max_fps = caps.max_fps};

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK,
                                           &proto_caps, sizeof(proto_caps));
    }

    case MPIX_CMD_SENSOR_GET_FORMAT:
    {
        struct mpix_sensor_format format;
        int ret = mpix_sensor_get_format(ctx->sensor, &format);
        if (ret < 0)
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_ERROR, NULL, 0);
        }

        struct mpix_protocol_sensor_format proto_format = {
            .fourcc = format.fourcc,
            .width = (uint16_t)format.width,
            .height = format.height,
            .fps = format.fps};

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK,
                                           &proto_format, sizeof(proto_format));
    }

    case MPIX_CMD_SENSOR_SET_FORMAT:
    {
        if (payload_size != sizeof(struct mpix_protocol_sensor_format))
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        const struct mpix_protocol_sensor_format *proto_format =
            (const struct mpix_protocol_sensor_format *)payload;

        struct mpix_sensor_format format = {
            .fourcc = proto_format->fourcc,
            .width = proto_format->width,
            .height = proto_format->height,
            .fps = proto_format->fps};

        int ret = mpix_sensor_set_format(ctx->sensor, &format);
        enum mpix_protocol_status status = (ret == 0) ? MPIX_STATUS_OK : MPIX_STATUS_ERROR;
        return mpix_protocol_send_response(ctx, cmd_type, status, NULL, 0);
    }

    case MPIX_CMD_SENSOR_GET_CTRL:
    {
        if (payload_size != sizeof(uint32_t))
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        uint32_t cid = *(const uint32_t *)payload;
        int32_t value;
        int ret = mpix_sensor_get_ctrl(ctx->sensor, cid, &value);

        if (ret < 0)
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_ERROR, NULL, 0);
        }

        struct mpix_protocol_sensor_ctrl ctrl = {
            .cid = cid,
            .value = value};

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK,
                                           &ctrl, sizeof(ctrl));
    }

    case MPIX_CMD_SENSOR_SET_CTRL:
    {
        if (payload_size != sizeof(struct mpix_protocol_sensor_ctrl))
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        const struct mpix_protocol_sensor_ctrl *ctrl =
            (const struct mpix_protocol_sensor_ctrl *)payload;

        int ret = mpix_sensor_set_ctrl(ctx->sensor, ctrl->cid, &ctrl->value);
        enum mpix_protocol_status status = (ret == 0) ? MPIX_STATUS_OK : MPIX_STATUS_ERROR;
        return mpix_protocol_send_response(ctx, cmd_type, status, NULL, 0);
    }

    default:
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_CMD, NULL, 0);
    }
}

static int protocol_handle_isp_cmd(struct mpix_protocol_context *ctx,
                                   uint8_t cmd_type,
                                   const uint8_t *payload,
                                   size_t payload_size)
{
    switch (cmd_type)
    {
    case MPIX_CMD_ISP_GET_WHITE_BALANCE:
    {
        struct mpix_protocol_white_balance wb = {
            .red_level = ctx->auto_ctrls.correction.white_balance.red_level,
            .blue_level = ctx->auto_ctrls.correction.white_balance.blue_level};
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, &wb, sizeof(wb));
    }

    case MPIX_CMD_ISP_SET_WHITE_BALANCE:
    {
        if (payload_size != sizeof(struct mpix_protocol_white_balance))
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        const struct mpix_protocol_white_balance *wb =
            (const struct mpix_protocol_white_balance *)payload;

        ctx->auto_ctrls.correction.white_balance.red_level = wb->red_level;
        ctx->auto_ctrls.correction.white_balance.blue_level = wb->blue_level;

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_ISP_GET_BLACK_LEVEL:
    {
        struct mpix_protocol_black_level bl = {
            .level = ctx->auto_ctrls.correction.black_level.level};
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, &bl, sizeof(bl));
    }

    case MPIX_CMD_ISP_SET_BLACK_LEVEL:
    {
        if (payload_size != sizeof(struct mpix_protocol_black_level))
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        const struct mpix_protocol_black_level *bl =
            (const struct mpix_protocol_black_level *)payload;

        ctx->auto_ctrls.correction.black_level.level = bl->level;

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_ISP_GET_GAMMA:
    {
        struct mpix_protocol_gamma gamma = {
            .level = ctx->auto_ctrls.correction.gamma.level};
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, &gamma, sizeof(gamma));
    }

    case MPIX_CMD_ISP_SET_GAMMA:
    {
        if (payload_size != sizeof(struct mpix_protocol_gamma))
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        const struct mpix_protocol_gamma *gamma =
            (const struct mpix_protocol_gamma *)payload;

        ctx->auto_ctrls.correction.gamma.level = gamma->level;

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_ISP_GET_COLOR_MATRIX:
    {
        struct mpix_protocol_color_matrix cm;
        memcpy(cm.levels, ctx->auto_ctrls.correction.color_matrix.levels, sizeof(cm.levels));
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, &cm, sizeof(cm));
    }

    case MPIX_CMD_ISP_SET_COLOR_MATRIX:
    {
        if (payload_size != sizeof(struct mpix_protocol_color_matrix))
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        const struct mpix_protocol_color_matrix *cm =
            (const struct mpix_protocol_color_matrix *)payload;

        memcpy(ctx->auto_ctrls.correction.color_matrix.levels, cm->levels, sizeof(cm->levels));

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_ISP_GET_JPEG_QUALITY:
    {
        struct mpix_protocol_jpeg_quality quality = {
            .quality = ctx->jpeg_quality};
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, &quality, sizeof(quality));
    }

    case MPIX_CMD_ISP_SET_JPEG_QUALITY:
    {
        if (payload_size != sizeof(struct mpix_protocol_jpeg_quality))
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        const struct mpix_protocol_jpeg_quality *quality =
            (const struct mpix_protocol_jpeg_quality *)payload;

        /* Validate JPEG quality range */
        if (quality->quality < 1 || quality->quality > 100)
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        ctx->jpeg_quality = quality->quality;

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_ISP_ENABLE_CORRECTION:
    {
        if (payload_size != sizeof(struct mpix_protocol_isp_correction_control))
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        const struct mpix_protocol_isp_correction_control *ctrl =
            (const struct mpix_protocol_isp_correction_control *)payload;

        /* Enable corrections based on bitmask */
        if (ctrl->correction_type & 0x01)
            ctx->black_level_correction_enabled = true;
        if (ctrl->correction_type & 0x02)
            ctx->gamma_correction_enabled = true;
        if (ctrl->correction_type & 0x04)
            ctx->white_balance_correction_enabled = true;
        if (ctrl->correction_type & 0x08)
            ctx->color_matrix_correction_enabled = true;
        if (ctrl->correction_type & 0x10)
            ctx->denoise_filter_enabled = true;

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_ISP_DISABLE_CORRECTION:
    {
        if (payload_size != sizeof(struct mpix_protocol_isp_correction_control))
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        const struct mpix_protocol_isp_correction_control *ctrl =
            (const struct mpix_protocol_isp_correction_control *)payload;

        /* Disable corrections based on bitmask */
        if (ctrl->correction_type & 0x01)
            ctx->black_level_correction_enabled = false;
        if (ctrl->correction_type & 0x02)
            ctx->gamma_correction_enabled = false;
        if (ctrl->correction_type & 0x04)
            ctx->white_balance_correction_enabled = false;
        if (ctrl->correction_type & 0x08)
            ctx->color_matrix_correction_enabled = false;
        if (ctrl->correction_type & 0x10)
            ctx->denoise_filter_enabled = false;

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_ISP_GET_CORRECTION_STATE:
    {
        struct mpix_protocol_isp_correction_state state = {
            .black_level_enabled = ctx->black_level_correction_enabled ? 1 : 0,
            .gamma_enabled = ctx->gamma_correction_enabled ? 1 : 0,
            .white_balance_enabled = ctx->white_balance_correction_enabled ? 1 : 0,
            .color_matrix_enabled = ctx->color_matrix_correction_enabled ? 1 : 0,
            .denoise_enabled = ctx->denoise_filter_enabled ? 1 : 0};
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, &state, sizeof(state));
    }

    default:
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_CMD, NULL, 0);
    }
}

static int protocol_handle_auto_cmd(struct mpix_protocol_context *ctx,
                                    uint8_t cmd_type,
                                    const uint8_t *payload,
                                    size_t payload_size)
{
    switch (cmd_type)
    {
    case MPIX_CMD_AUTO_GET_TARGET:
    {
        struct mpix_protocol_auto_target target = {
            .ae_target = ctx->auto_ctrls.ae_target};
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, &target, sizeof(target));
    }

    case MPIX_CMD_AUTO_SET_TARGET:
    {
        if (payload_size != sizeof(struct mpix_protocol_auto_target))
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        const struct mpix_protocol_auto_target *target =
            (const struct mpix_protocol_auto_target *)payload;

        ctx->auto_ctrls.ae_target = target->ae_target;

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_AUTO_GET_STATE:
    {
        struct mpix_protocol_auto_state state = {
            .ae_enabled = ctx->ae_enabled ? 1 : 0,
            .awb_enabled = ctx->awb_enabled ? 1 : 0,
            .ablc_enabled = ctx->ablc_enabled ? 1 : 0,
            .reserved = 0,
            .exposure_level = ctx->auto_ctrls.exposure_level,
            .wb_red_level = ctx->auto_ctrls.correction.white_balance.red_level,
            .wb_blue_level = ctx->auto_ctrls.correction.white_balance.blue_level,
            .black_level = ctx->auto_ctrls.correction.black_level.level,
            .padding = {0, 0, 0}};
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, &state, sizeof(state));
    }

    case MPIX_CMD_AUTO_ENABLE_AE:
    {
        ctx->ae_enabled = true;
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_AUTO_DISABLE_AE:
    {
        ctx->ae_enabled = false;
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_AUTO_ENABLE_AWB:
    {
        ctx->awb_enabled = true;
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_AUTO_DISABLE_AWB:
    {
        ctx->awb_enabled = false;
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_AUTO_ENABLE_ABLC:
    {
        ctx->ablc_enabled = true;
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_AUTO_DISABLE_ABLC:
    {
        ctx->ablc_enabled = false;
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_AUTO_ENABLE_ALL:
    {
        ctx->ae_enabled = true;
        ctx->awb_enabled = true;
        ctx->ablc_enabled = true;
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_AUTO_DISABLE_ALL:
    {
        ctx->ae_enabled = false;
        ctx->awb_enabled = false;
        ctx->ablc_enabled = false;
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    default:
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_CMD, NULL, 0);
    }
}

static int protocol_handle_stream_cmd(struct mpix_protocol_context *ctx,
                                      uint8_t cmd_type,
                                      const uint8_t *payload,
                                      size_t payload_size)
{
    switch (cmd_type)
    {
    case MPIX_CMD_STREAM_START:
    {
        int ret = mpix_protocol_start_streaming(ctx);
        enum mpix_protocol_status status = (ret == 0) ? MPIX_STATUS_OK : MPIX_STATUS_ERROR;
        return mpix_protocol_send_response(ctx, cmd_type, status, NULL, 0);
    }

    case MPIX_CMD_STREAM_STOP:
    {
        int ret = mpix_protocol_stop_streaming(ctx);
        enum mpix_protocol_status status = (ret == 0) ? MPIX_STATUS_OK : MPIX_STATUS_ERROR;
        return mpix_protocol_send_response(ctx, cmd_type, status, NULL, 0);
    }

    case MPIX_CMD_STREAM_GET_STATUS:
    {
        struct mpix_protocol_stream_status status = {
            .is_streaming = ctx->streaming ? 1 : 0,
            .stream_mode = (uint8_t)ctx->stream_mode,
            .frame_count = ctx->frame_counter,
            .error_count = ctx->error_counter};
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, &status, sizeof(status));
    }

    case MPIX_CMD_STREAM_SET_MODE:
    {
        if (payload_size != sizeof(struct mpix_protocol_stream_mode_config))
        {
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }

        const struct mpix_protocol_stream_mode_config *mode_config =
            (const struct mpix_protocol_stream_mode_config *)payload;

        if (mode_config->mode >= 4)
        { /* Invalid mode */
            return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_PARAM, NULL, 0);
        }
        ctx->stream_mode = (enum mpix_protocol_stream_mode)mode_config->mode;
        mpix_port_printf("Setting stream mode to %d (auto: %d)\n",
                         mode_config->mode, mode_config->enable_auto);
        /* For backward compatibility, enable_auto controls all algorithms */
        if (mode_config->enable_auto)
        {
            ctx->ae_enabled = true;
            ctx->awb_enabled = true;
            ctx->ablc_enabled = true;
        }
        else
        {
            ctx->ae_enabled = false;
            ctx->awb_enabled = false;
            ctx->ablc_enabled = false;
        }

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    default:
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_CMD, NULL, 0);
    }
}

static int protocol_handle_system_cmd(struct mpix_protocol_context *ctx,
                                      uint8_t cmd_type,
                                      const uint8_t *payload,
                                      size_t payload_size)
{
    (void)payload;
    (void)payload_size;

    switch (cmd_type)
    {
    case MPIX_CMD_SYSTEM_PING:
    {
        /* Simple ping-pong */
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, NULL, 0);
    }

    case MPIX_CMD_SYSTEM_GET_VERSION:
    {
        struct mpix_protocol_version version = {
            .major = 1,
            .minor = 0,
            .patch = 0,
            .reserved = 0};
        strcpy(version.build_info, "MPIX Stream v1.0.0");

        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_OK, &version, sizeof(version));
    }

    case MPIX_CMD_SYSTEM_RESET:
    {
        /* Implement system reset if needed */
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_NOT_SUPPORTED, NULL, 0);
    }

    default:
        return mpix_protocol_send_response(ctx, cmd_type, MPIX_STATUS_INVALID_CMD, NULL, 0);
    }
}

int mpix_protocol_start_streaming(struct mpix_protocol_context *ctx)
{
    if (!ctx || !ctx->sensor)
    {
        return -EINVAL;
    }

    if (ctx->streaming)
    {
        return 0; /* Already streaming */
    }

    int ret = mpix_sensor_start_stream(ctx->sensor);
    if (ret < 0)
    {
        return ret;
    }

    ctx->streaming = true;
    ctx->frame_counter = 0;

    return 0;
}

int mpix_protocol_stop_streaming(struct mpix_protocol_context *ctx)
{
    if (!ctx || !ctx->sensor)
    {
        return -EINVAL;
    }

    if (!ctx->streaming)
    {
        return 0; /* Already stopped */
    }

    int ret = mpix_sensor_stop_stream(ctx->sensor);
    if (ret < 0)
    {
        return ret;
    }

    ctx->streaming = false;

    return 0;
}

int mpix_protocol_send_frame(struct mpix_protocol_context *ctx,
                             const struct mpix_image *image)
{
    if (!ctx || !ctx->transport || !image)
    {
        return -EINVAL;
    }

    struct mpix_protocol_frame_header frame_header = {
        .magic_start = MPIX_PROTOCOL_MAGIC_START,
        .frame_id = ++ctx->frame_counter,
        .width = image->width,
        .height = image->height,
        .data_size = (uint32_t)image->size,
        .fourcc = image->fourcc,
        .checksum = mpix_protocol_checksum((const uint8_t *)image->buffer, image->size),
        .reserved = 0};

    struct mpix_protocol_frame_footer frame_footer = {
        .magic_end = MPIX_PROTOCOL_MAGIC_END};

    /* Send frame header */
    int ret = mpix_transport_send(ctx->transport, (uint8_t *)&frame_header, sizeof(frame_header));
    if (ret < 0)
    {
        ctx->error_counter++;
        return ret;
    }

    /* Send frame data */
    ret = mpix_transport_send(ctx->transport, (const uint8_t *)image->buffer, image->size);
    if (ret < 0)
    {
        ctx->error_counter++;
        return ret;
    }

    /* Send frame footer */
    ret = mpix_transport_send(ctx->transport, (uint8_t *)&frame_footer, sizeof(frame_footer));
    if (ret < 0)
    {
        ctx->error_counter++;
        return ret;
    }

    return 0;
}

/* Protocol synchronization recovery function */
static int mpix_protocol_recover_sync(struct mpix_protocol_context *ctx)
{
    if (!ctx || !ctx->transport)
    {
        return -EINVAL;
    }

#ifdef DEBUG_PROTOCOL
    printf("[PROTOCOL] Attempting to recover synchronization...\n");
#endif

    /* Try to find the next valid magic start sequence */
    uint8_t byte;
    uint32_t search_buffer = 0;
    int bytes_discarded = 0;
    const int max_search = 512; /* Limit search to prevent infinite loop */

    for (int i = 0; i < max_search; i++)
    {
        int ret = mpix_transport_recv(ctx->transport, &byte, 1);
        if (ret <= 0)
        {
            /* No more data available */
            break;
        }

        bytes_discarded++;
        search_buffer = (search_buffer << 8) | byte;

        if (search_buffer == MPIX_PROTOCOL_MAGIC_START)
        {
#ifdef DEBUG_PROTOCOL
            printf("[PROTOCOL] Found sync after discarding %d bytes\n", bytes_discarded - 4);
#endif

            /* We found the magic start, but we've consumed it.
             * We need to put it back somehow or handle this differently.
             * For now, we'll return -EAGAIN to retry processing. */
            return -EAGAIN;
        }
    }

#ifdef DEBUG_PROTOCOL
    printf("[PROTOCOL] Failed to find sync, discarded %d bytes\n", bytes_discarded);
#endif

    return -EBADMSG;
}

/** @} */
