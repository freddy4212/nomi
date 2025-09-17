/**
 * SPDX-License-Identifier: Apache-2.0
 * @file sensor.c
 * @brief Camera sensor probe and management
 */

#include <mpix/sensor.h>
#include <mpix/sensor/ov5647.h>
#include <mpix/sensor/imx219.h>
#include <mpix/sensor/sccb.h>

/* Currently active sensor */
static struct mpix_sensor *active_sensor = NULL;

/**
 * @brief Probe for available camera sensors
 * @return Pointer to found sensor, NULL if none found
 */
struct mpix_sensor *sensor_probe(void)
{
    struct mpix_sensor *sensor;
    int ret;

    /* Initialize SCCB interface */
    ret = sccb_init();
    if (ret < 0)
    {
        return NULL;
    }

    /* Try OV5647 */
    sensor = ov5647_get_sensor();
    if (sensor)
    {
        /* Initialize sensor */
        ret = mpix_sensor_init(sensor);
        if (ret == 0)
        {
            /* Probe sensor */
            ret = mpix_sensor_probe(sensor);
            if (ret == 0)
            {
                active_sensor = sensor;
                return sensor;
            }
        }
    }

    /* Try IMX219 */
    sensor = imx219_get_sensor();
    if (sensor)
    {
        /* Initialize sensor */
        ret = mpix_sensor_init(sensor);
        if (ret == 0)
        {
            /* Probe sensor */
            ret = mpix_sensor_probe(sensor);
            if (ret == 0)
            {
                active_sensor = sensor;
                return sensor;
            }
        }
    }

    return NULL;
}

/**
 * @brief Get the currently active sensor
 * @return Pointer to active sensor, NULL if none
 */
struct mpix_sensor *sensor_get_active(void)
{
    return active_sensor;
}

/**
 * @brief Get sensor name string
 * @return Sensor name string, NULL if no active sensor
 */
const char *sensor_get_name(void)
{
    if (!active_sensor || !active_sensor->name)
    {
        return NULL;
    }
    return active_sensor->name;
}
