#include <stdio.h>
#include "WE2_device.h"
#include "WE2_core.h"
#include "board.h"
#include "xprintf.h"

/* FreeRTOS includes */
#include "FreeRTOS.h"
#include "task.h"

#include <mpix/image.h>
#include <mpix/formats.h>
#include <mpix/stats.h>
#include <mpix/auto.h>
#include <mpix/op_correction.h>
#include <mpix/op_kernel.h>
#include <mpix/op_resize.h>
#include <mpix/op_palettize.h>
#include <mpix/port.h>


/* Test image dimensions - optimized for limited RAM */
#define TEST_WIDTH  320
#define TEST_HEIGHT 240

/* Number of iterations for each benchmark */
#define BENCH_ITERATIONS 5

/* Buffer size */
#define BUFFER_SIZE (TEST_WIDTH * TEST_HEIGHT * 3)

/* Test buffers */
__attribute__((section(".bss.elHeap")))
static uint8_t test_buffer[BUFFER_SIZE];
__attribute__((section(".bss.elHeap")))
static uint8_t output_buffer[BUFFER_SIZE];
__attribute__((section(".bss.elHeap")))
static uint8_t palette_buffer[256 * 3];

/* Function prototypes */
static void benchmark_init(void);
static void benchmark_debayer(void);
static void benchmark_resize(void);
static void benchmark_stats(void);
static void benchmark_kernel_operations(void);
static void benchmark_color_correction(void);
static void benchmark_palettization(void);
static void benchmark_encoding(void);
static void print_benchmark_header(const char *test_name);
static void print_benchmark_result(const char *operation, const char *format, int width, int height,
				   uint64_t time_us);
static void benchmark_convert(void);
static void fill_test_pattern(uint8_t *buffer, int width, int height, uint32_t fourcc);

/* FreeRTOS task functions */
static void benchmark_task(void *pvParameters);

/* Task configuration */
#define BENCHMARK_TASK_STACK_SIZE   (8192)
#define BENCHMARK_TASK_PRIORITY     (tskIDLE_PRIORITY + 1)

int main(void)
{
	/* Initialize hardware */
	board_init();

	xprintf("\n");
	xprintf("=====================================\n");
	xprintf("  libmpix Performance Benchmark\n");
	xprintf("  Target: Grove Vision AI Module V2 (WE2)\n");
	xprintf("  FreeRTOS Task-based Implementation\n");
	xprintf("=====================================\n");
	xprintf("\n");

	/* Create the benchmark task */
	BaseType_t xResult = xTaskCreate(
		benchmark_task,                    /* Task function */
		"BenchmarkTask",                   /* Task name */
		BENCHMARK_TASK_STACK_SIZE,         /* Stack size in words */
		NULL,                              /* Task parameters */
		BENCHMARK_TASK_PRIORITY,           /* Task priority */
		NULL                               /* Task handle */
	);

	if (xResult != pdPASS) {
		xprintf("Failed to create benchmark task!\n");
		while (1) {
			board_delay_ms(1000);
		}
	}

	xprintf("Starting FreeRTOS scheduler...\n");

	/* Start the FreeRTOS scheduler */
	vTaskStartScheduler();

	/* Should never reach here if the scheduler starts successfully */
	xprintf("ERROR: Scheduler failed to start!\n");
	while (1) {
		board_delay_ms(1000);
	}

	return 0;
}

/* Benchmark task implementation */
static void benchmark_task(void *pvParameters)
{
	(void)pvParameters; /* Unused parameter */

	xprintf("Benchmark task started\n");

	/* Initialize benchmark */
	benchmark_init();

	/* Run benchmarks */
	benchmark_stats();
	vTaskDelay(pdMS_TO_TICKS(100)); /* Allow log buffer to flush */

	benchmark_debayer();
	vTaskDelay(pdMS_TO_TICKS(100));

	benchmark_convert();
	vTaskDelay(pdMS_TO_TICKS(100));

	benchmark_resize();
	vTaskDelay(pdMS_TO_TICKS(100));

	benchmark_kernel_operations();
	vTaskDelay(pdMS_TO_TICKS(100));

	benchmark_color_correction();
	vTaskDelay(pdMS_TO_TICKS(100));

	benchmark_palettization();
	vTaskDelay(pdMS_TO_TICKS(100));

	benchmark_encoding();
	vTaskDelay(pdMS_TO_TICKS(100));

	xprintf("\n");
	xprintf("=====================================\n");
	xprintf("  Benchmark Complete\n");
	xprintf("=====================================\n");

	/* Task completed, suspend itself */
	while (1) {
		vTaskDelay(pdMS_TO_TICKS(10000));
	}
}

