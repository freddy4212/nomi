/**
 * SPDX-License-Identifier: Apache-2.0
 * @file ov5647.c
 * @brief OV5647 camera sensor driver implementation
 */

#include <errno.h>
#include <string.h>
#include <ctype.h>

#include <mpix/sensor/sccb.h>
#include <mpix/sensor/ov5647.h>

/* OV5647 register definitions */
#define OV5647_CHIP_ID_H_REG 0x300A /* Chip ID high byte */
#define OV5647_CHIP_ID_L_REG 0x300B /* Chip ID low byte */
#define OV5647_CHIP_ID 0x5647       /* Expected chip ID */
#define OV5647_SW_RESET_REG 0x0103
#define OV5647_MODE_SELECT_REG 0x0100
#define OV5647_TIMING_HTS_REG 0x380C
#define OV5647_TIMING_VTS_REG 0x380E

/* OV5647 mode register values */
#define OV5647_MODE_STANDBY 0x00
#define OV5647_MODE_STREAMING 0x01

/* Approximate maximum coarse exposure lines (example value; adjust if precise timing known) */
#define OV5647_EXPOSURE_MAX 0xFFFF

/* OV5647 MIPI control values */
#define OV5647_MIPI_CTRL_OFF 0x01 /* MIPI OFF */
#define OV5647_MIPI_CTRL_ON 0x14  /* MIPI ON */

/* Stream control registers */
#define OV5647_STREAM_MIPI_REG 0x4800
#define OV5647_STREAM_CTRL_REG 0x4202

/* Resolution configuration tables */
struct ov5647_reg
{
    uint16_t addr;
    uint8_t value;
};

/* VGA 640x480 30fps configuration - based on reference driver */
static const struct ov5647_reg ov5647_640x480_regs[] = {
    {0x3000, 0x0f},
    {0x3001, 0xff},
    {0x3002, 0xe4},
    /* Software reset */
    {0x0100, 0x00},
    {0x0103, 0x01},
    /* Clock settings */
    {0x3035, 0x11},
    {0x3036, 0x46},
    {0x303c, 0x11},
    /* Flip and mirror */
    {0x3821, 0x07},
    {0x3820, 0x41},
    /* Sensor settings */
    {0x370c, 0x03},
    {0x3612, 0x59},
    {0x3618, 0x00},
    {0x5000, 0x06},
    {0x5003, 0x08},
    {0x5a00, 0x08},
    /* Power settings */
    {0x3000, 0xff},
    {0x3001, 0xff},
    {0x3002, 0xff},
    {0x301d, 0xf0},
    /* AEC settings */
    {0x3a18, 0x00},
    {0x3a19, 0xf8},
    {0x3c01, 0x80},
    {0x3b07, 0x0c},
    /* Timing settings */
    {0x380c, 0x07},
    {0x380d, 0x3c},
    {0x3814, 0x35},
    {0x3815, 0x35},
    /* Additional sensor settings */
    {0x3708, 0x64},
    {0x3709, 0x52},
    /* Output size */
    {0x3808, 0x02}, /* Width high */
    {0x3809, 0x80}, /* Width low (640) */
    {0x380a, 0x01}, /* Height high */
    {0x380b, 0xe0}, /* Height low (480) */
    /* Crop settings */
    {0x3800, 0x00}, /* X start high */
    {0x3801, 0x10}, /* X start low */
    {0x3802, 0x00}, /* Y start high */
    {0x3803, 0x00}, /* Y start low */
    {0x3804, 0x0a}, /* X end high */
    {0x3805, 0x2f}, /* X end low */
    {0x3806, 0x07}, /* Y end high */
    {0x3807, 0x9f}, /* Y end low */
    /* Additional settings */
    {0x3630, 0x2e},
    {0x3632, 0xe2},
    {0x3633, 0x23},
    {0x3634, 0x44},
    {0x3620, 0x64},
    {0x3621, 0xe0},
    {0x3600, 0x37},
    {0x3704, 0xa0},
    {0x3703, 0x5a},
    {0x3715, 0x78},
    {0x3717, 0x01},
    {0x3731, 0x02},
    {0x370b, 0x60},
    {0x3705, 0x1a},
    {0x3f05, 0x02},
    {0x3f06, 0x10},
    {0x3f01, 0x0a},
    /* AEC/AGC settings */
    {0x3a08, 0x01},
    {0x3a09, 0x2e},
    {0x3a0a, 0x00},
    {0x3a0b, 0xfb},
    {0x3a0d, 0x02},
    {0x3a0e, 0x01},
    {0x3a0f, 0x58},
    {0x3a10, 0x50},
    {0x3a1b, 0x58},
    {0x3a1e, 0x50},
    {0x3a11, 0x60},
    {0x3a1f, 0x28},
    /* BLC settings */
    {0x4001, 0x02},
    {0x4004, 0x02},
    {0x4000, 0x09},
    /* Final power settings */
    {0x3000, 0x00},
    {0x3001, 0x00},
    {0x3002, 0x00},
    {0x3017, 0xe0},
    {0x301c, 0xfc},
    {0x3636, 0x06},
    {0x3016, 0x08},
    {0x3827, 0xec},
    {0x3018, 0x44},
    {0x3035, 0x21},
    {0x3106, 0xf5},
    {0x3034, 0x1a},
    {0x301c, 0xf8},
    /* MIPI settings */
    {0x4800, 0x34},
    {0x3503, 0x00},
    {0x4800, OV5647_MIPI_CTRL_OFF},
    {0x0100, 0x01},
    {0x4202, 0x0F},
    {0xFFFF, 0xFF} /* End marker */
};

