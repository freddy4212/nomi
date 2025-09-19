#include <stdio.h>
#include <console_io.h>
#include <hx_drv_uart.h>
#include <hx_drv_scu.h>
#include "WE2_device.h"
#include "WE2_core.h"
#include "board.h"
#include "xprintf.h"
#include <mpix/sensor.h>
#include <mpix/transport.h>
#include <mpix/transport/uart.h>

#include "FreeRTOS.h"
#include "task.h"


/* Simple image transfer protocol */
#define FRAME_HEADER 0xAA55AA55
#define FRAME_FOOTER 0x55AA55AA

static DEV_UART *_uart = NULL;
static volatile bool _tx_busy = false;

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

static void _uart_dma_send(void *)
{
    _tx_busy = false;
}

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
            continue;
        }
        sent += (size_t)rc;
    }
    return (int)sent;
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

    _transport_send_all(&g_uart_transport, (uint8_t *)&header, sizeof(header));
    _transport_send_all(&g_uart_transport, (const uint8_t *)image->buffer, image->size);
    _transport_send_all(&g_uart_transport, (uint8_t *)&footer, sizeof(footer));

    // xprintf("sending frame %d, size=%d\n", frame_id, image->size);
    // /* Send header (as binary data through xprintf with %c) */
    // _tx_busy = true;
    // uint8_t *header_bytes = (uint8_t *)&header;
    // SCB_CleanDCache_by_Addr((uint32_t *)header_bytes, sizeof(header));
    // _uart->uart_write_udma(header_bytes, sizeof(header), _uart_dma_send);
    // while (_tx_busy)
    //     ;

    // xprintf("header sent, sending data...\n");

    // /* Send image data */
    // uint8_t *data_bytes = (uint8_t *)image->buffer;
    // // send each 4095 chunks
    // const int chunk_size = 4095;
    // size_t bytes_sent = 0;
    // while (bytes_sent < image->size)
    // {
    //     _tx_busy = true;
    //     int bytes_to_send = (image->size - bytes_sent) > chunk_size ? chunk_size : (image->size - bytes_sent);
    //     xprintf("%d/%d\n", bytes_sent, image->size);
    //     SCB_CleanDCache_by_Addr((uint32_t *)(data_bytes + bytes_sent), bytes_to_send);
    //     _uart->uart_write_udma(data_bytes + bytes_sent, bytes_to_send, _uart_dma_send);
    //     while (_tx_busy)
    //         ;
    //     bytes_sent += bytes_to_send;
    //     xprintf("%d/%d done\n", bytes_sent, image->size);
    // }

    // xprintf("data sent, sending footer...\n");
    // /* Send footer */
    // _tx_busy = true;
    // uint8_t *footer_bytes = (uint8_t *)&footer;
    // SCB_CleanDCache_by_Addr((uint32_t *)footer_bytes, sizeof(footer));
    // _uart->uart_write_udma(footer_bytes, sizeof(footer), _uart_dma_send);
    // while (_tx_busy)
    //     ;

    // xprintf("footer sent\n");
}

int main(void)
{
    static uint32_t frame_counter = 0;

    board_init();

    // hx_drv_scu_set_PB6_pinmux(SCU_PB6_PINMUX_UART1_RX, 0);
    // hx_drv_scu_set_PB7_pinmux(SCU_PB7_PINMUX_UART1_TX, 0);
    // hx_drv_uart_init(USE_DW_UART_1, HX_UART1_BASE);

    // _uart = hx_drv_uart_get_dev(USE_DW_UART_1);
    // if (_uart == NULL)
    // {
    //     return 0;
    // }

    // int ret = _uart->uart_open(UART_BAUDRATE_921600);
    // if (ret != 0)
    // {
    //     return 0;
    // }

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
    }
    if (mpix_transport_init(&g_uart_transport) != 0)
    {
        xprintf("UART transport init failed\n");
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
                                       .width = 640,
                                       .height = 480,
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
            /* Send binary image data */
            send_image_frame(frame_counter, &image);

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