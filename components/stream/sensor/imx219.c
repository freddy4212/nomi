/**
 * SPDX-License-Identifier: Apache-2.0
 * @file imx219.c
 * @brief IMX219 camera sensor driver implementation
 */

#include <errno.h>
#include <string.h>
#include <ctype.h>

#include <mpix/sensor/sccb.h>
#include <mpix/sensor/imx219.h>
#include <mpix/sensor/datapath.h>
#include <mpix/sensor/mipi_csi.h>

/* IMX219 register definitions */
#define IMX219_CHIP_ID_H_REG 0x0000 /* Chip ID high byte */
#define IMX219_CHIP_ID_L_REG 0x0001 /* Chip ID low byte */
#define IMX219_CHIP_ID 0x0219       /* Expected chip ID */
#define IMX219_SW_RESET_REG 0x0103
#define IMX219_MODE_SELECT_REG 0x0100
#define IMX219_STREAMING_REG 0x0100

/* IMX219 mode register values */
#define IMX219_MODE_STANDBY 0x00
#define IMX219_MODE_STREAMING 0x01

/* Resolution configuration tables */
struct imx219_reg
{
    uint16_t addr;
    uint8_t value;
};

/* VGA 640x480 30fps configuration */
static const struct imx219_reg imx219_640x480_regs[] = {
    /* Stream off */
    {0x0100, 0x00},
    /* Clock settings */
    {0x0114, 0x01}, /* CSI_LANE_MODE */
    {0x0128, 0x00}, /* DPHY_CTRL */
    {0x012A, 0x18}, /* EXCK_FREQ_MSB */
    {0x012B, 0x00}, /* EXCK_FREQ_LSB */
    /* Image orientation */
    {0x0172, 0x03}, /* IMG_ORIENTATION */
    /* Binning configuration */
    {0x0157, 0x00}, /* ANALOG_GAIN_GLOBAL */
    {0x0160, 0x05}, /* FRM_LENGTH_A_MSB - reduced for 30fps */
    {0x0161, 0x28}, /* FRM_LENGTH_A_LSB - frame length 900 */
    {0x0162, 0x0D}, /* LINE_LENGTH_A_MSB */
    {0x0163, 0x78}, /* LINE_LENGTH_A_LSB */
    /* Crop settings - center crop for better quality */
    {0x0164, 0x03}, /* X_ADD_STA_A_MSB - start X = 1000 */
    {0x0165, 0xE8}, /* X_ADD_STA_A_LSB */
    {0x0166, 0x08}, /* X_ADD_END_A_MSB - end X = 2279 */
    {0x0167, 0xE7}, /* X_ADD_END_A_LSB */
    {0x0168, 0x02}, /* Y_ADD_STA_A_MSB - start Y = 752 */
    {0x0169, 0xF0}, /* Y_ADD_STA_A_LSB */
    {0x016A, 0x06}, /* Y_ADD_END_A_MSB - end Y = 1711 */
    {0x016B, 0xAF}, /* Y_ADD_END_A_LSB */
    /* Output size */
    {0x016C, 0x02}, /* X_OUTPUT_SIZE_MSB */
    {0x016D, 0x80}, /* X_OUTPUT_SIZE_LSB (640) */
    {0x016E, 0x01}, /* Y_OUTPUT_SIZE_MSB */
    {0x016F, 0xE0}, /* Y_OUTPUT_SIZE_LSB (480) */
    /* Binning settings - 2x2 binning for better quality */
    {0x0170, 0x01}, /* X_ODD_INC_A - 2x decimation */
    {0x0171, 0x01}, /* Y_ODD_INC_A - 2x decimation */
    {0x0174, 0x03}, /* BINNING_MODE_H_A - 2x2 horizontal binning */
    {0x0175, 0x03}, /* BINNING_MODE_V_A - 2x2 vertical binning */
    /* CSI Data Format */
    {0x018C, 0x08}, /* CSI_DATA_FORMAT_A_MSB */
    {0x018D, 0x08}, /* CSI_DATA_FORMAT_A_LSB */
    /* PLL settings */
    {0x0301, 0x05}, /* VTPXCK_DIV */
    {0x0303, 0x01}, /* VTSYCK_DIV */
    {0x0304, 0x03}, /* PREPLLCK_VT_DIV */
    {0x0305, 0x03}, /* PREPLLCK_OP_DIV */
    {0x0306, 0x00}, /* PLL_VT_MPY_MSB */
    {0x0307, 0x39}, /* PLL_VT_MPY_LSB */
    {0x0309, 0x08}, /* OPPXCK_DIV */
    {0x030B, 0x01}, /* OPSYCK_DIV */
    {0x030C, 0x00}, /* PLL_OP_MPY_MSB */
    {0x030D, 0x72}, /* PLL_OP_MPY_LSB */
    /* Data rate settings */
    {0x455E, 0x00}, /* CIS_TUNING_80 */
    {0x471E, 0x4B}, /* CIS_TUNING_87 */
    {0x4767, 0x0F}, /* CIS_TUNING_99 */
    {0x4750, 0x14}, /* CIS_TUNING_96 */
    {0x4540, 0x00}, /* CIS_TUNING_64 */
    {0x47B4, 0x14}, /* CIS_TUNING_116 */
    {0x4713, 0x30}, /* CIS_TUNING_81 */
    {0x478B, 0x10}, /* CIS_TUNING_103 */
    {0x478F, 0x10}, /* CIS_TUNING_104 */
    {0x4793, 0x10}, /* CIS_TUNING_105 */
    {0x4797, 0x0E}, /* CIS_TUNING_106 */
    {0x479B, 0x0E}, /* CIS_TUNING_107 */
    /* Initial exposure and gain settings for proper brightness */
    {0x0157, 0x80}, /* ANALOG_GAIN_GLOBAL - moderate gain */
    {0x015A, 0x0D}, /* COARSE_INTEGRATION_TIME_MSB */
    {0x015B, 0x00}, /* COARSE_INTEGRATION_TIME_LSB */
    {0xFFFF, 0xFF}  /* End marker */
};