/* 1280x960 configuration - based on reference driver */
static const struct ov5647_reg ov5647_1280x960_regs[] = {
    {0x3000, 0x0f},
    {0x3001, 0xff},
    {0x3002, 0xe4},
    /* Software reset */
    {0x0100, 0x00},
    {0x0103, 0x01},
    /* PLL settings */
    {0x3034, 0x1a},
    {0x3035, 0x21},
    {0x3036, 0x62},
    {0x303c, 0x11},
    {0x3106, 0xf5},
    {0x3827, 0xec},
    /* Sensor settings */
    {0x370c, 0x03},
    {0x3612, 0x59},
    {0x3618, 0x00},
    {0x5000, 0x89},
    {0x5002, 0x41},
    {0x5003, 0x08},
    {0x5a00, 0x08},
    /* Power settings */
    {0x3000, 0x00},
    {0x3001, 0x00},
    {0x3002, 0x00},
    {0x3016, 0x08},
    {0x3017, 0xe0},
    {0x3018, 0x44},
    {0x301c, 0xf8},
    {0x301d, 0xf0},
    /* AEC settings */
    {0x3a18, 0x00},
    {0x3a19, 0xf8},
    {0x3c01, 0x80},
    {0x3b07, 0x0c},
    /* Crop settings */
    {0x3800, 0x00}, /* X start high */
    {0x3801, 0x18}, /* X start low */
    {0x3802, 0x00}, /* Y start high */
    {0x3803, 0x0c}, /* Y start low */
    {0x3804, 0x0a}, /* X end high */
    {0x3805, 0x27}, /* X end low */
    {0x3806, 0x07}, /* Y end high */
    {0x3807, 0x97}, /* Y end low */
    /* Output size */
    {0x3808, 0x05}, /* Width high */
    {0x3809, 0x00}, /* Width low (1280) */
    {0x380a, 0x03}, /* Height high */
    {0x380b, 0xc0}, /* Height low (960) */
    /* Timing settings */
    {0x380c, 0x0a}, /* HTS high */
    {0x380d, 0x8c}, /* HTS low */
    {0x3811, 0x04},
    {0x3813, 0x02},
    {0x3814, 0x31},
    {0x3815, 0x31},
    /* Additional sensor settings */
    {0x3630, 0x2e},
    {0x3632, 0xe2},
    {0x3633, 0x23},
    {0x3634, 0x44},
    {0x3636, 0x06},
    {0x3620, 0x64},
    {0x3621, 0xe0},
    {0x3600, 0x37},
    {0x3704, 0xa0},
    {0x3703, 0x5a},
    {0x3715, 0x78},
    {0x3717, 0x01},
    {0x3731, 0x02},
    {0x370b, 0x60},
    {0x3705, 0x1a},
    {0x3f05, 0x02},
    {0x3f06, 0x10},
    {0x3f01, 0x0a},
    /* AEC/AGC settings */
    {0x3a08, 0x01},
    {0x3a09, 0x28},
    {0x3a0a, 0x00},
    {0x3a0b, 0xf6},
    {0x3a0d, 0x08},
    {0x3a0e, 0x06},
    /* AWB settings */
    {0x5180, 0x40},
    /* LENC settings */
    {0x583E, 0xFF},
    {0x583F, 0x80},
    /* AEC/AGC Area */
    {0x3a0f, 0x32},
    {0x3a10, 0x24},
    {0x3a1b, 0x32},
    {0x3a1e, 0x24},
    /* Weight settings */
    {0x5680, 0x00},
    {0x5681, 0x00},
    {0x5682, 0x00},
    {0x5683, 0x00},
    {0x568A, 0x21},
    {0x588B, 0x12},
    {0x588C, 0x21},
    {0x588D, 0x12},
    /* LENC gain table - abbreviated for space */
    {0x5800, 0x20},
    {0x5801, 0x20},
    {0x5802, 0x20},
    {0x5803, 0x20},
    {0x5804, 0x20},
    {0x5805, 0x20},
    {0x5806, 0x20},
    {0x5807, 0x10},
    {0x5808, 0x10},
    {0x5809, 0x10},
    {0x580a, 0x10},
    {0x580b, 0x20},
    {0x580c, 0x12},
    {0x580d, 0x0A},
    {0x580e, 0x00},
    {0x580f, 0x00},
    {0x5810, 0x0A},
    {0x5811, 0x12},
    {0x5812, 0x16},
    {0x5813, 0x0C},
    {0x5814, 0x00},
    {0x5815, 0x00},
    {0x5816, 0x0A},
    {0x5817, 0x16},
    {0x5818, 0x18},
    {0x5819, 0x0C},
    {0x581a, 0x0C},
    {0x581b, 0x18},
    {0x581c, 0x18},
    {0x581d, 0x18},
    {0x581e, 0x20},
    {0x581f, 0x20},
    {0x5820, 0x10},
    {0x5821, 0x20},
    {0x5822, 0x20},
    {0x5823, 0x20},
    /* Final settings */
    {0x3a11, 0x60},
    {0x3a1f, 0x28},
    {0x4001, 0x02},
    {0x4004, 0x04},
    {0x4000, 0x09},
    {0x4837, 0x16},
    {0x4800, 0x24},
    {0x3503, 0x00},
    /* Flip settings */
    {0x3820, 0x41},
    {0x3821, 0x00},
    /* Exposure and gain */
    {0x350a, 0x00},
    {0x350b, 0x10},
    {0x3500, 0x00},
    {0x3501, 0x1a},
    {0x3502, 0xf0},
    {0x3212, 0xa0},
    /* MIPI control */
    {0x4800, OV5647_MIPI_CTRL_OFF},
    {0x4202, 0x0F},
    {0x0100, 0x01},
    {0xFFFF, 0xFF} /* End marker */
};
/* Mode configuration table */
static const struct
{
    const struct ov5647_reg *regs;
    uint16_t width;
    uint16_t height;
    uint16_t fps;
    uint32_t fourcc;
} ov5647_modes[OV5647_MODE_MAX] = {
    [OV5647_MODE_640x480_30FPS] = {
        .regs = ov5647_640x480_regs,
        .width = 640,
        .height = 480,
        .fps = 15,
        .fourcc = MPIX_FMT_SBGGR8,
    },
    [OV5647_MODE_1280x960_30FPS] = {
        .regs = ov5647_1280x960_regs,
        .width = 1280,
        .height = 960,
        .fps = 15,
        .fourcc = MPIX_FMT_SBGGR8,
    },
};

