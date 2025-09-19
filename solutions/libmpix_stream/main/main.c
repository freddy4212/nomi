#include <stdio.h>
#include <console_io.h>
#include <hx_drv_uart.h>
#include "WE2_device.h"
#include "WE2_core.h"
#include "board.h"
#include "xprintf.h"
#include <mpix/sensor.h>
#include <mpix/transport.h>
#include <mpix/transport/uart.h>
#include <mpix/protocol.h>
#include <mpix/image.h>
#include <mpix/formats.h>
#include <mpix/stats.h>
#include <mpix/auto.h>
#include <mpix/op_correction.h>
#include <mpix/op_kernel.h>
#include <mpix/op_resize.h>
#include <mpix/op_jpeg.h>
#include <mpix/port.h>
#include "FreeRTOS.h"
#include "task.h"

/* Task configuration */
#define PROTOCOL_TASK_STACK_SIZE (8192)
#define CAMERA_TASK_STACK_SIZE (8192)
#define PROTOCOL_TASK_PRIORITY (tskIDLE_PRIORITY + 3)
#define CAMERA_TASK_PRIORITY (tskIDLE_PRIORITY + 2)

/* Global instances */
static struct mpix_transport g_uart_transport;
static struct mpix_protocol_context g_protocol_ctx;
static TaskHandle_t g_camera_task_handle = NULL;