/* 1280x960 30fps configuration - based on working 3280x2464 config */
static const struct imx219_reg imx219_1280x960_regs[] = {
    /* Stream off */
    {0x0100, 0x00},

    /* To Access Addresses 3000-5fff, send the following commands */
    {0x30EB, 0x0C},
    {0x30EB, 0x05},
    {0x300A, 0xFF},
    {0x300B, 0xFF},
    {0x30EB, 0x05},
    {0x30EB, 0x09},

    /* Image orientation */
    {0x0172, 0x03}, /* IMG_ORIENTATION */

    /* PLL Clock Table */
    {0x0301, 0x05}, /* VTPXCK_DIV */
    {0x0303, 0x01}, /* VTSYSCK_DIV */
    {0x0304, 0x03}, /* PREPLLCK_VT_DIV */
    {0x0305, 0x03}, /* PREPLLCK_OP_DIV */
    {0x0306, 0x00}, /* PLL_VT_MPY */
    {0x0307, 0x39},
    {0x030B, 0x01}, /* OP_SYS_CLK_DIV */
    {0x030C, 0x00}, /* PLL_OP_MPY */
    {0x030D, 0x72},

    /* Undocumented registers */
    {0x455E, 0x00},
    {0x471E, 0x4B},
    {0x4767, 0x0F},
    {0x4750, 0x14},
    {0x4540, 0x00},
    {0x47B4, 0x14},
    {0x4713, 0x30},
    {0x478B, 0x10},
    {0x478F, 0x10},
    {0x4793, 0x10},
    {0x4797, 0x0E},
    {0x479B, 0x0E},

    /* Frame Bank Register Group "A" */
    {0x0160, 0x05}, /* FRM_LENGTH_A_MSB - frame length for 30fps */
    {0x0161, 0x28}, /* FRM_LENGTH_A_LSB - frame length 1320 */
    {0x0162, 0x0D}, /* Line_Length_A */
    {0x0163, 0x78},
    {0x0170, 0x03}, /* X_ODD_INC_A - 2x2 binning (3 = skip 1 pixel) */
    {0x0171, 0x03}, /* Y_ODD_INC_A - 2x2 binning (3 = skip 1 line) */

    /* Output setup registers */
    {0x0114, 0x01}, /* CSI 2-Lane Mode */
    {0x0128, 0x00}, /* DPHY Auto Mode */
    {0x012A, 0x18}, /* EXCK_Freq */
    {0x012B, 0x00},

    /* Crop and output settings for 2560x1920 -> 1280x960 with 2x2 binning */
    {0x0164, 0x01}, /* X_ADD_STA_A MSB - start X = 360 (center crop) */
    {0x0165, 0x68}, /* X_ADD_STA_A LSB */
    {0x0166, 0x0B}, /* X_ADD_END_A MSB - end X = 2919 (360+2560-1) */
    {0x0167, 0x67}, /* X_ADD_END_A LSB */
    {0x0168, 0x01}, /* Y_ADD_STA_A MSB - start Y = 272 (center crop) */
    {0x0169, 0x10}, /* Y_ADD_STA_A LSB */
    {0x016A, 0x08}, /* Y_ADD_END_A MSB - end Y = 2191 (272+1920-1) */
    {0x016B, 0x8F}, /* Y_ADD_END_A LSB */
    {0x016C, 0x05}, /* X_OUTPUT_SIZE MSB = 1280 */
    {0x016D, 0x00}, /* X_OUTPUT_SIZE LSB */
    {0x016E, 0x03}, /* Y_OUTPUT_SIZE MSB = 960 */
    {0x016F, 0xC0}, /* Y_OUTPUT_SIZE LSB */
    {0x0624, 0x05}, /* Output width MSB */
    {0x0625, 0x00}, /* Output width LSB */
    {0x0626, 0x03}, /* Output height MSB */
    {0x0627, 0xC0}, /* Output height LSB */

    /* RAW10 format */
    {0x018C, 0x0A}, /* CSI_DATA_FORMAT_A MSB */
    {0x018D, 0x0A}, /* CSI_DATA_FORMAT_A LSB */

    /* PLL settings */
    {0x0301, 0x05}, /* VTPXCK_DIV */
    {0x0303, 0x01}, /* VTSYCK_DIV */
    {0x0304, 0x03}, /* PREPLLCK_VT_DIV */
    {0x0305, 0x03}, /* PREPLLCK_OP_DIV */
    {0x0306, 0x00}, /* PLL_VT_MPY_MSB */
    {0x0307, 0x39}, /* PLL_VT_MPY_LSB */
    {0x0309, 0x0A}, /* OPPXCK_DIV */
    {0x030B, 0x01}, /* OPSYCK_DIV */
    {0x030C, 0x00}, /* PLL_OP_MPY_MSB */
    {0x030D, 0x72}, /* PLL_OP_MPY_LSB */
    /* Data rate settings */
    {0x455E, 0x00}, /* CIS_TUNING_80 */
    {0x471E, 0x4B}, /* CIS_TUNING_87 */
    {0x4767, 0x0F}, /* CIS_TUNING_99 */
    {0x4750, 0x14}, /* CIS_TUNING_96 */
    {0x4540, 0x00}, /* CIS_TUNING_64 */
    {0x47B4, 0x14}, /* CIS_TUNING_116 */
    {0x4713, 0x30}, /* CIS_TUNING_81 */
    {0x478B, 0x10}, /* CIS_TUNING_103 */
    {0x478F, 0x10}, /* CIS_TUNING_104 */
    {0x4793, 0x10}, /* CIS_TUNING_105 */
    {0x4797, 0x0E}, /* CIS_TUNING_106 */
    {0x479B, 0x0E}, /* CIS_TUNING_107 */
    /* Initial exposure and gain settings for proper brightness */
    {0x0157, 0x80}, /* ANALOG_GAIN_GLOBAL - moderate gain */
    {0x015A, 0x0D}, /* COARSE_INTEGRATION_TIME_MSB */
    {0x015B, 0x00}, /* COARSE_INTEGRATION_TIME_LSB */
    {0xFFFF, 0xFF}  /* End marker */
};

