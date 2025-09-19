/* SPDX-License-Identifier: Apache-2.0 */
#ifndef MPIX_TRANSPORT_UART_H
#define MPIX_TRANSPORT_UART_H

#include <mpix/transport.h>
#include <console_io.h>
#include <hx_drv_scu.h>
#include <hx_drv_uart.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Configuration for UART transport */
struct mpix_transport_uart_config {
	int port_id;              /* e.g. USE_DW_UART_0 */
	uint32_t baudrate;        /* e.g. UART_BAUDRATE_921600 */
	uint32_t tx_chunk;        /* DMA chunk size (<=4095 typical) */
	uint32_t send_buffer_size;/* ring buffer size for TX */
	uint32_t recv_buffer_size;/* ring buffer size for RX */
};

/* Provide a default configuration */
void mpix_transport_uart_config_default(struct mpix_transport_uart_config *cfg);

/* Create transport with custom configuration */
int mpix_transport_uart_create_with_config(struct mpix_transport *t, const struct mpix_transport_uart_config *cfg);

/* Backward compatible create (uses defaults) */
int mpix_transport_uart_create(struct mpix_transport *t);


#ifdef __cplusplus
}
#endif

#endif /* MPIX_TRANSPORT_UART_H */
