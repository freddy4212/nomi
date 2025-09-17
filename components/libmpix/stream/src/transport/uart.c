/* SPDX-License-Identifier: Apache-2.0 */
/**
 * UART transport implementation using underlying platform DEV_UART with DMA (uart_write_udma).
 * Provides non-blocking chunked send API integrated with mpix_transport ring buffering.
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

/* Default constants (used for backward compatibility) */
#ifndef MPIX_UART_TX_CHUNK_DEFAULT
#define MPIX_UART_TX_CHUNK_DEFAULT 4095
#endif
#ifndef MPIX_UART_SEND_BUFFER_DEFAULT
#define MPIX_UART_SEND_BUFFER_DEFAULT (32 * 1024)
#endif
#ifndef MPIX_UART_RECV_BUFFER_DEFAULT
#define MPIX_UART_RECV_BUFFER_DEFAULT (8 * 1024)
#endif

/* Forward declaration for TX kick (needed by tx_done) */
static int _uart_kick_tx(struct mpix_transport *t);

/* NOTE: The underlying UART DMA API (uart_write_udma / uart_read_udma) only
 * supplies a callback function pointer without a user argument. We therefore
 * create small per-port wrapper callbacks and keep a context pointer array.
 * This allows multiple UART transports simultaneously (up to DW_UART_NUM). */
static struct mpix_uart_ctx *g_uart_ctx[DW_UART_NUM] = {0};

static void (*const _uart_tx_cb_table[DW_UART_NUM])(void);
static void (*const _uart_rx_cb_table[DW_UART_NUM])(void);


struct mpix_uart_ctx
{
	DEV_UART *dev;
	volatile bool tx_busy;
	struct mpix_transport *transport;
	int port_id;
	uint32_t baudrate;
	uint32_t tx_chunk;
	uint8_t *rx_staging;	  /* single-byte staging */
	uint32_t tx_inflight_len; /* bytes of current DMA chunk */
};

static void _uart_tx_done_common(struct mpix_uart_ctx *ctx)
{
	if (!ctx)
		return;
	if (ctx->transport && ctx->tx_inflight_len)
	{
		struct mpix_transport *t = ctx->transport;
		uint32_t remaining = ctx->tx_inflight_len;
		while (remaining)
		{
			size_t tailroom = mpix_ring_tailroom(&t->send_ring);
			size_t chunk = remaining < tailroom ? remaining : tailroom;
			(void)mpix_ring_read(&t->send_ring, chunk);
			remaining -= chunk;
		}
		ctx->tx_inflight_len = 0;
	}
	ctx->tx_busy = false;
	if (ctx->transport)
		_uart_kick_tx(ctx->transport);
}

/* RX DMA callback: push byte then restart */
static void _uart_rx_done_common(struct mpix_uart_ctx *ctx)
{
	if (!ctx || !ctx->rx_staging)
		return;
	struct mpix_transport *t = ctx->transport;
	if (!t)
		return;
	uint8_t *dst = mpix_ring_write(&t->recv_ring, 1);
	if (dst)
		*dst = ctx->rx_staging[0];
	if (ctx->dev)
	{
		int pid = ctx->port_id;
		if (pid < 0 || pid >= DW_UART_NUM)
			pid = 0;
		ctx->dev->uart_read_udma(ctx->rx_staging, 1, (void *)_uart_rx_cb_table[pid]);
	}
}

