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

#define MPIX_CID_BASE 0x00980000

#define MPIX_SENSOR_POWER (MPIX_CID_BASE + 0x0001)
#define MPIX_SENSOR_XCLK (MPIX_CID_BASE + 0x0002)
#define MPIX_SENSOR_MODE (MPIX_CID_BASE + 0x0003)
#define MPIX_SENSOR_FPS (MPIX_CID_BASE + 0x0004)
#define MPIX_SENSOR_BRIGHTNESS (MPIX_CID_BASE + 0x0005)
#define MPIX_SENSOR_CONTRAST (MPIX_CID_BASE + 0x0006)
#define MPIX_SENSOR_SATURATION (MPIX_CID_BASE + 0x0007)
#define MPIX_SENSOR_HUE (MPIX_CID_BASE + 0x0008)
#define MPIX_SENSOR_SHARPNESS (MPIX_CID_BASE + 0x0009)
#define MPIX_SENSOR_GAMMA (MPIX_CID_BASE + 0x000A)
#define MPIX_SENSOR_DENOISE (MPIX_CID_BASE + 0x000B)
#define MPIX_SENSOR_DPC (MPIX_CID_BASE + 0x000C)
#define MPIX_SENSOR_BLC (MPIX_CID_BASE + 0x000D)
#define MPIX_SENSOR_HMIRROR (MPIX_CID_BASE + 0x000E)
#define MPIX_SENSOR_VFLIP (MPIX_CID_BASE + 0x000F)
#define MPIX_SENSOR_LENC (MPIX_CID_BASE + 0x0010)
#define MPIX_SENSOR_SCENE (MPIX_CID_BASE + 0x0011)
#define MPIX_SENSOR_JPEG_QUALITY (MPIX_CID_BASE + 0x0012)

#define MPIX_SENSOR_AWB (MPIX_CID_BASE + 0x0020)
#define MPIX_SENSOR_EXPOSURE (MPIX_CID_BASE + 0x0021)
#define MPIX_SENSOR_DGAIN (MPIX_CID_BASE + 0x0022)
#define MPIX_SENSOR_AGAIN (MPIX_CID_BASE + 0x0023)
#define MPIX_SENSOR_AEC (MPIX_CID_BASE + 0x0024)
#define MPIX_SENSOR_AWB_R_GAIN (MPIX_CID_BASE + 0x0025)
#define MPIX_SENSOR_AWB_G_GAIN (MPIX_CID_BASE + 0x0026)
#define MPIX_SENSOR_AWB_B_GAIN (MPIX_CID_BASE + 0x0027)
#define MPIX_SENSOR_AFC (MPIX_CID_BASE + 0x0028)
#define MPIX_SENSOR_TEST_PATTERN (MPIX_CID_BASE + 0x0030)

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
typedef struct {
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