/* Global hardware context */
static struct ov5647_hw_ctx g_ov5647_hw_ctx;

/* Helper functions */
static int ov5647_write_reg(uint8_t addr, uint16_t reg, uint8_t value)
{
    return sccb_write_reg(addr, reg, value);
}

static int ov5647_read_reg(uint8_t addr, uint16_t reg, uint8_t *value)
{
    return sccb_read_reg(addr, reg, value);
}

static int ov5647_write_regs(uint8_t addr, const struct ov5647_reg *regs)
{
    int ret;

    for (int i = 0; regs[i].addr != 0xFFFF; i++)
    {
        ret = ov5647_write_reg(addr, regs[i].addr, regs[i].value);
        if (ret < 0)
        {
            return ret;
        }

        /* Add delay after reset */
        if (regs[i].addr == OV5647_SW_RESET_REG)
        {
            sccb_delay_ms(10);
        }
    }

    return 0;
}

static ov5647_mode_t ov5647_find_mode(uint16_t width, uint16_t height)
{
    int best = -1;
    uint32_t best_score = UINT32_MAX;
    for (int i = 0; i < OV5647_MODE_MAX; i++)
    {
        uint32_t dw = (ov5647_modes[i].width > width) ? (ov5647_modes[i].width - width) : (width - ov5647_modes[i].width);
        uint32_t dh = (ov5647_modes[i].height > height) ? (ov5647_modes[i].height - height) : (height - ov5647_modes[i].height);
        uint32_t score = (dw << 16) | dh; /* width diff priority */
        if (score < best_score)
        {
            best_score = score;
            best = i;
            if (dw == 0 && dh == 0)
                break;
        }
    }
    return best >= 0 ? (ov5647_mode_t)best : OV5647_MODE_MAX;
}

