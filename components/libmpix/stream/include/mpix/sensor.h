/**
 * SPDX-License-Identifier: Apache-2.0
 * @defgroup mpix_sensor_h stream/mpix_sensor.h
 * @brief MPIX Sensor Hardware Abstraction Layer
 * @{
 */
#ifndef MPIX_SENSOR_H
#define MPIX_SENSOR_H

#include <errno.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#include <mpix/genlist.h>
#include <mpix/image.h>
#include <mpix/utils.h>

// Forward declarations
struct mpix_sensor;
struct mpix_sensor_format;
struct mpix_sensor_caps;

/* Canonical V4L2 CIDs (subset) */
#define V4L2_CID_BRIGHTNESS 0x00980900
#define V4L2_CID_CONTRAST 0x00980901
#define V4L2_CID_SATURATION 0x00980902
#define V4L2_CID_HUE 0x00980903
#define V4L2_CID_AUTO_WHITE_BALANCE 0x0098090C
#define V4L2_CID_RED_BALANCE 0x0098090E
#define V4L2_CID_BLUE_BALANCE 0x0098090F
#define V4L2_CID_GAMMA 0x00980910
#define V4L2_CID_HFLIP 0x00980914
#define V4L2_CID_VFLIP 0x00980915
#define V4L2_CID_SHARPNESS 0x0098091B
#define V4L2_CID_EXPOSURE_ABSOLUTE 0x009a0902
#define V4L2_CID_EXPOSURE_AUTO 0x009a0901
#define V4L2_CID_TEST_PATTERN 0x009a0914
#define V4L2_CID_JPEG_COMPRESSION_QUALITY 0x009d0904
#define V4L2_CID_ANALOGUE_GAIN 0x009e0903
#define V4L2_CID_DIGITAL_GAIN 0x009e0904

/* Backward compatibility: keep old MPIX_* macro names referencing V4L2_* */
#define MPIX_SENSOR_BRIGHTNESS V4L2_CID_BRIGHTNESS
#define MPIX_SENSOR_CONTRAST V4L2_CID_CONTRAST
#define MPIX_SENSOR_SATURATION V4L2_CID_SATURATION
#define MPIX_SENSOR_HUE V4L2_CID_HUE
#define MPIX_SENSOR_AWB V4L2_CID_AUTO_WHITE_BALANCE
#define MPIX_SENSOR_AWB_R_GAIN V4L2_CID_RED_BALANCE
#define MPIX_SENSOR_AWB_B_GAIN V4L2_CID_BLUE_BALANCE
/* G gain has no direct V4L2 standard control; keep a custom ID near user range */
#define MPIX_SENSOR_AWB_G_GAIN 0x0A100001
#define MPIX_SENSOR_GAMMA V4L2_CID_GAMMA
#define MPIX_SENSOR_HMIRROR V4L2_CID_HFLIP
#define MPIX_SENSOR_VFLIP V4L2_CID_VFLIP
#define MPIX_SENSOR_SHARPNESS V4L2_CID_SHARPNESS
#define MPIX_SENSOR_EXPOSURE_ABSOLUTE V4L2_CID_EXPOSURE_ABSOLUTE
#define MPIX_SENSOR_EXPOSURE V4L2_CID_EXPOSURE_ABSOLUTE
#define MPIX_SENSOR_EXPOSURE_AUTO V4L2_CID_EXPOSURE_AUTO
#define MPIX_SENSOR_TEST_PATTERN V4L2_CID_TEST_PATTERN
#define MPIX_SENSOR_JPEG_QUALITY V4L2_CID_JPEG_COMPRESSION_QUALITY
#define MPIX_SENSOR_AGAIN V4L2_CID_ANALOGUE_GAIN
#define MPIX_SENSOR_DGAIN V4L2_CID_DIGITAL_GAIN

/* Custom extended control IDs */
#define MPIX_CID_EXPOSURE_MAX 0x0A300001 /* Returns sensor-specific maximum exposure value */

