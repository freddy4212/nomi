# Introduction

The **libmpix** is an open-source
([Apache 2.0](https://github.com/libmpix/libmpix/blob/main/LICENSE))
library to work with image data on microcontrollers:
pixel format conversion, debayer, blur, sharpen, color correction, resizing...

It pipelines multiple operations together, eliminating the intermediate buffers.
This allows larger resolution to fit in constrained systems, without compromising performance.

It provides a C implementation of the classical operations of an imaging pipeline, and plans to
add support for hardware-optimized implementations leveraging SIMD instructions like
[ARM Helium](https://www.arm.com/technologies/helium) present on ARM Cortex-M55/M85.

It is born out of a
[proposal for the Zephyr RTOS](https://github.com/zephyrproject-rtos/zephyr/issues/86669)
and is now a stand-alone project with tier-1 support for Zephyr.

Features:

- Simple zero-copy and pipelined engine, with low runtime overhead,
- Reduces memory overhead (can process 1 MB of data with only 5 kB of RAM)
- [POSIX support](https://github.com/libmpix/libmpix_example_posix) (Linux/BSD/MacOS),
  [Zephyr support](https://github.com/libmpix/libmpix_example_zephyr)

Upcoming:

- [SIMD](https://www.arm.com/technologies/helium) acceleration, 2.5D GPUs acceleration
- [MicroPython](https://micropython.org/) support,
  [Lua](https://lua.org/) support

C API:

```c
#include <mpix/image.h>

struct mpix_image img;

mpix_image_from_buf(&img, src, sizeof(src), MPIX_FORMAT_RGB24);
mpix_image_kernel(&img, MPIX_KERNEL_DENOISE, 5);
mpix_image_kernel(&img, MPIX_KERNEL_SHARPEN, 3);
mpix_image_convert(&img, MPIX_FMT_YUYV);
mpix_image_to_buf(&img, dst, sizeof(dst));

return img.err;
```
