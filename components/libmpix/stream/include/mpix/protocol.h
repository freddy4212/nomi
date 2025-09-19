/**
 * SPDX-License-Identifier: Apache-2.0
 * @defgroup mpix_protocol_h stream/mpix_protocol.h
 * @brief MPIX Camera Streaming Protocol
 * @{
 */
#ifndef MPIX_PROTOCOL_H
#define MPIX_PROTOCOL_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#include <mpix/sensor.h>
#include <mpix/transport.h>
#include <mpix/image.h>
#include <mpix/op_correction.h>
#include <mpix/auto.h>

/* Protocol constants */
#define MPIX_PROTOCOL_MAGIC_START 0xAA55BB66
#define MPIX_PROTOCOL_MAGIC_END   0x66BB55AA
#define MPIX_PROTOCOL_VERSION     0x01
#define MPIX_PROTOCOL_MAX_PAYLOAD 4096

/* Command types */
enum mpix_protocol_cmd_type {
    /* Sensor control commands */
    MPIX_CMD_SENSOR_GET_CAPS      = 0x10,  /* Get sensor capabilities */
    MPIX_CMD_SENSOR_GET_FORMAT    = 0x11,  /* Get current format */
    MPIX_CMD_SENSOR_SET_FORMAT    = 0x12,  /* Set format */
    MPIX_CMD_SENSOR_GET_CTRL      = 0x13,  /* Get control value */
    MPIX_CMD_SENSOR_SET_CTRL      = 0x14,  /* Set control value */
    
    /* ISP control commands */
    MPIX_CMD_ISP_GET_WHITE_BALANCE = 0x20,  /* Get white balance settings */
    MPIX_CMD_ISP_SET_WHITE_BALANCE = 0x21,  /* Set white balance settings */
    MPIX_CMD_ISP_GET_BLACK_LEVEL   = 0x22,  /* Get black level correction */
    MPIX_CMD_ISP_SET_BLACK_LEVEL   = 0x23,  /* Set black level correction */
    MPIX_CMD_ISP_GET_GAMMA         = 0x24,  /* Get gamma correction */
    MPIX_CMD_ISP_SET_GAMMA         = 0x25,  /* Set gamma correction */
    MPIX_CMD_ISP_GET_COLOR_MATRIX  = 0x26,  /* Get color matrix */
    MPIX_CMD_ISP_SET_COLOR_MATRIX  = 0x27,  /* Set color matrix */
    MPIX_CMD_ISP_GET_JPEG_QUALITY  = 0x28,  /* Get JPEG quality */
    MPIX_CMD_ISP_SET_JPEG_QUALITY  = 0x29,  /* Set JPEG quality */
    MPIX_CMD_ISP_ENABLE_CORRECTION = 0x2A,  /* Enable ISP correction */
    MPIX_CMD_ISP_DISABLE_CORRECTION= 0x2B,  /* Disable ISP correction */
    MPIX_CMD_ISP_GET_CORRECTION_STATE=0x2C, /* Get ISP correction state */
    
    /* Auto algorithms control */
    MPIX_CMD_AUTO_GET_TARGET       = 0x30,  /* Get AE target */
    MPIX_CMD_AUTO_SET_TARGET       = 0x31,  /* Set AE target */
    MPIX_CMD_AUTO_GET_STATE        = 0x32,  /* Get auto algorithm state */
    MPIX_CMD_AUTO_ENABLE_AE        = 0x33,  /* Enable auto exposure */
    MPIX_CMD_AUTO_DISABLE_AE       = 0x34,  /* Disable auto exposure */
    MPIX_CMD_AUTO_ENABLE_AWB       = 0x35,  /* Enable auto white balance */
    MPIX_CMD_AUTO_DISABLE_AWB      = 0x36,  /* Disable auto white balance */
    MPIX_CMD_AUTO_ENABLE_ABLC      = 0x37,  /* Enable auto black level correction */
    MPIX_CMD_AUTO_DISABLE_ABLC     = 0x38,  /* Disable auto black level correction */
    MPIX_CMD_AUTO_ENABLE_ALL       = 0x39,  /* Enable all auto algorithms */
    MPIX_CMD_AUTO_DISABLE_ALL      = 0x3A,  /* Disable all auto algorithms */
    
    /* Streaming control commands */
    MPIX_CMD_STREAM_START          = 0x40,  /* Start streaming */
    MPIX_CMD_STREAM_STOP           = 0x41,  /* Stop streaming */
    MPIX_CMD_STREAM_GET_STATUS     = 0x42,  /* Get streaming status */
    MPIX_CMD_STREAM_SET_MODE       = 0x43,  /* Set stream mode (raw/processed/jpeg) */
    
    /* System commands */
    MPIX_CMD_SYSTEM_PING           = 0x50,  /* Ping command */
    MPIX_CMD_SYSTEM_GET_VERSION    = 0x51,  /* Get firmware version */
    MPIX_CMD_SYSTEM_RESET          = 0x52,  /* Reset system */
};