static void benchmark_init(void)
{
	xprintf("Initializing test patterns...\n");

	/* Fill test buffer with Bayer pattern */
	fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_BGGR8);

	/* Test what formats are supported */
	struct mpix_image test_img;

	xprintf("Testing format support:\n");

	/* Test RGB24 */
	mpix_image_from_buf(&test_img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
			    MPIX_FMT_RGB24);
	xprintf("- RGB24: init_err=%d\n", test_img.err);

	/* Test BGGR8 */
	mpix_image_from_buf(&test_img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
			    MPIX_FMT_BGGR8);
	xprintf("- BGGR8: init_err=%d\n", test_img.err);

	xprintf("Initialization complete.\n\n");
}

static void benchmark_stats(void)
{
	struct mpix_image img;
	struct mpix_stats stats;
	uint64_t start_time, end_time;

	print_benchmark_header("Image Statistics");

	/* Initialize total time */
	uint64_t total_time = 0;

	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_BGGR8);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_BGGR8);

		start_time = mpix_port_get_uptime_us();
		mpix_image_stats(&img, &stats);
		end_time = mpix_port_get_uptime_us();

		total_time += end_time - start_time;
	}

	uint64_t avg_time = total_time / BENCH_ITERATIONS;
	print_benchmark_result("Stats", "BGGR8", TEST_WIDTH, TEST_HEIGHT, avg_time);
}

static void benchmark_debayer(void)
{
	struct mpix_image img;
	uint64_t start_time, end_time;

	print_benchmark_header("Debayering");

	/* Initialize total time for 2x2 debayer */
	uint64_t total_time_2x2 = 0;

	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		/* Fill with fresh Bayer pattern for each iteration */
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_BGGR8);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_BGGR8);

		if (img.err != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s (init_err=%d) |\n", "Debayer 2x2", "BGGR8",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED", img.err);
			break;
		}

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_debayer(&img, 2);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s (err=%d) |\n", "Debayer 2x2", "BGGR8",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED", result);
			break;
		}
		total_time_2x2 += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Debayer 2x2", "BGGR8", TEST_WIDTH, TEST_HEIGHT,
					       total_time_2x2 / BENCH_ITERATIONS);
		}
	}

	/* Initialize total time for 3x3 debayer */
	uint64_t total_time_3x3 = 0;

	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		/* Fill with fresh Bayer pattern for each iteration */
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_BGGR8);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_BGGR8);

		if (img.err != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s (init_err=%d) |\n", "Debayer 3x3", "BGGR8",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED", img.err);
			break;
		}

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_debayer(&img, 3);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s (err=%d) |\n", "Debayer 3x3", "BGGR8",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED", result);
			break;
		}
		total_time_3x3 += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Debayer 3x3", "BGGR8", TEST_WIDTH, TEST_HEIGHT,
					       total_time_3x3 / BENCH_ITERATIONS);
		}
	}
}

static void benchmark_convert(void)
{
	struct mpix_image img;
	uint64_t start_time, end_time;

	print_benchmark_header("Format Conversion");

	/* Test RGB24 to YUYV conversion */
	uint64_t rgb_to_yuyv_total_time = 0;
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_convert(&img, MPIX_FMT_YUYV);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s (err=%d) |\n", "RGB24->YUYV", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED", result);
			break;
		}
		rgb_to_yuyv_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("RGB24->YUYV", "YUYV", TEST_WIDTH, TEST_HEIGHT,
					       rgb_to_yuyv_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test RGB24 to MPIX_FMT_GREY conversion */
	uint64_t rgb_to_grey_total_time = 0;
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_convert(&img, MPIX_FMT_GREY);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s (err=%d) |\n", "RGB24->GREY", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED", result);
			break;
		}
		rgb_to_grey_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("RGB24->GREY", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       rgb_to_grey_total_time / BENCH_ITERATIONS);
		}
	}
}

