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
/* Simple image transfer protocol */
#define FRAME_HEADER 0xAA55AA55
#define FRAME_FOOTER 0x55AA55AA

static DEV_UART *_uart = NULL;
static volatile bool _tx_busy = false;

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

static void _uart_dma_send(void *)
{
    _tx_busy = false;
}

/* Send image through serial port */
static void send_image_frame(uint32_t frame_id, const struct mpix_image *image)
{
    image_frame_header_t header;
    image_frame_footer_t footer;

    /* Prepare header */
    header.header = FRAME_HEADER;
    header.frame_id = frame_id;
    header.width = image->width;
    header.height = image->height;
    header.data_size = image->size;
    header.checksum = calculate_checksum((const uint8_t *)image->buffer, image->size);
    header.reserved = 0;

    /* Prepare footer */
    footer.footer = FRAME_FOOTER;

    /* Send header (as binary data through xprintf with %c) */
    uint8_t *header_bytes = (uint8_t *)&header;
    SCB_CleanDCache_by_Addr((uint32_t *)header_bytes, sizeof(header));
    _tx_busy = true;
    _uart->uart_write_udma(header_bytes, sizeof(header), _uart_dma_send);
    while (_tx_busy)
        ;

    /* Send image data */
    uint8_t *data_bytes = (uint8_t *)image->buffer;
    // send each 4095 chunks
    const int chunk_size = 4095;
    int bytes_sent = 0;
    while (bytes_sent < image->size)
    {
        _tx_busy = true;
        int bytes_to_send = (image->size - bytes_sent) > chunk_size ? chunk_size : (image->size - bytes_sent);
        SCB_CleanDCache_by_Addr((uint32_t *)(data_bytes + bytes_sent), bytes_to_send);
        _uart->uart_write_udma(data_bytes + bytes_sent, bytes_to_send, _uart_dma_send);
        while (_tx_busy)
            ;
        bytes_sent += bytes_to_send;
    }

    /* Send footer */
    uint8_t *footer_bytes = (uint8_t *)&footer;
    SCB_CleanDCache_by_Addr((uint32_t *)footer_bytes, sizeof(footer));
    _tx_busy = true;
    _uart->uart_write_udma(footer_bytes, sizeof(footer), _uart_dma_send);
    while (_tx_busy)
        ;
}

int main(void)
{
    static uint32_t frame_counter = 0;

    board_init();

    _uart = hx_drv_uart_get_dev(USE_DW_UART_0);
    if (_uart == NULL)
    {
        return 0;
    }

    int ret = _uart->uart_open(UART_BAUDRATE_921600);
    if (ret != 0)
    {
        return 0;
    }

    struct mpix_sensor *sensor = sensor_probe();
    if (!sensor)
    {
        xprintf("No camera sensor found!\n");
        while (1)
        {
            board_delay_ms(1000);
        }
    }
    else
    {
        xprintf("Camera sensor found: %s\n", mpix_sensor_get_name(sensor));
    }

    mpix_sensor_set_format(sensor, &(struct mpix_sensor_format){
                                       .width = 1280,
                                       .height = 960,
                                   });
    mpix_sensor_start_stream(sensor);
    xprintf("Starting image transmission...\n");
    board_delay_ms(1000); /* Give time for startup message */
    struct mpix_image jpeg = {};
    struct mpix_stats stats = {};
    struct mpix_auto_ctrls ctrls = {};
    jpeg.buffer = mpix_port_alloc(128 * 1024);
    jpeg.size = 128 * 1024;
    while (1)
    {
        struct mpix_image image = {};

        if (mpix_sensor_get_frame(sensor, &image, 1000) == 0)
        {
            frame_counter++;
            // mpix_stats_print(&stats);

            mpix_image_stats(&image, &stats);

            mpix_auto_black_level(&ctrls, &stats);
            mpix_auto_white_balance(&ctrls, &stats);

            /* Convert from raw bayer to RGB24 */
            mpix_image_debayer(&image, 3);

            // mpix_stats_print(&stats);

            /* Apply all the color correction to the palette only */
            // mpix_image_correction(&image, MPIX_CORRECTION_BLACK_LEVEL, &ctrls.correction.black_level);
            mpix_image_correction(&image, MPIX_CORRECTION_WHITE_BALANCE, &ctrls.correction.white_balance);
            // mpix_image_correction(&image, MPIX_CORRECTION_GAMMA, &ctrls.correction.gamma);

            // mpix_image_kernel(&image, MPIX_KERNEL_DENOISE, 3);
            // mpix_image_kernel(&image, MPIX_KERNEL_SHARPEN, 3);

            mpix_image_jpeg_encode(&image, JPEGE_Q_MED);

            mpix_image_to_buf(&image, jpeg.buffer, 128 * 1024);
            jpeg.width = image.width;
            jpeg.height = image.height;
            jpeg.fourcc = MPIX_FMT_JPEG;
            jpeg.err = 0;
            jpeg.size = image.size;

            /* Send debug info as text first */
            xprintf("FRAME_START:%d,%d,%d,%d\n",
                    frame_counter, image.width, image.height, image.size);

            /* Send binary image data */
            send_image_frame(frame_counter, &jpeg);

            /* Send debug info as text after */
            xprintf("FRAME_END\n", frame_counter);

            mpix_sensor_release_frame(sensor, &image);
        }
        else
        {
            xprintf("Failed to get frame\n");
            board_delay_ms(500);
        }
    }
    return 0;
}