static void _uart_tx_done0(void) { _uart_tx_done_common(g_uart_ctx[0]); }
static void _uart_tx_done1(void) { _uart_tx_done_common(g_uart_ctx[1]); }
static void _uart_tx_done2(void) { _uart_tx_done_common(g_uart_ctx[2]); }
static void (*const _uart_tx_cb_table[DW_UART_NUM])(void) = {_uart_tx_done0, _uart_tx_done1, _uart_tx_done2};
static void _uart_rx_done0(void) { _uart_rx_done_common(g_uart_ctx[0]); }
static void _uart_rx_done1(void) { _uart_rx_done_common(g_uart_ctx[1]); }
static void _uart_rx_done2(void) { _uart_rx_done_common(g_uart_ctx[2]); }
static void (*const _uart_rx_cb_table[DW_UART_NUM])(void) = {_uart_rx_done0, _uart_rx_done1, _uart_rx_done2};

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
	ctx->dev = hx_drv_uart_get_dev(ctx->port_id);
	if (!ctx->dev)
		return -ENODEV;
	if (ctx->dev->uart_open(ctx->baudrate) != 0)
	{
		return -EIO;
	}
	ctx->tx_busy = false;
	t->state = MPIX_TRANSPORT_STATE_CONNECTED;
	/* Allocate RX staging if not yet */
	if (!ctx->rx_staging)
	{
		ctx->rx_staging = (uint8_t *)mpix_port_alloc(32); /* small aligned block */
		if (ctx->rx_staging)
			memset(ctx->rx_staging, 0, 32);
	}
	/* Register as active context (single instance support) */
	if (ctx->port_id >= 0 && ctx->port_id < DW_UART_NUM)
	{
		g_uart_ctx[ctx->port_id] = ctx;
	}
	/* Start first RX DMA (single byte) */
	if (ctx->rx_staging && ctx->dev)
	{
		int pid = ctx->port_id;
		if (pid < 0 || pid >= DW_UART_NUM)
			pid = 0;
		ctx->dev->uart_read_udma(ctx->rx_staging, 1, (void *)_uart_rx_cb_table[pid]);
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
	return mpix_ring_total_used(&t->recv_ring) > 0;
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

/* Internal: kick DMA if idle */
static int _uart_kick_tx(struct mpix_transport *t)
{
	struct mpix_uart_ctx *ctx = (struct mpix_uart_ctx *)t->ctx;
	if (ctx->tx_busy)
		return 0;
	/* Total bytes pending */
	size_t pending = mpix_ring_total_used(&t->send_ring);
	if (pending == 0)
		return 0;
	/* Contiguous bytes at tail */
	size_t tailroom = mpix_ring_tailroom(&t->send_ring);
	size_t chunk = pending < tailroom ? pending : tailroom;
	if (chunk > ctx->tx_chunk)
		chunk = ctx->tx_chunk;
	uint8_t *ptr = t->send_ring.data + t->send_ring.tail;
	SCB_CleanDCache_by_Addr((uint32_t *)ptr, chunk);
	ctx->tx_busy = true;
	ctx->tx_inflight_len = (uint32_t)chunk;
	/* Select per-port tx callback */
	int pid = ctx->port_id;
	if (pid < 0 || pid >= DW_UART_NUM)
		pid = 0;
	ctx->dev->uart_write_udma(ptr, chunk, (void *)_uart_tx_cb_table[pid]);
	return (int)chunk;
}

static int _uart_send(struct mpix_transport *t, const uint8_t *data, size_t size)
{
	if (!t || !data || size == 0)
		return -EINVAL;
	size_t written = 0;
	while (written < size)
	{
		size_t headroom = mpix_ring_headroom(&t->send_ring);
		if (headroom == 0)
			break; /* ring full */
		size_t chunk = size - written;
		if (chunk > headroom)
			chunk = headroom;
		uint8_t *dst = mpix_ring_write(&t->send_ring, chunk);
		if (!dst)
			break;
		memcpy(dst, data + written, chunk);
		written += chunk;
	}
	if (written > 0)
		_uart_kick_tx(t);
	return (int)written; /* 0 if full */
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
	if (ctx->rx_staging)
	{
		/* free staging */
		/* assuming mpix_port_alloc uses free-compatible allocator */
		mpix_port_free(ctx->rx_staging);
		ctx->rx_staging = NULL;
	}
	/* Buffers freed externally if desired (not freeing here to allow reuse) */
	/* Mark state */
	t->state = MPIX_TRANSPORT_STATE_DISCONNECTED;
}