static void benchmark_resize(void)
{
	struct mpix_image img;
	uint64_t start_time, end_time;

	print_benchmark_header("Resize Operations");

	/* Initialize total time */
	uint64_t total_time = 0;

	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		/* Fill buffer with RGB data for resize test */
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_resize(&img, MPIX_RESIZE_SUBSAMPLING, TEST_WIDTH / 2,
					       TEST_HEIGHT / 2);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Resize (Subsampling)", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Resize (Subsampling)", "RGB24", TEST_WIDTH,
					       TEST_HEIGHT, total_time / BENCH_ITERATIONS);
		}
	}

	/* Test Binning resize */
	total_time = 0;
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_resize(&img, MPIX_RESIZE_BINNING, TEST_WIDTH / 2,
					       TEST_HEIGHT / 2);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s (err=%d) |\n", "Resize (Binning)",
			       "RGB24", TEST_WIDTH, TEST_HEIGHT, "FAILED", result);
			break;
		}
		total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Resize (Binning)", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       total_time / BENCH_ITERATIONS);
		}
	}
}

static void benchmark_kernel_operations(void)
{
	struct mpix_image img;
	uint64_t start_time, end_time;
	uint64_t gaussian_total_time = 0;
	uint64_t sharpen_total_time = 0;
	uint64_t edge_total_time = 0;
	uint64_t denoise_total_time = 0;
	uint64_t identity_total_time = 0;
	uint64_t gaussian5_total_time = 0;
	uint64_t sharpen5_total_time = 0;
	uint64_t edge5_total_time = 0;
	uint64_t denoise5_total_time = 0;
	uint64_t identity5_total_time = 0;

	print_benchmark_header("Kernel Operations");

	/* Test Gaussian Blur */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_kernel(&img, MPIX_KERNEL_GAUSSIAN_BLUR, 3);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s (err=%d) |\n", "Gaussian Blur 3x3",
			       "RGB24", TEST_WIDTH, TEST_HEIGHT, "FAILED", result);
			break;
		}
		gaussian_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Gaussian Blur 3x3", "RGB24", TEST_WIDTH,
					       TEST_HEIGHT, gaussian_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test Sharpen */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_kernel(&img, MPIX_KERNEL_SHARPEN, 3);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Sharpen 3x3", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		sharpen_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Sharpen 3x3", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       sharpen_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test Edge Detection */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_kernel(&img, MPIX_KERNEL_EDGE_DETECT, 3);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Edge Detection 3x3", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		edge_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Edge Detection 3x3", "RGB24", TEST_WIDTH,
					       TEST_HEIGHT, edge_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test Denoise */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_kernel(&img, MPIX_KERNEL_DENOISE, 3);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Denoise 3x3", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		denoise_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Denoise 3x3", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       denoise_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test Identity (baseline) */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_kernel(&img, MPIX_KERNEL_IDENTITY, 3);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Identity 3x3", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		identity_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Identity 3x3", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       identity_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test 5x5 Gaussian Blur */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_kernel(&img, MPIX_KERNEL_GAUSSIAN_BLUR, 5);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s (err=%d) |\n", "Gaussian Blur 5x5",
			       "RGB24", TEST_WIDTH, TEST_HEIGHT, "FAILED", result);
			break;
		}
		gaussian5_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Gaussian Blur 5x5", "RGB24", TEST_WIDTH,
					       TEST_HEIGHT, gaussian5_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test 5x5 Sharpen */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_kernel(&img, MPIX_KERNEL_SHARPEN, 5);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Sharpen 5x5", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		sharpen5_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Sharpen 5x5", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       sharpen5_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test 5x5 Edge Detection */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_kernel(&img, MPIX_KERNEL_EDGE_DETECT, 5);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Edge Detection 5x5", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		edge5_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Edge Detection 5x5", "RGB24", TEST_WIDTH,
					       TEST_HEIGHT, edge5_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test 5x5 Denoise */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_kernel(&img, MPIX_KERNEL_DENOISE, 5);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Denoise 5x5", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		denoise5_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Denoise 5x5", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       denoise5_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test 5x5 Identity (baseline) */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_kernel(&img, MPIX_KERNEL_IDENTITY, 5);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Identity 5x5", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		identity5_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Identity 5x5", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       identity5_total_time / BENCH_ITERATIONS);
		}
	}
}