/* Orientation + Bayer mapping (native BGGR) similar to IMX219 */
static uint32_t ov5647_bayer_from_orientation(bool h, bool v)
{
    if (!h && !v)
        return MPIX_FMT_SRGGB8; /* RGGB*/
    if (h && !v)
        return MPIX_FMT_SGRBG8; /* GRBG*/
    if (!h && v)
        return MPIX_FMT_SGBRG8; /* GBRG */
    return MPIX_FMT_SBGGR8;     /* BGGR */
}

static void ov5647_apply_orientation(struct ov5647_hw_ctx *ctx)
{
    /* OV5647 uses 0x3820 (V) and 0x3821 (H) bits for mirror/flip.
     * Typical: bit2 of 0x3821 = H mirror, bit2 of 0x3820 = V flip, plus fixed pattern bits.
     * Current hard-coded init used 0x3821=0x07, 0x3820=0x41 (varies by script). We'll preserve upper bits and toggle bit2.
     */
    uint8_t vreg, hreg;
    if (ov5647_read_reg(ctx->i2c_addr, 0x3820, &vreg) < 0)
        return;
    if (ov5647_read_reg(ctx->i2c_addr, 0x3821, &hreg) < 0)
        return;
    if (ctx->v_flip)
        vreg |= (1u << 2);
    else
        vreg &= ~(1u << 2);
    if (ctx->h_mirror)
        hreg |= (1u << 2);
    else
        hreg &= ~(1u << 2);
    ov5647_write_reg(ctx->i2c_addr, 0x3820, vreg);
    ov5647_write_reg(ctx->i2c_addr, 0x3821, hreg);
    ctx->current_format.fourcc = ov5647_bayer_from_orientation(ctx->h_mirror, ctx->v_flip);
}

static void ov5647_apply_test_pattern(struct ov5647_hw_ctx *ctx)
{
    /* OV5647 test pattern register 0x503D:
     * 0x00: disable
     * 0x80: color bar
     * 0x81: color bar (alternate) – treat as 2
     */
    uint8_t val;
    switch (ctx->test_pattern)
    {
    case 0:
        val = 0x00;
        break;
    case 1:
        val = 0x80;
        break;
    case 2:
        val = 0x81;
        break;
    default:
        val = 0x00;
        ctx->test_pattern = 0;
        break;
    }
    ov5647_write_reg(ctx->i2c_addr, 0x503D, val);
}

