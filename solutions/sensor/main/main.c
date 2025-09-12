#include <stdio.h>
#include <console_io.h>
#include <hx_drv_uart.h>
#include "WE2_device.h"
#include "WE2_core.h"
#include "board.h"
#include "xprintf.h"
#include <mpix/sensor.h>

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
    for (int i = 0; i < sizeof(header); i++)
    {
        xprintf("%c", header_bytes[i]);
    }

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
    for (int i = 0; i < sizeof(footer); i++)
    {
        xprintf("%c", footer_bytes[i]);
    }
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

    while (1)
    {
        struct mpix_image image;
        if (mpix_sensor_get_frame(sensor, &image, 1000) == 0)
        {
            frame_counter++;

            /* Send debug info as text first */
            xprintf("FRAME_START:%d,%d,%d,%d %d\n",
                    frame_counter, image.width, image.height, image.size, mpix_port_get_uptime_us());

            /* Send binary image data */
            send_image_frame(frame_counter, &image);

            /* Send debug info as text after */
            xprintf("FRAME_END:%d\n", frame_counter);

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