static void benchmark_color_correction(void)
{
	struct mpix_image img;
	uint64_t start_time, end_time;
	uint64_t black_level_total_time = 0;
	uint64_t white_balance_total_time = 0;
	uint64_t gamma_total_time = 0;
	uint64_t combined_total_time = 0;

	union mpix_correction_any black_level_corr = {
		.black_level.level = 16,
	};
	union mpix_correction_any white_balance_corr = {
		.white_balance.red_level = 1228,  /* 1.2 * 1024 */
		.white_balance.blue_level = 1126, /* 1.1 * 1024 */
	};
	union mpix_correction_any gamma_corr = {
		.gamma.level = 10, /* Gamma level between 1-15 */
	};

	print_benchmark_header("Color Correction");

	/* Test Black Level Correction */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result =
			mpix_image_correction(&img, MPIX_CORRECTION_BLACK_LEVEL, &black_level_corr);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s (err=%d) |\n", "Black Level",
			       "RGB24", TEST_WIDTH, TEST_HEIGHT, "FAILED", result);
			break;
		}
		black_level_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Black Level", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       black_level_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test White Balance Correction */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_correction(&img, MPIX_CORRECTION_WHITE_BALANCE,
						   &white_balance_corr);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "White Balance", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		white_balance_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("White Balance", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       white_balance_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test Gamma Correction */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_correction(&img, MPIX_CORRECTION_GAMMA, &gamma_corr);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Gamma Correction", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		gamma_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Gamma Correction", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       gamma_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test Combined Corrections */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result1 =
			mpix_image_correction(&img, MPIX_CORRECTION_BLACK_LEVEL, &black_level_corr);
		int result2 = mpix_image_correction(&img, MPIX_CORRECTION_WHITE_BALANCE,
						    &white_balance_corr);
		int result3 = mpix_image_correction(&img, MPIX_CORRECTION_GAMMA, &gamma_corr);
		if (result1 == 0 && result2 == 0 && result3 == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result1 != 0 || result2 != 0 || result3 != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Combined CCM", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		combined_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Combined CCM", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       combined_total_time / BENCH_ITERATIONS);
		}
	}
}

static void benchmark_palettization(void)
{
	struct mpix_image img;
	uint64_t start_time, end_time;
	uint64_t optimize_total_time = 0;
	uint64_t palettize_total_time = 0;
	uint64_t depalettize_total_time = 0;

	struct mpix_palette palette = {
		.colors = palette_buffer,
		.fourcc = MPIX_FMT_PALETTE5,
	};

	print_benchmark_header("Palettization");

	/* Test Palette Optimization */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_optimize_palette(&img, &palette, 100);
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Optimize Palette", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}

		optimize_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Optimize Palette", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       optimize_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test Image Palettization */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		/* Pre-optimize palette for consistent timing */
		int opt_result = mpix_image_optimize_palette(&img, &palette, 100);

		start_time = mpix_port_get_uptime_us();
		if (opt_result == 0) {
			int result = mpix_image_palettize(&img, &palette);
			if (result == 0) {
				mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
			} else {
				end_time = mpix_port_get_uptime_us();
				xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Palettize", "RGB24",
				       TEST_WIDTH, TEST_HEIGHT, "FAILED");
				break;
			}
		} else {
			end_time = mpix_port_get_uptime_us();
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Palettize", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		end_time = mpix_port_get_uptime_us();

		palettize_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Palettize", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       palettize_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test Depalettization */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		/* Pre-palettize for depalettization test */
		int opt_result = mpix_image_optimize_palette(&img, &palette, 100);
		int pal_result = -1;
		if (opt_result == 0) {
			pal_result = mpix_image_palettize(&img, &palette);
		}

		start_time = mpix_port_get_uptime_us();
		if (pal_result == 0) {
			int result = mpix_image_depalettize(&img, &palette);
			if (result == 0) {
				mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
			} else {
				end_time = mpix_port_get_uptime_us();
				xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Depalettize", "RGB24",
				       TEST_WIDTH, TEST_HEIGHT, "FAILED");
				break;
			}
		} else {
			end_time = mpix_port_get_uptime_us();
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "Depalettize", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		end_time = mpix_port_get_uptime_us();

		depalettize_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("Depalettize", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       depalettize_total_time / BENCH_ITERATIONS);
		}
	}
}