/* Protocol processing task */
static void protocol_task(void *pvParameters)
{
    (void)pvParameters;

    xprintf("[PROTOCOL] Task started\n");

    uint32_t process_count = 0;
    uint32_t error_count = 0;
    uint32_t last_stats_time = 0;
    uint32_t consecutive_errors = 0;

    while (1)
    {
        /* Process incoming protocol messages */
        int ret = mpix_protocol_process(&g_protocol_ctx);
        process_count++;

        if (ret > 0)
        {
            xprintf("[PROTOCOL] Processed command, bytes: %d\n", ret);
            consecutive_errors = 0; /* Reset consecutive error count */
        }
        else if (ret == -EAGAIN)
        {
            /* No data available - this is normal */
            consecutive_errors = 0;
        }
        else if (ret < 0)
        {
            error_count++;
            consecutive_errors++;
            g_protocol_ctx.error_counter++;

            /* Detailed error diagnostics */
            const char *error_desc = "Unknown";
            switch (ret)
            {
            case -EINVAL:
                error_desc = "Invalid parameter";
                break;
            case -EAGAIN:
                error_desc = "Try again";
                break;
            case -EBADMSG:
                error_desc = "Bad message/Invalid header/checksum";
                break;
            case -E2BIG:
                error_desc = "Message too large";
                break;
            case -ENOMEM:
                error_desc = "Out of memory";
                break;
            case -EIO:
                error_desc = "I/O error";
                break;
            case -ENODEV:
                error_desc = "No device";
                break;
            case -EBUSY:
                error_desc = "Device busy";
                break;
            case -ETIMEDOUT:
                error_desc = "Timeout";
                break;
            default:
                if (ret == -77)
                    error_desc = "EBADMSG - Bad message format";
                break;
            }

            xprintf("[PROTOCOL] Error processing command: %d (%s), total errors: %d, consecutive: %d\n",
                    ret, error_desc, error_count, consecutive_errors);

            /* If we have too many consecutive errors, try recovery measures */
            if (consecutive_errors >= 5)
            {
                xprintf("[PROTOCOL] Too many consecutive errors, attempting recovery...\n");

                /* Try to drain any remaining data from the transport */
                if (g_protocol_ctx.transport)
                {
                    /* Check if there's data to drain */
                    int drain_count = 0;
                    while (mpix_transport_is_recv_ready(g_protocol_ctx.transport) && drain_count < 1024)
                    {
                        uint8_t dummy;
                        if (mpix_transport_recv(g_protocol_ctx.transport, &dummy, 1) <= 0)
                        {
                            break;
                        }
                        drain_count++;
                    }
                    if (drain_count > 0)
                    {
                        xprintf("[PROTOCOL] Drained %d bytes from transport buffer\n", drain_count);
                    }
                }

                consecutive_errors = 0;         /* Reset after recovery attempt */
                vTaskDelay(pdMS_TO_TICKS(100)); /* Brief pause */
            }
        }

        /* Print statistics every 5 seconds */
        uint32_t current_time = xTaskGetTickCount() * portTICK_PERIOD_MS;
        if (current_time - last_stats_time > 5000)
        {
            xprintf("[PROTOCOL] Stats - Processed: %lu, Errors: %lu, Stream: %s\n",
                    process_count, error_count, g_protocol_ctx.streaming ? "ON" : "OFF");

            /* Also print transport status if available */
            if (g_protocol_ctx.transport)
            {
                xprintf("[PROTOCOL] Transport status - RX ready: %s\n",
                        mpix_transport_is_recv_ready(g_protocol_ctx.transport) ? "YES" : "NO");
            }

            last_stats_time = current_time;
            process_count = 0; /* Reset counters for next period */
            error_count = 0;
        }

        /* Small delay to prevent busy waiting */
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

/* Camera streaming task */
static void camera_task(void *pvParameters)
{
    (void)pvParameters;

    xprintf("[CAMERA] Task started\n");

    struct mpix_image processed_image = {};
    
    // Wait a bit for sensor initialization to complete
    vTaskDelay(pdMS_TO_TICKS(500));
    
    // Get current sensor format to calculate buffer size dynamically
    struct mpix_sensor_format current_format;
    if (mpix_sensor_get_format(g_protocol_ctx.sensor, &current_format) != 0) {
        // Fallback to default if we can't get format
        current_format.width = 640;
        current_format.height = 480;
        xprintf("[CAMERA] WARNING: Could not get sensor format, using default 640x480\n");
    }
    
    // Calculate buffer size based on actual sensor format: width*height*3 for RGB24 (maximum size)
    size_t image_buffer_size = current_format.width * current_format.height * 3; // RGB24 is the largest format
    processed_image.buffer = mpix_port_alloc(image_buffer_size);
    processed_image.size = image_buffer_size;

    if (!processed_image.buffer)
    {
        xprintf("[CAMERA] ERROR: Failed to allocate image buffer\n");
        vTaskDelete(NULL);
        return;
    }

    xprintf("[CAMERA] Image buffer allocated: %u bytes (%dx%dx3 RGB24)\n", 
            image_buffer_size, current_format.width, current_format.height);

    uint32_t frame_count = 0;
    uint32_t error_count = 0;
    uint32_t last_fps_time = 0;

    while (1)
    {
        /* Check if streaming is enabled */
        if (!g_protocol_ctx.streaming)
        {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        /* Get frame from sensor */
        struct mpix_image raw_image = {};
        int ret = mpix_sensor_get_frame(g_protocol_ctx.sensor, &raw_image, 1000);
        if (ret != 0)
        {
            error_count++;
            if (error_count % 10 == 1)
            { /* Log every 10th error to avoid spam */
                xprintf("[CAMERA] Frame timeout/error: %d (total errors: %d)\n", ret, error_count);
            }
            vTaskDelay(pdMS_TO_TICKS(200));
            continue;
        }

        frame_count++;

        /* Log frame info occasionally */
        if (frame_count % 30 == 1)
        {
            xprintf("[CAMERA] Frame %lu: %dx%d, size: %d, fourcc: 0x%x\n",
                    frame_count, raw_image.width, raw_image.height, raw_image.size, raw_image.fourcc);
        }

        /* Process the image based on stream mode */
        struct mpix_image *output_image = &raw_image;

        if (g_protocol_ctx.stream_mode != MPIX_STREAM_MODE_RAW)
        {
            /* Copy raw image properties */
            mpix_image_from_buf(&processed_image, raw_image.buffer, raw_image.size,
                                raw_image.width, raw_image.height, raw_image.fourcc);

            /* Run auto algorithms if enabled */
            if (g_protocol_ctx.ae_enabled || g_protocol_ctx.awb_enabled || g_protocol_ctx.ablc_enabled)
            {
                mpix_image_stats(&processed_image, &g_protocol_ctx.stats);

                /* Run individual auto algorithms based on enable flags */
                if (g_protocol_ctx.awb_enabled)
                {
                    mpix_auto_white_balance(&g_protocol_ctx.auto_ctrls, &g_protocol_ctx.stats);
                }
                if (g_protocol_ctx.ae_enabled)
                {
                    mpix_auto_exposure_control(&g_protocol_ctx.auto_ctrls, &g_protocol_ctx.stats);
                }
                if (g_protocol_ctx.ablc_enabled)
                {
                    mpix_auto_black_level(&g_protocol_ctx.auto_ctrls, &g_protocol_ctx.stats);
                }

                if (frame_count % 60 == 1)
                { /* Log auto algorithm status every 60 frames */
                    xprintf("[CAMERA] Auto algorithms - AE: %s, AWB: %s, ABLC: %s\n",
                            g_protocol_ctx.ae_enabled ? "ON" : "OFF",
                            g_protocol_ctx.awb_enabled ? "ON" : "OFF",
                            g_protocol_ctx.ablc_enabled ? "ON" : "OFF");
                }
            }

            /* Apply ISP corrections based on enable flags */
            if (g_protocol_ctx.black_level_correction_enabled) {
                mpix_image_correction(&processed_image, MPIX_CORRECTION_BLACK_LEVEL,
                                      (union mpix_correction_any *)&g_protocol_ctx.auto_ctrls.correction.black_level);
            }
            
            if (g_protocol_ctx.gamma_correction_enabled) {
                mpix_image_correction(&processed_image, MPIX_CORRECTION_GAMMA,
                                      (union mpix_correction_any *)&g_protocol_ctx.auto_ctrls.correction.gamma);
            }

            /* Debayer to RGB */
            mpix_image_debayer(&processed_image, 3);

            /* Apply more ISP corrections based on enable flags */
            if (g_protocol_ctx.white_balance_correction_enabled) {
                mpix_image_correction(&processed_image, MPIX_CORRECTION_WHITE_BALANCE,
                                      (union mpix_correction_any *)&g_protocol_ctx.auto_ctrls.correction.white_balance);
            }
            
            if (g_protocol_ctx.color_matrix_correction_enabled) {
                mpix_image_correction(&processed_image, MPIX_CORRECTION_COLOR_MATRIX,
                                      (union mpix_correction_any *)&g_protocol_ctx.auto_ctrls.correction.color_matrix);
            }

            /* Apply denoise filter based on enable flag */
            if (g_protocol_ctx.denoise_filter_enabled) {
                mpix_image_kernel(&processed_image, MPIX_KERNEL_DENOISE, 3);
            }

            /* Apply format-specific processing */
            xprintf("[CAMERA] Current stream mode: %d\n", g_protocol_ctx.stream_mode);
            switch (g_protocol_ctx.stream_mode)
            {
            case MPIX_STREAM_MODE_RGB:
                /* Keep as RGB */
                if (frame_count % 60 == 1)
                {
                    xprintf("[CAMERA] Processing mode: RGB\n");
                }
                break;

            case MPIX_STREAM_MODE_JPEG:
                /* Compress to JPEG */
                mpix_image_jpeg_encode(&processed_image, JPEGE_Q_MED);
                if (frame_count % 60 == 1)
                {
                    xprintf("[CAMERA] Processing mode: JPEG\n");
                }
                break;

            case MPIX_STREAM_MODE_AUTO:
                /* Auto mode - use JPEG with auto algorithms */
                mpix_image_jpeg_encode(&processed_image, JPEGE_Q_MED);
                if (frame_count % 60 == 1)
                {
                    xprintf("[CAMERA] Processing mode: AUTO\n");
                }
                break;

            default:
                if (frame_count % 60 == 1)
                {
                    xprintf("[CAMERA] Processing mode: UNKNOWN (%d)\n", g_protocol_ctx.stream_mode);
                }
                break;
            }

            /* Convert to output buffer */
            mpix_image_to_buf(&processed_image, processed_image.buffer, image_buffer_size);
            output_image = &processed_image;
        }

        /* Send the frame */
        ret = mpix_protocol_send_frame(&g_protocol_ctx, output_image);
        if (ret != 0)
        {
            g_protocol_ctx.error_counter++;
            if (g_protocol_ctx.error_counter % 10 == 1)
            { /* Log every 10th send error */
                xprintf("[CAMERA] Send frame error: %d (total: %d)\n", ret, g_protocol_ctx.error_counter);
            }
        }

        /* Release the raw frame */
        mpix_sensor_release_frame(g_protocol_ctx.sensor, &raw_image);

        /* Calculate and display FPS every 5 seconds */
        uint32_t current_time = xTaskGetTickCount() * portTICK_PERIOD_MS;
        if (current_time - last_fps_time > 5000)
        {
            float fps = (float)(frame_count * 1000) / (current_time - last_fps_time + 1);
            xprintf("[CAMERA] FPS: %d, Frames: %lu, Errors: %lu\n", (int)fps, frame_count, error_count);
            frame_count = 0;
            error_count = 0;
            last_fps_time = current_time;
        }

        /* Yield to other tasks */
        taskYIELD();
    }

    /* Cleanup */
    if (processed_image.buffer)
    {
        mpix_port_free(processed_image.buffer);
        xprintf("[CAMERA] Image buffer freed\n");
    }
    vTaskDelete(NULL);
}

/* Initialize the system */
static int system_init(void)
{
    xprintf("[INIT] Starting system initialization...\n");

    /* Initialize UART transport */
    struct mpix_transport_uart_config uart_cfg;
    mpix_transport_uart_config_default(&uart_cfg);
    uart_cfg.port_id = USE_DW_UART_1;
    uart_cfg.baudrate = UART_BAUDRATE_921600;
    uart_cfg.tx_chunk = 4095;
    uart_cfg.send_buffer_size = 64 * 1024;
    uart_cfg.recv_buffer_size = 8 * 1024;

    xprintf("[INIT] UART config - Port: %d, Baud: %d, TX buf: %d, RX buf: %d\n",
            uart_cfg.port_id, uart_cfg.baudrate, uart_cfg.send_buffer_size, uart_cfg.recv_buffer_size);

    if (mpix_transport_uart_create_with_config(&g_uart_transport, &uart_cfg) != 0)
    {
        xprintf("[INIT] ERROR: UART transport create failed\n");
        return -1;
    }
    xprintf("[INIT] UART transport created successfully\n");

    if (mpix_transport_init(&g_uart_transport) != 0)
    {
        xprintf("[INIT] ERROR: UART transport init failed\n");
        return -1;
    }
    xprintf("[INIT] UART transport initialized successfully\n");

    /* Probe sensor */
    xprintf("[INIT] Probing camera sensor...\n");
    struct mpix_sensor *sensor = sensor_probe();
    if (!sensor)
    {
        xprintf("[INIT] ERROR: No camera sensor found\n");
        return -1;
    }
    xprintf("[INIT] Camera sensor found and probed successfully\n");

    /* Set default sensor format */
    struct mpix_sensor_format format = {
        .fourcc = MPIX_FMT_SRGGB8, /* Raw Bayer format */
        .width = 640,
        .height = 480,
        .fps = 30};

    xprintf("[INIT] Setting sensor format: %dx%d @ %dfps, fourcc: 0x%x\n",
            format.width, format.height, format.fps, format.fourcc);

    if (mpix_sensor_set_format(sensor, &format) != 0)
    {
        xprintf("[INIT] WARNING: Failed to set sensor format\n");
    }
    else
    {
        xprintf("[INIT] Sensor format set successfully\n");
    }

    /* Initialize protocol context */
    xprintf("[INIT] Initializing protocol context...\n");
    if (mpix_protocol_init(&g_protocol_ctx, sensor, &g_uart_transport) != 0)
    {
        xprintf("[INIT] ERROR: Protocol init failed\n");
        return -1;
    }
    xprintf("[INIT] Protocol context initialized successfully\n");

    xprintf("[INIT] System initialization completed successfully\n");
    return 0;
}

/* Main function */
int main(void)
{
    board_init();

    xprintf("\n========================================\n");
    xprintf("[BOOT] Starting MPIX Stream System...\n");
    xprintf("[BOOT] Firmware Version: 1.0.0\n");
    xprintf("[BOOT] Build Date: %s %s\n", __DATE__, __TIME__);
    xprintf("========================================\n");

    /* Initialize the system */
    if (system_init() != 0)
    {
        xprintf("[BOOT] ERROR: System initialization failed - system halted\n");
        while (1)
        {
            board_delay_ms(1000);
        }
    }

    /* Create protocol processing task */
    xprintf("[BOOT] Creating protocol processing task...\n");
    BaseType_t res = xTaskCreate(protocol_task, "ProtocolTask", PROTOCOL_TASK_STACK_SIZE,
                                 NULL, PROTOCOL_TASK_PRIORITY, NULL);
    if (res != pdPASS)
    {
        xprintf("[BOOT] ERROR: Failed to create ProtocolTask - system halted\n");
        while (1)
        {
            board_delay_ms(1000);
        }
    }
    xprintf("[BOOT] ProtocolTask created successfully\n");

    /* Create camera streaming task */
    xprintf("[BOOT] Creating camera streaming task...\n");
    res = xTaskCreate(camera_task, "CameraTask", CAMERA_TASK_STACK_SIZE,
                      NULL, CAMERA_TASK_PRIORITY, &g_camera_task_handle);
    if (res != pdPASS)
    {
        xprintf("[BOOT] ERROR: Failed to create CameraTask - system halted\n");
        while (1)
        {
            board_delay_ms(1000);
        }
    }
    xprintf("[BOOT] CameraTask created successfully\n");

    xprintf("[BOOT] All tasks created, starting FreeRTOS scheduler...\n");
    xprintf("[BOOT] Protocol UART: USE_DW_UART_1 @ 921600 baud\n");
    xprintf("[BOOT] System ready for protocol communication\n");
    xprintf("========================================\n");

    /* Start the scheduler */
    vTaskStartScheduler();

    /* Should never reach here */
    xprintf("[BOOT] ERROR: Scheduler returned - system halted\n");
    while (1)
    {
        board_delay_ms(1000);
    }
}