/* Response status codes */
enum mpix_protocol_status {
    MPIX_STATUS_OK                 = 0x00,  /* Success */
    MPIX_STATUS_ERROR              = 0x01,  /* Generic error */
    MPIX_STATUS_INVALID_CMD        = 0x02,  /* Invalid command */
    MPIX_STATUS_INVALID_PARAM      = 0x03,  /* Invalid parameter */
    MPIX_STATUS_NOT_SUPPORTED      = 0x04,  /* Command not supported */
    MPIX_STATUS_DEVICE_BUSY        = 0x05,  /* Device busy */
    MPIX_STATUS_TIMEOUT            = 0x06,  /* Operation timeout */
    MPIX_STATUS_BUFFER_FULL        = 0x07,  /* Buffer full */
    MPIX_STATUS_NOT_INITIALIZED    = 0x08,  /* Not initialized */
};

/* Stream modes */
enum mpix_protocol_stream_mode {
    MPIX_STREAM_MODE_RAW           = 0x00,  /* Raw sensor data */
    MPIX_STREAM_MODE_RGB           = 0x01,  /* Processed RGB data */
    MPIX_STREAM_MODE_JPEG          = 0x02,  /* JPEG compressed */
    MPIX_STREAM_MODE_QOI           = 0x03,  /* QOI compressed */
    MPIX_STREAM_MODE_AUTO          = 0x04,  /* Auto mode with ISP */
};

/* Protocol frame header */
struct mpix_protocol_header {
    uint32_t magic_start;        /* Start magic number */
    uint8_t  version;           /* Protocol version */
    uint8_t  cmd_type;          /* Command type */
    uint16_t sequence;          /* Sequence number */
    uint16_t payload_length;    /* Payload length */
    uint16_t checksum;          /* Header checksum */
} __attribute__((packed));

/* Protocol frame footer */
struct mpix_protocol_footer {
    uint32_t magic_end;         /* End magic number */
} __attribute__((packed));

/* Sensor capabilities response */
struct mpix_protocol_sensor_caps {
    uint32_t fourcc;           /* Supported format */
    uint16_t max_width;        /* Maximum width */
    uint16_t max_height;       /* Maximum height */
    uint16_t min_width;        /* Minimum width */
    uint16_t min_height;       /* Minimum height */
    uint16_t max_fps;          /* Maximum frame rate */
} __attribute__((packed));

/* Sensor format structure */
struct mpix_protocol_sensor_format {
    uint32_t fourcc;           /* Image format */
    uint16_t width;            /* Image width */
    uint16_t height;           /* Image height */
    uint16_t fps;              /* Frame rate */
} __attribute__((packed));

/* Sensor control structure */
struct mpix_protocol_sensor_ctrl {
    uint32_t cid;              /* Control ID (V4L2 style) */
    int32_t  value;            /* Control value */
} __attribute__((packed));

/* ISP white balance structure */
struct mpix_protocol_white_balance {
    uint16_t red_level;        /* Red channel gain */
    uint16_t blue_level;       /* Blue channel gain */
} __attribute__((packed));

/* ISP black level structure */
struct mpix_protocol_black_level {
    uint8_t level;             /* Black level offset */
} __attribute__((packed));

/* ISP gamma structure */
struct mpix_protocol_gamma {
    uint16_t level;            /* Gamma level */
} __attribute__((packed));

/* ISP color matrix structure */
struct mpix_protocol_color_matrix {
    int16_t levels[9];         /* 3x3 color matrix */
} __attribute__((packed));

/* JPEG quality structure */
struct mpix_protocol_jpeg_quality {
    uint8_t quality;           /* JPEG quality level */
} __attribute__((packed));

/* ISP correction state structure */
struct mpix_protocol_isp_correction_state {
    uint8_t black_level_enabled;    /* Black level correction enabled */
    uint8_t gamma_enabled;          /* Gamma correction enabled */
    uint8_t white_balance_enabled;  /* White balance correction enabled */
    uint8_t color_matrix_enabled;   /* Color matrix correction enabled */
    uint8_t denoise_enabled;        /* Denoise filter enabled */
} __attribute__((packed));

/* ISP correction control structure */
struct mpix_protocol_isp_correction_control {
    uint8_t correction_type;        /* Correction type (bitmask) */
    uint8_t enable;                 /* Enable/disable flag */
} __attribute__((packed));

/* Auto algorithm target structure */
struct mpix_protocol_auto_target {
    uint8_t ae_target;         /* Auto exposure target */
} __attribute__((packed));

/* Auto algorithm state structure */
struct mpix_protocol_auto_state {
    uint8_t ae_enabled;        /* Auto exposure enabled */
    uint8_t awb_enabled;       /* Auto white balance enabled */
    uint8_t ablc_enabled;      /* Auto black level enabled */
    uint8_t reserved;          /* Reserved for alignment */
    int32_t exposure_level;    /* Current exposure level */
    uint16_t wb_red_level;     /* Current WB red level */
    uint16_t wb_blue_level;    /* Current WB blue level */
    uint8_t black_level;       /* Current black level */
    uint8_t padding[3];        /* Padding for alignment */
} __attribute__((packed));