static void benchmark_encoding(void)
{
	struct mpix_image img;
	uint64_t start_time, end_time;
	uint64_t qoi_encode_total_time = 0;
	uint64_t jpeg_encode_total_time = 0;

	print_benchmark_header("Image Encoding");

	/* Test QOI Encoding */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_qoi_encode(&img);
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "QOI Encode", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		qoi_encode_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("QOI Encode", "RGB24", TEST_WIDTH, TEST_HEIGHT,
					       qoi_encode_total_time / BENCH_ITERATIONS);
		}
	}

	/* Test JPEG Encoding */
	for (int i = 0; i < BENCH_ITERATIONS; i++) {
		fill_test_pattern(test_buffer, TEST_WIDTH, TEST_HEIGHT, MPIX_FMT_RGB24);
		mpix_image_from_buf(&img, test_buffer, BUFFER_SIZE, TEST_WIDTH, TEST_HEIGHT,
				    MPIX_FMT_RGB24);

		start_time = mpix_port_get_uptime_us();
		int result = mpix_image_jpeg_encode(&img, 80); /* 80% quality */
		if (result == 0) {
			mpix_image_to_buf(&img, output_buffer, sizeof(output_buffer));
		}
		end_time = mpix_port_get_uptime_us();

		if (result != 0) {
			xprintf("| %-18s | %-8s | %4dx%-4d | %8s |\n", "JPEG Encode (80%)", "RGB24",
			       TEST_WIDTH, TEST_HEIGHT, "FAILED");
			break;
		}
		jpeg_encode_total_time += end_time - start_time;

		if (i == BENCH_ITERATIONS - 1) {
			print_benchmark_result("JPEG Encode (80%)", "RGB24", TEST_WIDTH,
					       TEST_HEIGHT,
					       jpeg_encode_total_time / BENCH_ITERATIONS);
		}
	}
}

static void print_benchmark_header(const char *test_name)
{
	xprintf("\n## %s\n\n", test_name);
	xprintf("| Operation          | Format   | Resolution | Time (us) |\n");
	xprintf("|:-------------------|:---------|:-----------|----------:|\n");
}

static void print_benchmark_result(const char *operation, const char *format, int width, int height,
				   uint64_t time_us)
{
	xprintf("| %-18s | %-8s | %4dx%-4d | %8u |\n", operation, format, width, height, (uint32_t)time_us);

	/* Small delay to prevent log buffer overflow */
	vTaskDelay(pdMS_TO_TICKS(10));
}

static void fill_test_pattern(uint8_t *buffer, int width, int height, uint32_t fourcc)
{
	/* Fill with a gradient pattern for Bayer data */
	if (fourcc == MPIX_FMT_BGGR8) {
		for (int y = 0; y < height; y++) {
			for (int x = 0; x < width; x++) {
				int idx = y * width + x;
				/* Create a gradient pattern based on position */
				buffer[idx] = (uint8_t)((x + y) * 255 / (width + height - 2));
			}
		}
	} else if (fourcc == MPIX_FMT_RGB24) {
		/* Fill with RGB pattern */
		for (int y = 0; y < height; y++) {
			for (int x = 0; x < width; x++) {
				int idx = (y * width + x) * 3;
				buffer[idx] = (uint8_t)(x * 255 / (width - 1));      /* R */
				buffer[idx + 1] = (uint8_t)(y * 255 / (height - 1)); /* G */
				buffer[idx + 2] =
					(uint8_t)((x + y) * 255 / (width + height - 2)); /* B */
			}
		}
	}
}
