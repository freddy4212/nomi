/* Generated with /home/blakesu/2.mylibmpix/libmpix/scripts/genlist.py */

#define MPIX_LIST_CONVERT_OP \
	&mpix_convert_op_rgb24_rgb24, \
	&mpix_convert_op_rgb24_rgb332, \
	&mpix_convert_op_rgb332_rgb24, \
	&mpix_convert_op_rgb24_rgb565x, \
	&mpix_convert_op_rgb24_rgb565, \
	&mpix_convert_op_rgb565x_rgb24, \
	&mpix_convert_op_rgb565_rgb24, \
	&mpix_convert_op_yuv24_rgb24, \
	&mpix_convert_op_rgb24_yuv24, \
	&mpix_convert_op_yuv24_yuyv, \
	&mpix_convert_op_yuyv_yuv24, \
	&mpix_convert_op_rgb24_yuyv, \
	&mpix_convert_op_yuyv_rgb24, \
	&mpix_convert_op_grey_rgb24, \
	&mpix_convert_op_rgb24_grey, \
	NULL

#define MPIX_LIST_CORRECTION_OP \
	&mpix_correction_op_blc_bggr8, \
	&mpix_correction_op_blc_sbggr8, \
	&mpix_correction_op_blc_srggb8, \
	&mpix_correction_op_blc_sgrbg8, \
	&mpix_correction_op_blc_sgbrg8, \
	&mpix_correction_op_blc_grey, \
	&mpix_correction_op_blc_rgb24, \
	&mpix_correction_op_wb_rgb24, \
	&mpix_correction_op_gc_bggr8, \
	&mpix_correction_op_gc_sbggr8, \
	&mpix_correction_op_gc_srggb8, \
	&mpix_correction_op_gc_sgrbg8, \
	&mpix_correction_op_gc_sgbrg8, \
	&mpix_correction_op_gc_grey, \
	&mpix_correction_op_gc_rgb24, \
	NULL

#define MPIX_LIST_DEBAYER_OP \
	&mpix_debayer_op_srggb8_3x3, \
	&mpix_debayer_op_sgbrg8_3x3, \
	&mpix_debayer_op_sbggr8_3x3, \
	&mpix_debayer_op_bggr8_3x3, \
	&mpix_debayer_op_sgrbg8_3x3, \
	&mpix_debayer_op_srggb8_2x2, \
	&mpix_debayer_op_sgbrg8_2x2, \
	&mpix_debayer_op_sbggr8_2x2, \
	&mpix_debayer_op_bggr8_2x2, \
	&mpix_debayer_op_sgrbg8_2x2, \
	&mpix_debayer_op_srggb8_1x1, \
	&mpix_debayer_op_sbggr8_1x1, \
	&mpix_debayer_op_sgbrg8_1x1, \
	&mpix_debayer_op_sgrbg8_1x1, \
	NULL

#define MPIX_LIST_JPEG_OP \
	&mpix_jpeg_op_encode_yuyv, \
	NULL

#define MPIX_LIST_KERNEL_3X3_OP \
	&mpix_kernel_3x3_op_identity_rgb24, \
	&mpix_kernel_3x3_op_edge_detect_rgb24, \
	&mpix_kernel_3x3_op_gaussian_blur_rgb24, \
	&mpix_kernel_3x3_op_sharpen_rgb24, \
	&mpix_kernel_3x3_op_denoise_rgb24, \
	NULL

#define MPIX_LIST_KERNEL_5X5_OP \
	&mpix_kernel_5x5_op_identity_rgb24, \
	&mpix_kernel_5x5_op_gaussian_blur_rgb24, \
	&mpix_kernel_5x5_op_sharpen_rgb24, \
	&mpix_kernel_5x5_op_denoise_rgb24, \
	NULL

#define MPIX_LIST_PALETTE_OP \
	&mpix_palette_op_rgb24_palette1, \
	&mpix_palette_op_palette1_rgb24, \
	&mpix_palette_op_rgb24_palette2, \
	&mpix_palette_op_palette2_rgb24, \
	&mpix_palette_op_rgb24_palette3, \
	&mpix_palette_op_rgb24_palette4, \
	&mpix_palette_op_palette3_rgb24, \
	&mpix_palette_op_palette4_rgb24, \
	&mpix_palette_op_rgb24_palette5, \
	&mpix_palette_op_rgb24_palette6, \
	&mpix_palette_op_rgb24_palette7, \
	&mpix_palette_op_rgb24_palette8, \
	&mpix_palette_op_palette5_rgb24, \
	&mpix_palette_op_palette6_rgb24, \
	&mpix_palette_op_palette7_rgb24, \
	&mpix_palette_op_palette8_rgb24, \
	NULL

#define MPIX_LIST_QOI_OP \
	&mpix_qoi_op_encode_rgb24, \
	NULL

#define MPIX_LIST_RESIZE_OP \
	&mpix_resize_op_rgb24, \
	&mpix_resize_op_yuv24, \
	&mpix_resize_op_rgb565, \
	&mpix_resize_op_rgb565x, \
	&mpix_resize_op_grey, \
	&mpix_resize_op_rgb332, \
	NULL