/* Sensor operations implementation */
static int ov5647_init(const struct mpix_sensor *sensor)
{
    struct ov5647_hw_ctx *ctx = (struct ov5647_hw_ctx *)sensor->hw_ctx;

    if (!ctx)
    {
        return -EINVAL;
    }

    if (ctx->initialized)
    {
        return 0;
    }

    /* Initialize hardware context */
    ctx->i2c_addr = OV5647_I2C_ADDR;
    ctx->streaming = false;
    ctx->current_mode = OV5647_MODE_640x480_30FPS;

    /* Initialize controls to default values */
    ctx->h_mirror = false;
    ctx->v_flip = false;
    ctx->exposure = 1;      /* auto exposure enabled */
    ctx->white_balance = 1; /* auto white balance enabled */
    ctx->test_pattern = 0;

    /* Default orientation: enable both flips for consistency with IMX219 request (0x03 style)
     * If you want both enabled by default, set flags and apply.
     */
    ctx->h_mirror = true;
    ctx->v_flip = true;
    ctx->current_format.fourcc = ov5647_bayer_from_orientation(ctx->h_mirror, ctx->v_flip);
    ov5647_apply_orientation(ctx);
    ctx->initialized = true;

    return 0;
}

static int ov5647_probe(const struct mpix_sensor *sensor)
{
    struct ov5647_hw_ctx *ctx = (struct ov5647_hw_ctx *)sensor->hw_ctx;
    uint8_t chip_id_h, chip_id_l;
    uint16_t chip_id;
    int ret;

    if (!ctx)
    {
        return -EINVAL;
    }

    /* Read chip ID - OV5647 uses 0x300A (high) and 0x300B (low) */
    ret = ov5647_read_reg(ctx->i2c_addr, OV5647_CHIP_ID_H_REG, &chip_id_h);
    if (ret < 0)
    {
        return ret;
    }

    ret = ov5647_read_reg(ctx->i2c_addr, OV5647_CHIP_ID_L_REG, &chip_id_l);
    if (ret < 0)
    {
        return ret;
    }

    chip_id = (chip_id_h << 8) | chip_id_l;

    if (chip_id != OV5647_CHIP_ID)
    {
        return -ENODEV;
    }

    return 0;
}

static int ov5647_get_capabilities(const struct mpix_sensor *sensor,
                                   struct mpix_sensor_caps *caps)
{
    if (!sensor || !caps)
    {
        return -EINVAL;
    }

    caps->fourcc = MPIX_FMT_SBGGR8;
    caps->max_width = 2592;
    caps->max_height = 1944;
    caps->min_width = 640;
    caps->min_height = 480;
    caps->max_fps = 30;

    return 0;
}

static int ov5647_get_format(const struct mpix_sensor *sensor,
                             struct mpix_sensor_format *format)
{
    struct ov5647_hw_ctx *ctx = (struct ov5647_hw_ctx *)sensor->hw_ctx;

    if (!sensor || !format || !ctx)
    {
        return -EINVAL;
    }

    *format = ctx->current_format;

    return 0;
}