/* Mode configuration table */
static const struct
{
    const struct imx219_reg *regs;
    uint16_t width;
    uint16_t height;
    uint16_t fps;
    uint32_t fourcc;
} imx219_modes[IMX219_MODE_MAX] = {
    [IMX219_MODE_640x480_30FPS] = {
        .regs = imx219_640x480_regs,
        .width = 640,
        .height = 480,
        .fps = 30,
        .fourcc = MPIX_FMT_SRGGB8,
    },
    [IMX219_MODE_1280x960_30FPS] = {
        .regs = imx219_1280x960_regs,
        .width = 1280,
        .height = 960,
        .fps = 30,
        .fourcc = MPIX_FMT_SRGGB8,
    },
};

/* Global hardware context */
static struct imx219_hw_ctx g_imx219_hw_ctx;

/* Helper functions */
static int imx219_write_reg(uint8_t addr, uint16_t reg, uint8_t value)
{
    return sccb_write_reg(addr, reg, value);
}

static int imx219_read_reg(uint8_t addr, uint16_t reg, uint8_t *value)
{
    return sccb_read_reg(addr, reg, value);
}

static int imx219_write_regs(uint8_t addr, const struct imx219_reg *regs)
{
    int ret;

    for (int i = 0; regs[i].addr != 0xFFFF; i++)
    {
        ret = imx219_write_reg(addr, regs[i].addr, regs[i].value);
        if (ret < 0)
        {
            MPIX_ERR("Failed to write reg 0x%04X: %d", regs[i].addr, ret);
            return ret;
        }

        /* Add delay after reset */
        if (regs[i].addr == IMX219_SW_RESET_REG)
        {
            sccb_delay_ms(10);
        }
    }

    return 0;
}

