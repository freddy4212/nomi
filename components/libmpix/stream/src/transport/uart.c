/* SPDX-License-Identifier: Apache-2.0 */
/**
 * UART transport implementation with DMA-based non-blocking transmission.
 * Provides ring-buffered communication integrated with mpix_transport interface.
 */
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>

#include <mpix/transport.h>
#include <mpix/ring.h>
#include <mpix/utils.h>
#include <mpix/transport/uart.h>

#include <hx_drv_uart.h>
#include "board.h"

/* Configuration defaults */
#ifndef MPIX_UART_TX_CHUNK_DEFAULT
#define MPIX_UART_TX_CHUNK_DEFAULT 4095
#endif
#ifndef MPIX_UART_SEND_BUFFER_DEFAULT
#define MPIX_UART_SEND_BUFFER_DEFAULT (32 * 1024)
#endif
#ifndef MPIX_UART_RECV_BUFFER_DEFAULT
#define MPIX_UART_RECV_BUFFER_DEFAULT (8 * 1024)
#endif
#define MPIX_UART_DMA_BUFFER_SIZE 4096

/* Forward declarations */
static int _uart_kick_tx(struct mpix_transport *t);

/* Global context and callback arrays for DMA completion handling */
static struct mpix_uart_ctx *g_uart_ctx[DW_UART_NUM] = {0};
static uint8_t rx_staging[DW_UART_NUM];
static uint8_t tx_dma_buffer[DW_UART_NUM][MPIX_UART_DMA_BUFFER_SIZE];

struct mpix_uart_ctx
{
	DEV_UART *dev;					  /* UART device handle */
	volatile bool tx_busy;			  /* TX DMA in progress */
	volatile bool rx_busy;			  /* RX DMA in progress */
	struct mpix_transport *transport; /* Back reference to transport */
	int port_id;					  /* UART port identifier */
	uint32_t baudrate;				  /* Communication baud rate */
	uint32_t tx_chunk;				  /* Maximum TX chunk size */
	uint32_t rx_staging_size;		  /* RX staging buffer size */
	uint32_t tx_inflight_len;		  /* Current DMA transfer size */
};

/* DMA completion callbacks */
static void _uart_tx_done_common(struct mpix_uart_ctx *ctx);
static void _uart_rx_done_common(struct mpix_uart_ctx *ctx);

static void _uart_tx_done0(void) { _uart_tx_done_common(g_uart_ctx[0]); }
static void _uart_tx_done1(void) { _uart_tx_done_common(g_uart_ctx[1]); }
static void _uart_tx_done2(void) { _uart_tx_done_common(g_uart_ctx[2]); }

static void _uart_rx_done0(void) { _uart_rx_done_common(g_uart_ctx[0]); }
static void _uart_rx_done1(void) { _uart_rx_done_common(g_uart_ctx[1]); }
static void _uart_rx_done2(void) { _uart_rx_done_common(g_uart_ctx[2]); }

static void (*const _uart_tx_cb_table[DW_UART_NUM])(void) = {
	_uart_tx_done0, _uart_tx_done1, _uart_tx_done2};
static void (*const _uart_rx_cb_table[DW_UART_NUM])(void) = {
	_uart_rx_done0, _uart_rx_done1, _uart_rx_done2};

static void _uart_tx_done_common(struct mpix_uart_ctx *ctx)
{
	if (!ctx || !ctx->transport)
		return;

	/* Mark DMA as available and try to send next chunk */
	_uart_kick_tx(ctx->transport);
}

/* RX DMA callback: process received byte and restart DMA */
static void _uart_rx_done_common(struct mpix_uart_ctx *ctx)
{
	if (!ctx || !ctx->transport || !ctx->dev)
		return;

	struct mpix_transport *t = ctx->transport;
	ctx->rx_busy = false;

	/* Push received byte to ring buffer */
	uint8_t *dst = mpix_ring_write(&t->recv_ring, 1);
	if (dst)
		*dst = rx_staging[ctx->port_id];

	/* Restart single-byte RX DMA */
	int port_id = (ctx->port_id >= 0 && ctx->port_id < DW_UART_NUM) ? ctx->port_id : 0;
	ctx->rx_busy = true;
	ctx->dev->uart_read_udma(&rx_staging[ctx->port_id], 1, (void *)_uart_rx_cb_table[port_id]);
}

/* Forward declaration of ops */
static int _uart_init(struct mpix_transport *t);
static int _uart_send(struct mpix_transport *t, const uint8_t *data, size_t size);
static int _uart_recv(struct mpix_transport *t, uint8_t *buffer, size_t size);
static bool _uart_is_send_ready(struct mpix_transport *t);
static bool _uart_is_recv_ready(struct mpix_transport *t);
static size_t _uart_get_send_space(struct mpix_transport *t);
static size_t _uart_get_recv_available(struct mpix_transport *t);
static void _uart_deinit(struct mpix_transport *t);