/* Legacy custom IDs retained (no standard mapping) */
#define MPIX_SENSOR_POWER 0x0A200100
#define MPIX_SENSOR_XCLK 0x0A200101
#define MPIX_SENSOR_MODE 0x0A200102
#define MPIX_SENSOR_FPS 0x0A200103
#define MPIX_SENSOR_DENOISE 0x0A200104
#define MPIX_SENSOR_DPC 0x0A200105
#define MPIX_SENSOR_BLC 0x0A200106
#define MPIX_SENSOR_LENC 0x0A200107
#define MPIX_SENSOR_SCENE 0x0A200108
#define MPIX_SENSOR_AEC 0x0A200109
#define MPIX_SENSOR_AFC 0x0A20010A

/**
 * @brief Sensor capabilities structure
 */
struct mpix_sensor_caps
{
	/** Supported image formats (array of FOURCC codes) */
	uint32_t fourcc;
	/**< Maximum image width */
	size_t max_width;
	/**< Maximum image height */
	size_t max_height;
	/**< Minimum image width */
	size_t min_width;
	/**< Minimum image height */
	size_t min_height;
	/**< Supported frame rates (in fps) */
	uint16_t max_fps;
};

/**
 * @brief Sensor  format structure
 */
struct mpix_sensor_format
{
	/** Image format */
	uint32_t fourcc;
	/** Image width */
	size_t width;
	/** Image height */
	uint16_t height;
	/** Frame rate */
	uint16_t fps;
};

/**
 * @brief Enhanced sensor interface operations
 */
struct mpix_sensor_ops
{
	/** Initialize the sensor hardware */
	int (*init)(const struct mpix_sensor *sensor);

	/** Probe the sensor for capabilities */
	int (*probe)(const struct mpix_sensor *sensor);

	/** Get capabilities */
	int (*get_capabilities)(const struct mpix_sensor *sensor, struct mpix_sensor_caps *caps);

	int (*get_format)(const struct mpix_sensor *sensor, struct mpix_sensor_format *format);

	int (*set_format)(const struct mpix_sensor *sensor,
					  const struct mpix_sensor_format *format);

	/** Set the value of a control parameter */
	int (*set_ctrl)(const struct mpix_sensor *sensor, uint32_t cid, const void *value);

	/** Get the value of a control parameter */
	int (*get_ctrl)(const struct mpix_sensor *sensor, uint32_t cid, void *value);

	/** Start capturing frames */
	int (*start_stream)(struct mpix_sensor *sensor);

	/** Stop capturing frames */
	int (*stop_stream)(struct mpix_sensor *sensor);

	int (*get_frame)(struct mpix_sensor *sensor, struct mpix_image *image, uint32_t timeout_ms);

	int (*release_frame)(struct mpix_sensor *sensor, const struct mpix_image *image);

	/** Cleanup and deinitialize */
	void (*deinit)(struct mpix_sensor *sensor);
};

/**
 * @brief Sensor interface structure
 */
struct mpix_sensor
{
	/** Sensor name */
	const char *name;
	/** Sensor operations */
	const struct mpix_sensor_ops *ops;
	/** Sensor-specific context */
	void *hw_ctx;
	/** Current image format */
	struct mpix_sensor_format format;
	/** Sensor capabilities */
	struct mpix_sensor_caps *caps;
	/** Sensor state */
	enum
	{
		MPIX_SENSOR_STATE_IDLE,
		MPIX_SENSOR_STATE_INITIALIZED,
		MPIX_SENSOR_STATE_STREAMING,
		MPIX_SENSOR_STATE_ERROR
	} state;
};

struct mpix_sensor *sensor_probe(void);
struct mpix_sensor *sensor_get_active(void);

// Camera system compatibility functions
typedef struct
{
	int (*init)(void);
	int (*stream_on)(void);
	int (*stream_off)(void);
} sensor_ops_t;