static imx219_mode_t imx219_find_mode(uint16_t width, uint16_t height)
{
    for (int i = 0; i < IMX219_MODE_MAX; i++)
    {
        if (imx219_modes[i].width == width && imx219_modes[i].height == height)
        {
            return i;
        }
    }
    return IMX219_MODE_MAX; /* Not found */
}

/* Sensor operations implementation */
static int imx219_init(const struct mpix_sensor *sensor)
{
    struct imx219_hw_ctx *ctx = (struct imx219_hw_ctx *)sensor->hw_ctx;

    if (!ctx)
    {
        return -EINVAL;
    }

    if (ctx->initialized)
    {
        return 0;
    }

    /* Initialize hardware context */
    ctx->i2c_addr = IMX219_I2C_ADDR;
    ctx->streaming = false;
    ctx->current_mode = IMX219_MODE_640x480_30FPS;

    /* Initialize controls to default values */
    ctx->brightness = 0;
    ctx->contrast = 0;
    ctx->saturation = 0;
    ctx->h_mirror = false;
    ctx->v_flip = false;
    ctx->exposure = 0x0100; /* Default exposure time for IMX219 */
    ctx->white_balance = 1; /* auto white balance enabled */
    ctx->test_pattern = 0;

    ctx->initialized = true;

    return 0;
}

static int imx219_probe(const struct mpix_sensor *sensor)
{
    struct imx219_hw_ctx *ctx = (struct imx219_hw_ctx *)sensor->hw_ctx;
    uint8_t chip_id_h, chip_id_l;
    uint16_t chip_id;
    int ret;

    if (!ctx)
    {
        return -EINVAL;
    }

    /* Read chip ID - IMX219 uses 0x0000 (high) and 0x0001 (low) */
    ret = imx219_read_reg(ctx->i2c_addr, IMX219_CHIP_ID_H_REG, &chip_id_h);
    if (ret < 0)
    {
        return ret;
    }

    ret = imx219_read_reg(ctx->i2c_addr, IMX219_CHIP_ID_L_REG, &chip_id_l);
    if (ret < 0)
    {
        return ret;
    }

    chip_id = (chip_id_h << 8) | chip_id_l;

    if (chip_id != IMX219_CHIP_ID)
    {
        return -ENODEV;
    }

    return 0;
}

static int imx219_get_capabilities(const struct mpix_sensor *sensor,
                                   struct mpix_sensor_caps *caps)
{
    if (!sensor || !caps)
    {
        return -EINVAL;
    }

    caps->fourcc = MPIX_FMT_SRGGB8;
    caps->max_width = 1280;
    caps->max_height = 960;
    caps->min_width = 640;
    caps->min_height = 480;
    caps->max_fps = 30;

    return 0;
}

static int imx219_get_format(const struct mpix_sensor *sensor,
                             struct mpix_sensor_format *format)
{
    struct imx219_hw_ctx *ctx = (struct imx219_hw_ctx *)sensor->hw_ctx;

    if (!sensor || !format || !ctx)
    {
        return -EINVAL;
    }

    *format = ctx->current_format;

    return 0;
}