/* Stream status structure */
struct mpix_protocol_stream_status {
    uint8_t  is_streaming;     /* Streaming active */
    uint8_t  stream_mode;      /* Current stream mode */
    uint32_t frame_count;      /* Total frames sent */
    uint32_t error_count;      /* Error count */
} __attribute__((packed));

/* Stream mode structure */
struct mpix_protocol_stream_mode_config {
    uint8_t mode;              /* Stream mode */
    uint8_t enable_auto;       /* Enable auto algorithms */
} __attribute__((packed));

/* Image frame header for streaming */
struct mpix_protocol_frame_header {
    uint32_t magic_start;      /* Frame start magic */
    uint32_t frame_id;         /* Frame sequence */
    uint16_t width;            /* Image width */
    uint16_t height;           /* Image height */
    uint32_t data_size;        /* Image data size */
    uint32_t fourcc;           /* Image format */
    uint16_t checksum;         /* Data checksum */
    uint16_t reserved;         /* Reserved */
} __attribute__((packed));

/* Image frame footer for streaming */
struct mpix_protocol_frame_footer {
    uint32_t magic_end;        /* Frame end magic */
} __attribute__((packed));

/* System version info */
struct mpix_protocol_version {
    uint8_t major;             /* Major version */
    uint8_t minor;             /* Minor version */
    uint8_t patch;             /* Patch version */
    uint8_t reserved;          /* Reserved */
    char    build_info[32];    /* Build information */
} __attribute__((packed));

/* Protocol context structure */
struct mpix_protocol_context {
    /* Hardware components */
    struct mpix_sensor *sensor;
    struct mpix_transport *transport;
    
    /* State */
    bool streaming;
    enum mpix_protocol_stream_mode stream_mode;
    uint32_t frame_counter;
    uint32_t error_counter;
    uint16_t sequence_counter;
    
    /* Auto algorithms */
    struct mpix_auto_ctrls auto_ctrls;
    bool ae_enabled;           /* Auto exposure enabled */
    bool awb_enabled;          /* Auto white balance enabled */
    bool ablc_enabled;         /* Auto black level correction enabled */
    
    /* ISP correction controls */
    bool black_level_correction_enabled;   /* Black level correction enabled */
    bool gamma_correction_enabled;         /* Gamma correction enabled */
    bool white_balance_correction_enabled; /* White balance correction enabled */
    bool color_matrix_correction_enabled;  /* Color matrix correction enabled */
    bool denoise_filter_enabled;           /* Denoise filter enabled */
    
    /* JPEG settings */
    uint8_t jpeg_quality;                   /* JPEG quality level (1-100) */
    
    /* Buffers */
    uint8_t *rx_buffer;
    size_t rx_buffer_size;
    
    /* Statistics */
    struct mpix_stats stats;
};

/* Function prototypes */

/**
 * @brief Initialize protocol context
 * 
 * @param ctx Protocol context
 * @param sensor Sensor instance
 * @param transport Transport instance
 * @return 0 on success, negative error code on failure
 */
int mpix_protocol_init(struct mpix_protocol_context *ctx,
                      struct mpix_sensor *sensor,
                      struct mpix_transport *transport);

/**
 * @brief Deinitialize protocol context
 * 
 * @param ctx Protocol context
 */
void mpix_protocol_deinit(struct mpix_protocol_context *ctx);

/**
 * @brief Process incoming protocol messages
 * 
 * @param ctx Protocol context
 * @return 0 on success, negative error code on failure
 */
int mpix_protocol_process(struct mpix_protocol_context *ctx);

/**
 * @brief Start streaming
 * 
 * @param ctx Protocol context
 * @return 0 on success, negative error code on failure
 */
int mpix_protocol_start_streaming(struct mpix_protocol_context *ctx);

/**
 * @brief Stop streaming
 * 
 * @param ctx Protocol context
 * @return 0 on success, negative error code on failure
 */
int mpix_protocol_stop_streaming(struct mpix_protocol_context *ctx);

/**
 * @brief Send a frame over the transport
 * 
 * @param ctx Protocol context
 * @param image Image to send
 * @return 0 on success, negative error code on failure
 */
int mpix_protocol_send_frame(struct mpix_protocol_context *ctx,
                            const struct mpix_image *image);

/**
 * @brief Calculate checksum for data
 * 
 * @param data Data buffer
 * @param size Data size
 * @return Checksum value
 */
uint16_t mpix_protocol_checksum(const uint8_t *data, size_t size);

/**
 * @brief Send response
 * 
 * @param ctx Protocol context
 * @param cmd_type Original command type
 * @param status Response status
 * @param payload Response payload
 * @param payload_size Payload size
 * @return 0 on success, negative error code on failure
 */
int mpix_protocol_send_response(struct mpix_protocol_context *ctx,
                               uint8_t cmd_type,
                               enum mpix_protocol_status status,
                               const void *payload,
                               size_t payload_size);

#endif /* MPIX_PROTOCOL_H */
/** @} */
