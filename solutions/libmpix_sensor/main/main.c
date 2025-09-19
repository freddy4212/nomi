#include <stdio.h>
#include <console_io.h>
#include <hx_drv_uart.h>
#include "WE2_device.h"
#include "WE2_core.h"
#include "board.h"
#include "xprintf.h"
#include <mpix/sensor.h>
#include <mpix/image.h>
#include <mpix/formats.h>
#include <mpix/stats.h>
#include <mpix/auto.h>
#include <mpix/op_correction.h>
#include <mpix/op_kernel.h>
#include <mpix/op_resize.h>
#include <mpix/op_palettize.h>
#include <mpix/port.h>
#include <mpix/transport.h>
#include <mpix/transport/uart.h>
#include "FreeRTOS.h"
#include "task.h"

/* Simple image transfer protocol */
#define FRAME_HEADER 0xAA55AA55
#define FRAME_FOOTER 0x55AA55AA

// Remove direct DEV_UART usage; use transport abstraction
static struct mpix_transport g_uart_transport; /* UART transport instance */

typedef struct
{
    uint32_t header;    /* Frame header magic number */
    uint32_t frame_id;  /* Frame sequence number */
    uint16_t width;     /* Image width */
    uint16_t height;    /* Image height */
    uint32_t data_size; /* Image data size in bytes */
    uint16_t checksum;  /* Simple checksum of data */
    uint16_t reserved;  /* Reserved for alignment */
} __attribute__((packed)) image_frame_header_t;

typedef struct
{
    uint32_t footer; /* Frame footer magic number */
} __attribute__((packed)) image_frame_footer_t;

/* Calculate simple checksum */
static uint16_t calculate_checksum(const uint8_t *data, uint32_t size)
{
    uint32_t sum = 0;
    for (uint32_t i = 0; i < size; i++)
    {
        sum += data[i];
    }
    return (uint16_t)(sum & 0xFFFF);
}

/* Send image through UART transport */
static int _transport_send_all(struct mpix_transport *t, const uint8_t *buf, size_t len)
{
    size_t sent = 0;
    while (sent < len)
    {
        int rc = mpix_transport_send(t, buf + sent, len - sent);
        if (rc < 0)
            return rc;
        if (rc == 0)
        {
            taskYIELD();
            continue;
        }
        sent += (size_t)rc;
    }
    return (int)sent;
}

static void send_image_frame(uint32_t frame_id, const struct mpix_image *image)
{
    image_frame_header_t header;
    image_frame_footer_t footer;

    header.header = FRAME_HEADER;
    header.frame_id = frame_id;
    header.width = image->width;
    header.height = image->height;
    header.data_size = image->size;
    header.checksum = calculate_checksum((const uint8_t *)image->buffer, image->size);
    header.reserved = 0;
    footer.footer = FRAME_FOOTER;

    _transport_send_all(&g_uart_transport, (uint8_t *)&header, sizeof(header));
    _transport_send_all(&g_uart_transport, (const uint8_t *)image->buffer, image->size);
    _transport_send_all(&g_uart_transport, (uint8_t *)&footer, sizeof(footer));
}

/* Task configuration */
#define CAMERA_TASK_STACK_SIZE (8192)
#define CAMERA_TASK_PRIORITY (tskIDLE_PRIORITY + 2)