static const struct mpix_transport_ops uart_ops = {
	.init = _uart_init,
	.send = _uart_send,
	.recv = _uart_recv,
	.is_send_ready = _uart_is_send_ready,
	.is_recv_ready = _uart_is_recv_ready,
	.get_send_space = _uart_get_send_space,
	.get_recv_available = _uart_get_recv_available,
	.deinit = _uart_deinit,
};

static inline size_t mpix_ring_free(struct mpix_ring *ring)
{
	return (ring->head >= ring->tail ? ring->size - ring->head + ring->tail : ring->tail - ring->head) - 1;
}

static inline size_t mpix_ring_used(struct mpix_ring *ring)
{
	return (ring->head >= ring->tail ? ring->head - ring->tail : ring->size - ring->tail + ring->head);
}
static inline size_t mpix_ring_push(struct mpix_ring *ring, const uint8_t *data, size_t size)
{
	if (!data || size == 0)
	{
		return 0;
	}
	size_t free = mpix_ring_free(ring);
	if (free == 0)
	{
		return 0;
	}
	size = size > free ? free : size;
	for (size_t i = 0; i < size; i++)
	{
		ring->data[ring->head] = data[i];
		ring->head = (ring->head + 1) % ring->size;
	}
	return size;
}

static inline size_t mpix_ring_pop(struct mpix_ring *ring, uint8_t *data, size_t size)
{
	if (!data || size == 0)
	{
		return 0;
	}

	size_t used = mpix_ring_used(ring);

	size = size > used ? used : size;

	for (size_t i = 0; i < size; i++)
	{
		data[i] = ring->data[ring->tail];
		ring->tail = (ring->tail + 1) % ring->size;
	}

	return size;
}

void mpix_transport_uart_config_default(struct mpix_transport_uart_config *cfg)
{
	if (!cfg)
		return;
	cfg->port_id = USE_DW_UART_0;
	cfg->baudrate = UART_BAUDRATE_921600;
	cfg->tx_chunk = MPIX_UART_TX_CHUNK_DEFAULT;
	cfg->send_buffer_size = MPIX_UART_SEND_BUFFER_DEFAULT;
	cfg->recv_buffer_size = MPIX_UART_RECV_BUFFER_DEFAULT;
}

int mpix_transport_uart_create_with_config(struct mpix_transport *t, const struct mpix_transport_uart_config *cfg)
{
	if (!t || !cfg)
		return -EINVAL;
	memset(t, 0, sizeof(*t));
	struct mpix_uart_ctx *ctx = (struct mpix_uart_ctx *)mpix_port_alloc(sizeof(struct mpix_uart_ctx));
	if (!ctx)
		return -ENOMEM;
	memset(ctx, 0, sizeof(*ctx));
	ctx->port_id = cfg->port_id;
	ctx->baudrate = cfg->baudrate;
	ctx->tx_chunk = cfg->tx_chunk;
	ctx->rx_staging_size = 1; /* Keep 1-byte staging for immediate response */
	ctx->transport = t;
	t->ctx = ctx;
	t->ops = &uart_ops;
	/* Allocate buffers using config */
	t->send_buffer_size = cfg->send_buffer_size;
	t->recv_buffer_size = cfg->recv_buffer_size;
	t->send_buffer = (uint8_t *)mpix_port_alloc(t->send_buffer_size);
	t->recv_buffer = (uint8_t *)mpix_port_alloc(t->recv_buffer_size);
	if (!t->send_buffer || !t->recv_buffer)
	{
		return -ENOMEM;
	}
	mpix_ring_init(&t->send_ring, t->send_buffer, t->send_buffer_size);
	mpix_ring_init(&t->recv_ring, t->recv_buffer, t->recv_buffer_size);
	t->state = MPIX_TRANSPORT_STATE_DISCONNECTED;
	return 0;
}

int mpix_transport_uart_create(struct mpix_transport *t)
{
	struct mpix_transport_uart_config def;
	mpix_transport_uart_config_default(&def);
	return mpix_transport_uart_create_with_config(t, &def);
}

