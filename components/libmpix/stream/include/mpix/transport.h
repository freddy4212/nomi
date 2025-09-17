/**
 * SPDX-License-Identifier: Apache-2.0
 * @defgroup mpix_transport_h stream/mpix_transport.h
 * @brief MPIX Transport Layer Abstraction
 * @{
 */
#ifndef MPIX_TRANSPORT_H
#define MPIX_TRANSPORT_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <errno.h>

#include <mpix/formats.h>
#include <mpix/image.h>
#include <mpix/ring.h>
#include <mpix/utils.h>

/**
 * @brief Forward declarations
 */

struct mpix_transport;

/**
 * @brief Transport interface operations
 */
struct mpix_transport_ops {
	/** Initialize transport */
	int (*init)(struct mpix_transport *transport);
	/** Send data (non-blocking) */
	int (*send)(struct mpix_transport *transport, const uint8_t *data, size_t size);
	/** Receive data (non-blocking) */
	int (*recv)(struct mpix_transport *transport, uint8_t *buffer, size_t size);
	/** Check if transport is ready for send */
	bool (*is_send_ready)(struct mpix_transport *transport);
	/** Check if data is available for receive */
	bool (*is_recv_ready)(struct mpix_transport *transport);
	/** Get send buffer space available */
	size_t (*get_send_space)(struct mpix_transport *transport);
	/** Get receive buffer data available */
	size_t (*get_recv_available)(struct mpix_transport *transport);
	/** Cleanup and deinitialize */
	void (*deinit)(struct mpix_transport *transport);
};

/**
 * @brief Transport layer abstraction
 *
 * Unified interface for WebSocket/UART/I2C/SPI
 */
struct mpix_transport {
	/** Transport operations */
	const struct mpix_transport_ops *ops;
	/** Hardware/protocol specific context */
	void *ctx;
	/** Send ring buffer (must use mpix_ring_init) */
	struct mpix_ring send_ring;
	/** Receive ring buffer (must use mpix_ring_init) */
	struct mpix_ring recv_ring;
	/** Send buffer (dynamically allocated) */
	uint8_t *send_buffer;
	/** Receive buffer (dynamically allocated) */
	uint8_t *recv_buffer;
	/** Send buffer size */
	size_t send_buffer_size;
	/** Receive buffer size */
	size_t recv_buffer_size;
	/** Transport state */
	enum {
		MPIX_TRANSPORT_STATE_DISCONNECTED,
		MPIX_TRANSPORT_STATE_CONNECTING,
		MPIX_TRANSPORT_STATE_CONNECTED,
		MPIX_TRANSPORT_STATE_ERROR
	} state;
	/** Error code if in error state */
	int error;
};

static inline int mpix_transport_init(struct mpix_transport *transport)
{
	if (!transport || !transport->ops || !transport->ops->init) {
		return -EINVAL;
	}
	return transport->ops->init(transport);
}
static inline int mpix_transport_send(struct mpix_transport *transport, const uint8_t *data,
				      size_t size)
{
	if (!transport || !transport->ops || !transport->ops->send) {
		return -EINVAL;
	}
	return transport->ops->send(transport, data, size);
}
static inline int mpix_transport_recv(struct mpix_transport *transport, uint8_t *buffer,
				      size_t size)
{
	if (!transport || !transport->ops || !transport->ops->recv) {
		return -EINVAL;
	}
	return transport->ops->recv(transport, buffer, size);
}
static inline bool mpix_transport_is_send_ready(struct mpix_transport *transport)
{
	if (!transport || !transport->ops || !transport->ops->is_send_ready) {
		return false;
	}
	return transport->ops->is_send_ready(transport);
}
static inline bool mpix_transport_is_recv_ready(struct mpix_transport *transport)
{
	if (!transport || !transport->ops || !transport->ops->is_recv_ready) {
		return false;
	}
	return transport->ops->is_recv_ready(transport);
}
static inline size_t mpix_transport_get_send_space(struct mpix_transport *transport)
{
	if (!transport || !transport->ops || !transport->ops->get_send_space) {
		return 0;
	}
	return transport->ops->get_send_space(transport);
}
static inline size_t mpix_transport_get_recv_available(struct mpix_transport *transport)
{
	if (!transport || !transport->ops || !transport->ops->get_recv_available) {
		return 0;
	}
	return transport->ops->get_recv_available(transport);
}
static inline void mpix_transport_deinit(struct mpix_transport *transport)
{
	if (!transport || !transport->ops || !transport->ops->deinit) {
		return;
	}
	transport->ops->deinit(transport);
}

#endif /** @} */