static void camera_task(void *pvParameters)
{
    (void)pvParameters;
    static uint32_t frame_counter = 0;

    // Initialize UART transport
    struct mpix_transport_uart_config cfg;
    mpix_transport_uart_config_default(&cfg);
    cfg.port_id = USE_DW_UART_1;
    cfg.baudrate = UART_BAUDRATE_921600;
    cfg.tx_chunk = 4095;              // max chunk
    cfg.send_buffer_size = 64 * 1024; // larger TX ring for burst frames
    cfg.recv_buffer_size = 4 * 1024;  // modest RX ring
    if (mpix_transport_uart_create_with_config(&g_uart_transport, &cfg) != 0)
    {
        xprintf("UART transport create failed\n");
        vTaskDelete(NULL);
    }
    if (mpix_transport_init(&g_uart_transport) != 0)
    {
        xprintf("UART transport init failed\n");
        vTaskDelete(NULL);
    }

    struct mpix_sensor *sensor = sensor_probe();
    if (!sensor)
    {
        xprintf("No camera sensor found!\n");
        vTaskDelete(NULL);
    }
    else
    {
        xprintf("Camera sensor found: %s\n", mpix_sensor_get_name(sensor));
    }

    mpix_sensor_set_format(sensor, &(struct mpix_sensor_format){.width = 640, .height = 480});
    mpix_sensor_start_stream(sensor);
    xprintf("Starting image transmission (task) ...\n");

    struct mpix_image jpeg = {};
    struct mpix_stats stats = {};
    struct mpix_auto_ctrls ctrls = {};
    jpeg.buffer = mpix_port_alloc(128 * 1024);
    jpeg.size = 128 * 1024;
    mpix_auto_exposure_init(&ctrls, sensor);
    ctrls.correction.color_matrix.levels[0] = 2235; // 4650K matrix
    ctrls.correction.color_matrix.levels[1] = -726;
    ctrls.correction.color_matrix.levels[2] = -484;
    ctrls.correction.color_matrix.levels[3] = -719;
    ctrls.correction.color_matrix.levels[4] = 2830;
    ctrls.correction.color_matrix.levels[5] = -1088;
    ctrls.correction.color_matrix.levels[6] = -257;
    ctrls.correction.color_matrix.levels[7] = -737;
    ctrls.correction.color_matrix.levels[8] = 2018;
    ctrls.correction.gamma.level = 12 << 5;
    ctrls.ae_target = 36; // Set initial AE target to mid-level
    uint64_t last_time = mpix_port_get_uptime_us();
    while (1)
    {
        struct mpix_image image = {};
        if (mpix_sensor_get_frame(sensor, &image, 1000) == 0)
        {
            frame_counter++;
            mpix_image_stats(&image, &stats);
            // mpix_auto_black_level(&ctrls, &stats);
            mpix_auto_white_balance(&ctrls, &stats);
            mpix_auto_exposure_control(&ctrls, &stats);

            ctrls.correction.black_level.level = 16;
            mpix_image_correction(&image, MPIX_CORRECTION_BLACK_LEVEL, (union mpix_correction_any *)&ctrls.correction.black_level);
            mpix_image_correction(&image, MPIX_CORRECTION_GAMMA, (union mpix_correction_any *)&ctrls.correction.gamma);
            mpix_image_debayer(&image, 3);
            mpix_image_correction(&image, MPIX_CORRECTION_WHITE_BALANCE, (union mpix_correction_any *)&ctrls.correction.white_balance);
            mpix_image_correction(&image, MPIX_CORRECTION_COLOR_MATRIX, (union mpix_correction_any *)&ctrls.correction.color_matrix);
            mpix_image_kernel(&image, MPIX_KERNEL_DENOISE, 3);
            // image.flag_print_ops = 1; // reduce log noise inside RTOS
            mpix_image_jpeg_encode(&image, JPEGE_Q_MED);
            mpix_image_to_buf(&image, jpeg.buffer, 128 * 1024);
            jpeg.width = image.width;
            jpeg.height = image.height;
            jpeg.fourcc = MPIX_FMT_JPEG;
            jpeg.err = 0;
            jpeg.size = image.size;
            send_image_frame(frame_counter, &jpeg);
            mpix_sensor_release_frame(sensor, &image);

            mpix_port_printf("Frame %lu: %ux%u, size=%u, err=%d, AE exp=%d, AWB R=%u B=%u, time=%dms\n",
                             frame_counter, jpeg.width, jpeg.height, jpeg.size, jpeg.err,
                             ctrls.exposure_level,
                             ctrls.correction.white_balance.red_level,
                             ctrls.correction.white_balance.blue_level,
                             (int)(mpix_port_get_uptime_us() - last_time) / 1000);
            last_time = mpix_port_get_uptime_us();
        }
        else
        {
            xprintf("Frame timeout\n");
            vTaskDelay(pdMS_TO_TICKS(200));
        }
        taskYIELD();
    }
}

// Replace original main loop with RTOS startup
int main(void)
{
    board_init();
    xprintf("\n[BOOT] Starting camera FreeRTOS task...\n");

    BaseType_t res = xTaskCreate(camera_task, "CameraTask", CAMERA_TASK_STACK_SIZE, NULL, CAMERA_TASK_PRIORITY, NULL);
    if (res != pdPASS)
    {
        xprintf("Failed to create CameraTask\n");
        while (1)
        {
            board_delay_ms(1000);
        }
    }

    vTaskStartScheduler();
    while (1)
    {
        board_delay_ms(1000);
    }
}