/**
 * SPDX-License-Identifier: Apache-2.0
 * @internal
 */
#ifndef MPIX_RING_H
#define MPIX_RING_H

#include <stdbool.h>
#include <string.h>

#include <mpix/utils.h>

/**
 * @brief Ring buffer of pixels
 *
 * Store the data betwen a previous operation and the next operation.
 */
struct mpix_ring {
	/** Pointer to the buffer that stores the data */
	uint8_t *data;
	/** Total size of the buffer */
	size_t size;
	/** Position of the writing head where data is inserted */
	size_t head;
	/** Position of the reading tail where data is read and removed */
	size_t tail;
	/** Position of the peeking tail where data is read ahead of the tail */
	size_t peek;
	/** Flag to tell apart between full and empty when head == tail */
	bool full;
};

static inline void mpix_ring_init(struct mpix_ring *ring, uint8_t *buf, size_t size)
{
	memset(ring, 0x00, sizeof(*ring));
	ring->data = buf;
	ring->size = size;
}

static inline bool mpix_ring_is_full(struct mpix_ring *ring)
{
	return ring->full;
}

static inline bool mpix_ring_is_empty(struct mpix_ring *ring)
{
	return ring->head == ring->tail && !ring->full;
}

static inline size_t mpix_ring_headroom(struct mpix_ring *ring)
{
	if (ring->head < ring->tail) {
		/* [::::H      T::::]
		 *      ^^^^^^^
		 */
		return ring->tail - ring->head;
	}
	if (ring->tail < ring->head) {
		/* [    T::::::H    ]
		 *             ^^^^^
		 */
		return ring->size - ring->head;
	}
	if (mpix_ring_is_empty(ring)) {
		/* [          TH    ]
		 *             ^^^^^
		 */
		return ring->size - ring->head;
	} else {
		/* [::::::::::HT::::]
		 */
		return 0;
	}
}

static inline size_t mpix_ring_tailroom(struct mpix_ring *ring)
{
	if (ring->head < ring->tail) {
		/* [::::H      T::::]
		 *             ^^^^^
		 */
		return ring->size - ring->tail;
	}
	if (ring->tail < ring->head) {
		/* [    T::::::H    ]
		 *      ^^^^^^^
		 */
		return ring->head - ring->tail;
	}
	if (mpix_ring_is_full(ring)) {
		/* [::::::::::HT::::]
		 *             ^^^^^
		 */
		assert(ring->head == ring->tail);
		return ring->size - ring->tail;
	} else {
		/* [          TH    ]
		 */
		assert(ring->head == ring->tail);
		return 0;
	}
}

static inline size_t mpix_ring_peekroom(struct mpix_ring *ring)
{
	if (ring->head < ring->tail && ring->tail <= ring->peek) {
		/* [::::H      T:P::]
		 *               ^^^
		 */
		return ring->size - ring->peek;
	}
	if (ring->peek < ring->head && ring->head < ring->tail) {
		/* [:P::H      T::::]
		 *   ^^^
		 */
		return ring->head - ring->peek;
	}
	if (ring->tail <= ring->peek && ring->peek < ring->head) {
		/* [    T:P::::H    ]
		 *        ^^^^^
		 */
		return ring->head - ring->peek;
	}
	if (mpix_ring_is_full(ring) && ring->tail <= ring->peek) {
		/* [::::::::::HT:P::]
		 *               ^^^
		 */
		assert(ring->head == ring->tail);
		return ring->size - ring->peek;
	}
	if (mpix_ring_is_full(ring) && ring->peek <= ring->head) {
		/* [::P:::::::HT::::]
		 *    ^^^^^^^^
		 */
		assert(ring->head == ring->tail);
		return ring->head - ring->peek;
	}
	return 0;
}

static inline size_t mpix_ring_total_used(struct mpix_ring *ring)
{
	if (ring->head < ring->tail) {
		/* [::::H      T::::]
		 *  ^^^^^      ^^^^^
		 */
		return ring->head + ring->size - ring->tail;
	}
	if (ring->tail < ring->head) {
		/* [    T::::::H    ]
		 *      ^^^^^^^^
		 */
		return ring->head - ring->tail;
	}
	if (mpix_ring_is_full(ring)) {
		/* [::::::::::HT::::]
		 *  ^^^^^^^^^^^^^^^^
		 */
		assert(ring->head == ring->tail);
		return ring->size;
	} else {
		/* [          TH    ]
		 */
		assert(ring->head == ring->tail);
		return 0;
	}
}

static inline uint8_t *mpix_ring_write(struct mpix_ring *ring, size_t size)
{
	uint8_t *data = ring->data + ring->head;

	if (mpix_ring_headroom(ring) < size) {
		MPIX_ERR("Not enough room (%u) to write %u bytes", mpix_ring_headroom(ring), size);
		return NULL;
	}
	ring->head = (ring->head + size) % ring->size;
	ring->peek = ring->tail;
	ring->full = (ring->head == ring->tail);
	return data;
}

static inline uint8_t *mpix_ring_read(struct mpix_ring *ring, size_t size)
{
	uint8_t *data = ring->data + ring->tail;

	if (mpix_ring_tailroom(ring) < size) {
		return NULL;
	}
	ring->tail = (ring->tail + size) % ring->size;
	ring->peek = ring->tail;
	ring->full = 0;
	return data;
}

static inline uint8_t *mpix_ring_peek(struct mpix_ring *ring, size_t size)
{
	uint8_t *data = ring->data + ring->peek;

	if (mpix_ring_peekroom(ring) < size) {
		return NULL;
	}
	ring->peek = (ring->peek + size) % ring->size;
	return data;
}

static inline void mpix_ring_dump(struct mpix_ring *ring)
{
	MPIX_INF("ring %s full, size %u, head %u (#%u), tail %u (#%u), peek %u (#%u)",
		ring->full ? "is" : "not", ring->size, mpix_ring_headroom(ring), ring->head,
		mpix_ring_tailroom(ring), ring->tail, mpix_ring_peekroom(ring), ring->peek);
}

#endif
