@page new_operations Implement new conversion functions
@brief Guide for implementing new operations within an existying operation family

Each libmpix operation derive from a base operation @ref mpix_base_op.

This struct store all information needed to keeps track of the conversion progress
(image dimension, line position, ring buffer, the input/output pixel format).

In addition, every operation family typically defines custom helpers that further facilitates the
definition of a new operation.

Finally, operations are submitted by a `MPIX_REGISTER_..._OP()` macro that will make it available
in the associated `mpix_image_...()` function.

## Example: add a new RGB565 endianess conversion function

For instance, for an operation converting between RGB565 big-endian and RGB565 little-endian:

```c
void mpix_convert_rgb565be_to_rgb565le(const uint8_t *src, uint8_t *dst, uint16_t width)
{
        for (size_t i = 0, o = 0, w = 0; w < width; w++, dst += 2, src += 2) {
		dst[0] = src[1];
		dst[1] = src[0];
        }
}
MPIX_REGISTER_CONVERT_OP(rgb565be_rgb565le, mpix_convert_rgb565be_to_rgb565le, RGB565X, RGB565);
```

Thanks to the @ref MPIX_REGISTER_CONVERT_OP() macro to include this operation in a table,
and the @ref mpix_image_convert() function that searches that table, this is enough.
The application will be able to call it from the application like this:

```c
mpix_image_from_buf(&img, buf, sizeof(buf), MPIX_FMT_RGB565X, width, height);
mpix_image_convert(&img, MPIX_FMT_RGB565);
```

## Multiple operations per function

As seen above, the implementation is just an endianness swap, so the implementation can be common
for many differeent types:

```c
void mpix_convert_byteswap_raw16(const uint8_t *src, uint8_t *dst, uint16_t width)
{
        for (size_t i = 0, o = 0, w = 0; w < width; w++, dst += 2, src += 2) {
		dst[0] = src[1];
		dst[1] = src[0];
        }
}
MPIX_REGISTER_CONVERT_OP(rgb565be_rgb565le, mpix_convert_byteswap_raw16, RGB565X, RGB565);
MPIX_REGISTER_CONVERT_OP(rgb565le_rgb565be, mpix_convert_byteswap_raw16, RGB565, RGB565X);
MPIX_REGISTER_CONVERT_OP(yuyv_uyvy, mpix_convert_byteswap_raw16, YUYV, UYVY);
MPIX_REGISTER_CONVERT_OP(uyvy_yuyv, mpix_convert_byteswap_raw16, UYVY, YUYV);
[...]
```

Each type of operation have their own function type, and own parameter for the
`MPIX_REGISTER_..._OP()`, documented in the respective `mpix/op_....h` part of the API.