static int ov5647_set_format(const struct mpix_sensor *sensor,
                             const struct mpix_sensor_format *format)
{
    struct ov5647_hw_ctx *ctx = (struct ov5647_hw_ctx *)sensor->hw_ctx;
    ov5647_mode_t mode;
    int ret;

    if (!sensor || !format || !ctx)
    {
        return -EINVAL;
    }

    /* Find matching mode */
    mode = ov5647_find_mode(format->width, format->height);
    if (mode >= OV5647_MODE_MAX)
    {
        return -ENOTSUP;
    }

    /* Stop streaming if active */
    if (ctx->streaming)
    {
        ret = ov5647_write_reg(ctx->i2c_addr, OV5647_MODE_SELECT_REG, OV5647_MODE_STANDBY);
        if (ret < 0)
        {
            return ret;
        }
        ctx->streaming = false;
    }

    MPIX_INF("Setting OV5647 mode: %dx%d @ %dfps\n",
             ov5647_modes[mode].width,
             ov5647_modes[mode].height,
             ov5647_modes[mode].fps);

    /* Apply mode configuration */
    ret = ov5647_write_regs(ctx->i2c_addr, ov5647_modes[mode].regs);
    if (ret < 0)
    {
        return ret;
    }

    /* Update context */
    ctx->current_mode = mode;
    ctx->current_format = *format;
    /* Re-apply orientation to keep fourcc in sync */
    ov5647_apply_orientation(ctx);

    const mipi_csi_config_t csi_config = {
        .clock_freq_mhz = 350,
        .lane_count = MIPI_CSI_LANE_2,
        .pixel_depth = MIPI_CSI_PIXEL_DEPTH_10,
        .clock_mode = MIPI_CSI_CLK_MODE_CONTINUOUS,
        .deskew_enable = false};

    mipi_csi_configure(&csi_config);

    mipi_csi_enable();

    const datapath_config_t dp_config = {
        .width = format->width,
        .height = format->height,
        .pixel_depth = 10, /* 10-bit input from MIPI CSI */
        .enable_crop = false,
    };

    datapath_configure(&dp_config);

    return 0;
}

static int ov5647_set_ctrl(const struct mpix_sensor *sensor, uint32_t cid, const void *value)
{
    struct ov5647_hw_ctx *ctx = (struct ov5647_hw_ctx *)sensor->hw_ctx;
    int val;

    if (!sensor || !value || !ctx)
    {
        return -EINVAL;
    }

    val = *(const int *)value;

    switch (cid)
    {

    case V4L2_CID_HFLIP:
        ctx->h_mirror = (val != 0);
        ov5647_apply_orientation(ctx);
        break;

    case V4L2_CID_VFLIP:
        ctx->v_flip = (val != 0);
        ov5647_apply_orientation(ctx);
        break;

    case V4L2_CID_EXPOSURE_ABSOLUTE:
        ctx->exposure = val;
        /* TODO: Apply exposure register settings */
        break;

    case V4L2_CID_AUTO_WHITE_BALANCE:
        ctx->white_balance = val;
        /* TODO: Apply white balance register settings */
        break;

    case V4L2_CID_TEST_PATTERN:
        ctx->test_pattern = val;
        ov5647_apply_test_pattern(ctx);
        break;

    default:
        return -EINVAL;
    }

    return 0;
}

static int ov5647_get_ctrl(const struct mpix_sensor *sensor, uint32_t cid, void *value)
{
    struct ov5647_hw_ctx *ctx = (struct ov5647_hw_ctx *)sensor->hw_ctx;
    int *val = (int *)value;

    if (!sensor || !value || !ctx)
    {
        return -EINVAL;
    }

    switch (cid)
    {
    case V4L2_CID_HFLIP:
        *val = ctx->h_mirror ? 1 : 0;
        break;

    case V4L2_CID_VFLIP:
        *val = ctx->v_flip ? 1 : 0;
        break;

    case V4L2_CID_EXPOSURE_ABSOLUTE:
        *val = ctx->exposure;
        break;

    case V4L2_CID_AUTO_WHITE_BALANCE:
        *val = ctx->white_balance;
        break;

    case V4L2_CID_TEST_PATTERN:
        *val = ctx->test_pattern;
        break;
    case MPIX_CID_EXPOSURE_MAX:
        *val = OV5647_EXPOSURE_MAX;
        break;

    default:
        return -EINVAL;
    }

    return 0;
}

static int ov5647_start_stream(struct mpix_sensor *sensor)
{
    struct ov5647_hw_ctx *ctx = (struct ov5647_hw_ctx *)sensor->hw_ctx;
    int ret;

    if (!sensor || !ctx)
    {
        return -EINVAL;
    }

    if (ctx->streaming)
    {
        return 0; /* Already streaming */
    }

    /* Start streaming using proper sequence */
    /* First enable MIPI output */
    ret = ov5647_write_reg(ctx->i2c_addr, OV5647_STREAM_MIPI_REG, OV5647_MIPI_CTRL_ON);
    if (ret < 0)
    {
        return ret;
    }

    /* Then enable sensor output */
    ret = ov5647_write_reg(ctx->i2c_addr, OV5647_STREAM_CTRL_REG, 0x00);
    if (ret < 0)
    {
        return ret;
    }

    datapath_start();

    ctx->streaming = true;
    sensor->state = MPIX_SENSOR_STATE_STREAMING;

    return 0;
}