static int imx219_set_format(const struct mpix_sensor *sensor,
                             const struct mpix_sensor_format *format)
{
    struct imx219_hw_ctx *ctx = (struct imx219_hw_ctx *)sensor->hw_ctx;
    imx219_mode_t mode;
    int ret;

    if (!sensor || !format || !ctx)
    {
        return -EINVAL;
    }

    // if (format->fourcc != MPIX_FMT_SRGGB8)
    // {
    //     return -ENOTSUP;
    // }

    /* Find matching mode */
    mode = imx219_find_mode(format->width, format->height);

    MPIX_INF("Requested format: %ux%u@%u, mode: %d",
             format->width, format->height, format->fps, mode);

    if (mode >= IMX219_MODE_MAX)
    {
        return -ENOTSUP;
    }

    /* Stop streaming if active */
    if (ctx->streaming)
    {
        ret = imx219_write_reg(ctx->i2c_addr, IMX219_MODE_SELECT_REG, IMX219_MODE_STANDBY);
        if (ret < 0)
        {
            return ret;
        }
        ctx->streaming = false;
    }

    /* Apply mode configuration */
    ret = imx219_write_regs(ctx->i2c_addr, imx219_modes[mode].regs);
    if (ret < 0)
    {
        return ret;
    }

    /* Configure MIPI CSI */
    const mipi_csi_config_t csi_config = {
        .clock_freq_mhz = 456, /* IMX219 MIPI clock frequency */
        .lane_count = MIPI_CSI_LANE_2,
        .pixel_depth = MIPI_CSI_PIXEL_DEPTH_10,
        .clock_mode = MIPI_CSI_CLK_MODE_CONTINUOUS,
        .deskew_enable = false};
    mipi_csi_configure(&csi_config);
    mipi_csi_enable();

    /* Configure datapath */
    const datapath_config_t dp_config = {
        .width = format->width,
        .height = format->height,
        .pixel_depth = 10, /* IMX219 outputs 10-bit */
        .enable_crop = false,
        .crop_x = 0,
        .crop_y = 0,
        .crop_width = format->width,
        .crop_height = format->height};
    datapath_configure(&dp_config);

    /* Update context */
    ctx->current_mode = mode;
    ctx->current_format = *format;

    return 0;
}

static int imx219_set_ctrl(const struct mpix_sensor *sensor, uint32_t cid, const void *value)
{
    struct imx219_hw_ctx *ctx = (struct imx219_hw_ctx *)sensor->hw_ctx;
    int val;

    if (!sensor || !value || !ctx)
    {
        return -EINVAL;
    }

    val = *(const int *)value;

    switch (cid)
    {
    case MPIX_SENSOR_BRIGHTNESS:
        ctx->brightness = val;
        /* TODO: Apply brightness register settings */
        break;

    case MPIX_SENSOR_CONTRAST:
        ctx->contrast = val;
        /* TODO: Apply contrast register settings */
        break;

    case MPIX_SENSOR_SATURATION:
        ctx->saturation = val;
        /* TODO: Apply saturation register settings */
        break;

    case MPIX_SENSOR_HMIRROR:
        ctx->h_mirror = (val != 0);
        /* TODO: Apply horizontal mirror register settings */
        break;

    case MPIX_SENSOR_VFLIP:
        ctx->v_flip = (val != 0);
        /* TODO: Apply vertical flip register settings */
        break;

    case MPIX_SENSOR_EXPOSURE:
        ctx->exposure = val;
        /* Apply exposure time (coarse integration time) */
        if (val > 0)
        {
            uint16_t exp_time = (uint16_t)(val & 0xFFFF);
            imx219_write_reg(ctx->i2c_addr, 0x015A, (exp_time >> 8) & 0xFF); /* MSB */
            imx219_write_reg(ctx->i2c_addr, 0x015B, exp_time & 0xFF);        /* LSB */
        }
        break;

    case MPIX_SENSOR_AWB:
        ctx->white_balance = val;
        /* TODO: Apply white balance register settings */
        break;

    case MPIX_SENSOR_TEST_PATTERN:
        ctx->test_pattern = val;
        /* TODO: Apply test pattern register settings */
        break;

    default:
        return -EINVAL;
    }

    return 0;
}

static int imx219_get_ctrl(const struct mpix_sensor *sensor, uint32_t cid, void *value)
{
    struct imx219_hw_ctx *ctx = (struct imx219_hw_ctx *)sensor->hw_ctx;
    int *val = (int *)value;

    if (!sensor || !value || !ctx)
    {
        return -EINVAL;
    }

    switch (cid)
    {
    case MPIX_SENSOR_BRIGHTNESS:
        *val = ctx->brightness;
        break;

    case MPIX_SENSOR_CONTRAST:
        *val = ctx->contrast;
        break;

    case MPIX_SENSOR_SATURATION:
        *val = ctx->saturation;
        break;

    case MPIX_SENSOR_HMIRROR:
        *val = ctx->h_mirror ? 1 : 0;
        break;

    case MPIX_SENSOR_VFLIP:
        *val = ctx->v_flip ? 1 : 0;
        break;

    case MPIX_SENSOR_EXPOSURE:
        *val = ctx->exposure;
        break;

    case MPIX_SENSOR_AWB:
        *val = ctx->white_balance;
        break;

    case MPIX_SENSOR_TEST_PATTERN:
        *val = ctx->test_pattern;
        break;

    default:
        return -EINVAL;
    }

    return 0;
}

