@page how_to_qoi How to QOI-encode images
@brief Uses libmpix to encode image to the QOI format.

The [Quite Ok Image Format (QOI Format)](https://qoiformat.org/) a lossless compression codec with
ratios close to PNG at a fraction of the complexity. This makes it a good candidate for use in
low-power platforms such as microcontrollers.

### How to encode QOI images with libmpix

First load a buffer into an image struct, in RGB format:

```c
struct mpix_image img;

mpix_image_from_buf(&img, buf, sizeof(buf), 640, 480, MPIX_FMT_RGB24);
```

If the image is not in RGB format, you may then need ot add an extra
format conversion step (@ref how_to_convert).

Then encode the image to the QOI format:

```c
mpix_image_qoi_encode(&img);
```