static int ov5647_stop_stream(struct mpix_sensor *sensor)
{
    struct ov5647_hw_ctx *ctx = (struct ov5647_hw_ctx *)sensor->hw_ctx;
    int ret;

    if (!sensor || !ctx)
    {
        return -EINVAL;
    }

    if (!ctx->streaming)
    {
        return 0; /* Already stopped */
    }

    datapath_stop();

    /* Stop streaming using proper sequence */
    /* First disable MIPI output */
    ret = ov5647_write_reg(ctx->i2c_addr, OV5647_STREAM_MIPI_REG, OV5647_MIPI_CTRL_OFF);
    if (ret < 0)
    {
        return ret;
    }

    /* Then disable sensor output */
    ret = ov5647_write_reg(ctx->i2c_addr, OV5647_STREAM_CTRL_REG, 0x0F);
    if (ret < 0)
    {
        return ret;
    }

    mipi_csi_disable();

    ctx->streaming = false;
    sensor->state = MPIX_SENSOR_STATE_INITIALIZED;

    return 0;
}

static int ov5647_get_frame(struct mpix_sensor *sensor, struct mpix_image *image,
                            uint32_t timeout_ms)
{
    struct ov5647_hw_ctx *ctx = (struct ov5647_hw_ctx *)sensor->hw_ctx;
    (void)timeout_ms; /* Currently unused */
    if (!sensor || !image || !ctx)
    {
        return -EINVAL;
    }

    if (!ctx->streaming)
    {
        return -EAGAIN;
    }

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

    /* For now, return not supported */
    return 0;
}

static int ov5647_release_frame(struct mpix_sensor *sensor, const struct mpix_image *image)
{
    if (!sensor || !image)
    {
        return -EINVAL;
    }

    datapath_release_raw_buffer();

    return 0;
}

static void ov5647_deinit(struct mpix_sensor *sensor)
{
    struct ov5647_hw_ctx *ctx = (struct ov5647_hw_ctx *)sensor->hw_ctx;

    if (!sensor || !ctx)
    {
        return;
    }

    /* Stop streaming if active */
    if (ctx->streaming)
    {
        ov5647_stop_stream(sensor);
    }

    ctx->initialized = false;
    sensor->state = MPIX_SENSOR_STATE_IDLE;
}

/* Sensor operations structure */
static const struct mpix_sensor_ops ov5647_ops = {
    .init = ov5647_init,
    .probe = ov5647_probe,
    .get_capabilities = ov5647_get_capabilities,
    .get_format = ov5647_get_format,
    .set_format = ov5647_set_format,
    .set_ctrl = ov5647_set_ctrl,
    .get_ctrl = ov5647_get_ctrl,
    .start_stream = ov5647_start_stream,
    .stop_stream = ov5647_stop_stream,
    .get_frame = ov5647_get_frame,
    .release_frame = ov5647_release_frame,
    .deinit = ov5647_deinit,
};

/* Sensor instance */
static struct mpix_sensor ov5647_sensor = {
    .name = "ov5647",
    .ops = &ov5647_ops,
    .hw_ctx = &g_ov5647_hw_ctx,
    .state = MPIX_SENSOR_STATE_IDLE,
};

/* Public API implementation */
struct mpix_sensor *ov5647_get_sensor(void)
{
    return &ov5647_sensor;
}

int ov5647_hw_ctx_init(struct ov5647_hw_ctx *hw_ctx)
{
    if (!hw_ctx)
    {
        return -EINVAL;
    }

    memset(hw_ctx, 0, sizeof(*hw_ctx));

    return 0;
}