static int imx219_start_stream(struct mpix_sensor *sensor)
{
    struct imx219_hw_ctx *ctx = (struct imx219_hw_ctx *)sensor->hw_ctx;
    int ret;

    if (!sensor || !ctx)
    {
        return -EINVAL;
    }

    if (ctx->streaming)
    {
        return 0; /* Already streaming */
    }

    /* Start datapath */
    datapath_start();

    /* Start streaming */
    ret = imx219_write_reg(ctx->i2c_addr, IMX219_STREAMING_REG, IMX219_MODE_STREAMING);
    if (ret < 0)
    {
        datapath_stop();
        return ret;
    }

    ctx->streaming = true;
    sensor->state = MPIX_SENSOR_STATE_STREAMING;

    return 0;
}

static int imx219_stop_stream(struct mpix_sensor *sensor)
{
    struct imx219_hw_ctx *ctx = (struct imx219_hw_ctx *)sensor->hw_ctx;
    int ret;

    if (!sensor || !ctx)
    {
        return -EINVAL;
    }

    if (!ctx->streaming)
    {
        return 0; /* Already stopped */
    }

    /* Stop datapath first */
    datapath_stop();

    /* Stop streaming */
    ret = imx219_write_reg(ctx->i2c_addr, IMX219_STREAMING_REG, IMX219_MODE_STANDBY);
    if (ret < 0)
    {
        return ret;
    }

    /* Disable MIPI CSI */
    mipi_csi_disable();

    ctx->streaming = false;
    sensor->state = MPIX_SENSOR_STATE_INITIALIZED;

    return 0;
}

static int imx219_get_frame(struct mpix_sensor *sensor, struct mpix_image *image,
                            uint32_t timeout_ms)
{
    struct imx219_hw_ctx *ctx = (struct imx219_hw_ctx *)sensor->hw_ctx;
    (void)timeout_ms; /* Currently unused */
    if (!sensor || !image || !ctx)
    {
        return -EINVAL;
    }

    if (!ctx->streaming)
    {
        return -EAGAIN;
    }

    /* Wait for frame ready */
    while (!datapath_is_frame_ready())
    {
        /* Wait */
        sccb_delay_ms(1);
    }

    image->width = ctx->current_format.width;
    image->height = ctx->current_format.height;
    image->fourcc = ctx->current_format.fourcc;
    image->buffer = (uint8_t *)datapath_acquire_raw_buffer();
    image->size = image->width * image->height;

    return 0;
}

static int imx219_release_frame(struct mpix_sensor *sensor, const struct mpix_image *image)
{
    if (!sensor || !image)
    {
        return -EINVAL;
    }

    datapath_release_raw_buffer();

    return 0;
}

static void imx219_deinit(struct mpix_sensor *sensor)
{
    struct imx219_hw_ctx *ctx = (struct imx219_hw_ctx *)sensor->hw_ctx;

    if (!sensor || !ctx)
    {
        return;
    }

    /* Stop streaming if active */
    if (ctx->streaming)
    {
        imx219_stop_stream(sensor);
    }

    ctx->initialized = false;
    sensor->state = MPIX_SENSOR_STATE_IDLE;
}

/* Sensor operations structure */
static const struct mpix_sensor_ops imx219_ops = {
    .init = imx219_init,
    .probe = imx219_probe,
    .get_capabilities = imx219_get_capabilities,
    .get_format = imx219_get_format,
    .set_format = imx219_set_format,
    .set_ctrl = imx219_set_ctrl,
    .get_ctrl = imx219_get_ctrl,
    .start_stream = imx219_start_stream,
    .stop_stream = imx219_stop_stream,
    .get_frame = imx219_get_frame,
    .release_frame = imx219_release_frame,
    .deinit = imx219_deinit,
};

/* Sensor instance */
static struct mpix_sensor imx219_sensor = {
    .name = "imx219",
    .ops = &imx219_ops,
    .hw_ctx = &g_imx219_hw_ctx,
    .state = MPIX_SENSOR_STATE_IDLE,
};

/* Public API implementation */
struct mpix_sensor *imx219_get_sensor(void)
{
    return &imx219_sensor;
}

int imx219_hw_ctx_init(struct imx219_hw_ctx *hw_ctx)
{
    if (!hw_ctx)
    {
        return -EINVAL;
    }

    memset(hw_ctx, 0, sizeof(*hw_ctx));

    return 0;
}