static int _uart_init(struct mpix_transport *t)
{
	if (!t || !t->ctx)
		return -EINVAL;
	struct mpix_uart_ctx *ctx = (struct mpix_uart_ctx *)t->ctx;

	if (ctx->port_id == USE_DW_UART_1)
	{
		hx_drv_scu_set_PB6_pinmux(SCU_PB6_PINMUX_UART1_RX, 0);
		hx_drv_scu_set_PB7_pinmux(SCU_PB7_PINMUX_UART1_TX, 0);
		hx_drv_uart_init(USE_DW_UART_1, HX_UART1_BASE);
	}

	ctx->dev = hx_drv_uart_get_dev(ctx->port_id);
	if (!ctx->dev)
		return -ENODEV;

	if (ctx->dev->uart_open(ctx->baudrate) != 0)
	{
		return -EIO;
	}

	ctx->tx_busy = false;
	ctx->rx_busy = false;
	t->state = MPIX_TRANSPORT_STATE_CONNECTED;

	/* Register as active context (single instance support) */
	if (ctx->port_id >= 0 && ctx->port_id < DW_UART_NUM)
	{
		g_uart_ctx[ctx->port_id] = ctx;
	}

	/* Start first RX DMA (single byte for now) */
	if (ctx->dev)
	{
		int pid = ctx->port_id;
		if (pid < 0 || pid >= DW_UART_NUM)
			pid = 0;
		ctx->rx_busy = true;
		ctx->dev->uart_read_udma(&rx_staging[ctx->port_id], 1, (void *)_uart_rx_cb_table[pid]);
	}

	return 0;
}

static bool _uart_is_send_ready(struct mpix_transport *t)
{
	(void)t;
	return true; /* ring buffering handles load */
}
static bool _uart_is_recv_ready(struct mpix_transport *t)
{
	if (!t)
		return false;
	size_t available = mpix_ring_total_used(&t->recv_ring);

	return available > 0;
}
static size_t _uart_get_send_space(struct mpix_transport *t)
{
	if (!t)
		return 0;
	size_t used = mpix_ring_total_used(&t->send_ring);
	return t->send_ring.size - used;
}
static size_t _uart_get_recv_available(struct mpix_transport *t)
{
	if (!t)
		return 0;
	return mpix_ring_total_used(&t->recv_ring);
}

/* Start DMA transmission if idle and data is available */
static int _uart_kick_tx(struct mpix_transport *t)
{
	struct mpix_uart_ctx *ctx = (struct mpix_uart_ctx *)t->ctx;

	size_t used = mpix_ring_used(&t->send_ring);
	size_t chunk_size = used > MPIX_UART_DMA_BUFFER_SIZE ? MPIX_UART_DMA_BUFFER_SIZE : used;
	if (chunk_size == 0)
	{
		ctx->tx_busy = false;
		return 0;
	}

	/* Start DMA transmission */
	ctx->tx_busy = true;
	ctx->tx_inflight_len = chunk_size;
	mpix_ring_pop(&t->send_ring, tx_dma_buffer[ctx->port_id], chunk_size);
	SCB_CleanDCache_by_Addr((uint32_t *)tx_dma_buffer[ctx->port_id], chunk_size);
	ctx->dev->uart_write_udma(tx_dma_buffer[ctx->port_id], chunk_size, (void *)_uart_tx_cb_table[ctx->port_id]);

	return (int)chunk_size;
}

static int _uart_send(struct mpix_transport *t, const uint8_t *data, size_t size)
{
	if (!t || !data || size == 0)
		return -EINVAL;

	struct mpix_uart_ctx *ctx = (struct mpix_uart_ctx *)t->ctx;
	if (!ctx)
		return -EINVAL;

	size_t written = 0;
	while (written < size)
	{
		written += mpix_ring_push(&t->send_ring, data + written, size - written);
		if (!ctx->tx_busy)
			_uart_kick_tx(t);
	}

	return (int)written;
}

static int _uart_recv(struct mpix_transport *t, uint8_t *buffer, size_t size)
{
	if (!t || !buffer || size == 0)
		return -EINVAL;
	size_t avail = mpix_ring_total_used(&t->recv_ring);
	if (avail == 0)
		return 0;
	if (size > avail)
		size = avail;

	size_t copied = 0;
	while (copied < size)
	{
		size_t tailroom = mpix_ring_tailroom(&t->recv_ring);
		size_t chunk = size - copied;
		if (chunk > tailroom)
			chunk = tailroom;
		uint8_t *src = mpix_ring_read(&t->recv_ring, chunk);
		if (!src)
			break; /* should not happen */
		memcpy(buffer + copied, src, chunk);
		copied += chunk;
	}

	return (int)copied;
}

static void _uart_deinit(struct mpix_transport *t)
{
	if (!t || !t->ctx)
		return;
	struct mpix_uart_ctx *ctx = (struct mpix_uart_ctx *)t->ctx;
	if (ctx->dev)
	{
		ctx->dev->uart_close();
	}

	/* Buffers freed externally if desired (not freeing here to allow reuse) */
	/* Mark state */
	t->state = MPIX_TRANSPORT_STATE_DISCONNECTED;
}