const sensor_ops_t *sensor_get_ops(int sensor_type);
const char *sensor_get_name(void);
int sensor_probe_wrapper(void);

static inline int mpix_sensor_init(struct mpix_sensor *sensor)
{
	if (!sensor || !sensor->ops || !sensor->ops->init)
	{
		return -EINVAL;
	}
	return sensor->ops->init(sensor);
}

static inline const char *mpix_sensor_get_name(const struct mpix_sensor *sensor)
{
	if (!sensor)
	{
		return NULL;
	}
	return sensor->name;
}

static inline int mpix_sensor_probe(struct mpix_sensor *sensor)
{
	if (!sensor || !sensor->ops || !sensor->ops->probe)
	{
		return -EINVAL;
	}
	return sensor->ops->probe(sensor);
}

static inline int mpix_sensor_get_capabilities(struct mpix_sensor *sensor,
											   struct mpix_sensor_caps *caps)
{
	if (!sensor || !sensor->ops || !sensor->ops->get_capabilities || !caps)
	{
		return -EINVAL;
	}
	return sensor->ops->get_capabilities(sensor, caps);
}

static inline int mpix_sensor_get_format(struct mpix_sensor *sensor,
										 struct mpix_sensor_format *format)
{
	if (!sensor || !sensor->ops || !sensor->ops->get_format || !format)
	{
		return -EINVAL;
	}
	return sensor->ops->get_format(sensor, format);
}

static inline int mpix_sensor_set_format(struct mpix_sensor *sensor,
										 const struct mpix_sensor_format *format)
{
	if (!sensor || !sensor->ops || !sensor->ops->set_format || !format)
	{
		return -EINVAL;
	}
	return sensor->ops->set_format(sensor, format);
}

static inline int mpix_sensor_set_ctrl(struct mpix_sensor *sensor, uint32_t cid, const void *value)
{
	if (!sensor || !sensor->ops || !sensor->ops->set_ctrl || !value)
	{
		return -EINVAL;
	}
	return sensor->ops->set_ctrl(sensor, cid, value);
}

static inline int mpix_sensor_get_ctrl(struct mpix_sensor *sensor, uint32_t cid, void *value)
{
	if (!sensor || !sensor->ops || !sensor->ops->get_ctrl || !value)
	{
		return -EINVAL;
	}
	return sensor->ops->get_ctrl(sensor, cid, value);
}

static inline int mpix_sensor_start_stream(struct mpix_sensor *sensor)
{
	if (!sensor || !sensor->ops || !sensor->ops->start_stream)
	{
		return -EINVAL;
	}
	return sensor->ops->start_stream(sensor);
}

static inline int mpix_sensor_stop_stream(struct mpix_sensor *sensor)
{
	if (!sensor || !sensor->ops || !sensor->ops->stop_stream)
	{
		return -EINVAL;
	}
	return sensor->ops->stop_stream(sensor);
}

static inline int mpix_sensor_get_frame(struct mpix_sensor *sensor, struct mpix_image *image,
										uint32_t timeout_ms)
{
	if (!sensor || !sensor->ops || !sensor->ops->get_frame || !image)
	{
		return -EINVAL;
	}
	return sensor->ops->get_frame(sensor, image, timeout_ms);
}

static inline int mpix_sensor_release_frame(struct mpix_sensor *sensor,
											const struct mpix_image *image)
{
	if (!sensor || !sensor->ops || !sensor->ops->release_frame || !image)
	{
		return -EINVAL;
	}
	return sensor->ops->release_frame(sensor, image);
}

static inline void mpix_sensor_deinit(struct mpix_sensor *sensor)
{
	if (!sensor || !sensor->ops || !sensor->ops->deinit)
	{
		return;
	}
	sensor->ops->deinit(sensor);
}

#endif // MPIX_SENSOR_H
/** @} */
