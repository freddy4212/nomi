#include <stdio.h>
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include "powermode_export.h"

#define WE2_CHIP_VERSION_C		0x8538000c
#define SEND_IMAGE_SPI			0
#ifdef TRUSTZONE_SEC
#ifdef FREERTOS
/* Trustzone config. */
//
/* FreeRTOS includes. */
//#include "secure_port_macros.h"
#else
#if (__ARM_FEATURE_CMSE & 1) == 0
#error "Need ARMv8-M security extensions"
#elif (__ARM_FEATURE_CMSE & 2) == 0
#error "Compile with --cmse"
#endif
#include "arm_cmse.h"
//#include "veneer_table.h"
//
#endif
#endif

#include "WE2_device.h"
#include "spi_master_protocol.h"
#include "hx_drv_spi.h"
#include "spi_eeprom_comm.h"
#include "board.h"
#include "xprintf.h"
#include "board.h"
#include "WE2_core.h"
#include "hx_drv_scu.h"
#include "hx_drv_swreg_aon.h"
#ifdef IP_sensorctrl
#include "hx_drv_sensorctrl.h"
#endif
#ifdef IP_xdma
#include "hx_drv_xdma.h"
#include "sensor_dp_lib.h"
#endif
#ifdef IP_cdm
#include "hx_drv_cdm.h"
#endif
#ifdef IP_gpio
#include "hx_drv_gpio.h"
#endif
#include "hx_drv_pmu_export.h"
#include "hx_drv_pmu.h"
#include "powermode.h"
#include "spi_fatfs.h"
#include "BITOPS.h"

#include "cisdp_sensor.h"
#include "event_handler.h"
#include "common_config.h"
#include "libmpix_camera.h"

#include <mpix/image.h>

#define SPI_SEN_PIC_CLK				(10000000)

static volatile uint32_t g_cur_frame = 0;
static volatile uint32_t g_frame_ready = 0;
static volatile uint32_t g_xdma_abnormal = 0;
static volatile uint32_t g_rs_abnormal = 0;
static volatile uint32_t g_hog_abnormal = 0;
static volatile uint32_t g_rs_frameready = 0;
static volatile uint32_t g_hog_frameready = 0;
static volatile uint32_t g_md_detect = 0;
static volatile uint32_t g_time = 0;
static volatile uint32_t g_prev_time = 0;
static volatile uint32_t g_wdt1_timeout = 0;
static volatile uint32_t g_wdt2_timeout = 0;
static volatile uint32_t g_wdt3_timeout = 0;

void dp_var_init()
{
	g_cur_frame = 0;
	g_frame_ready = 0;
	g_xdma_abnormal = 0;
	g_rs_abnormal = 0;
	g_hog_abnormal = 0;
	g_rs_frameready = 0;
	g_hog_frameready = 0;
	g_md_detect = 0;
	g_time = 0;
	g_prev_time = 0;
	g_wdt1_timeout = 0;
	g_wdt2_timeout = 0;
	g_wdt3_timeout = 0;
}

static void app_dplib_cb(SENSORDPLIB_STATUS_E event)
{
	uint32_t de0_count, conv_count;
	dbg_printf(DBG_MORE_INFO, "event = %d\n", event);

	if(event != SENSORDPLIB_STATUS_TIMER_FIRE_APP_NOTREADY)
	{
		hx_drv_edm_get_de_count(0, &de0_count);
		dbg_printf(DBG_MORE_INFO, "de0_count = 0x%x\n", de0_count);
		hx_drv_edm_get_conv_de_count(&conv_count);
		dbg_printf(DBG_MORE_INFO, "conv_count = 0x%x\n", conv_count);
	}
	switch(event)
	{
	case SENSORDPLIB_STATUS_EDM_WDT1_TIMEOUT:
		dbg_printf(DBG_MORE_INFO, "CB WDT1 Timeout\n");
		g_wdt1_timeout = 1;
    	hx_drv_swreg_aon_set_sensorinit(SWREG_AON_SENSOR_INIT_NO);
		break;

	case SENSORDPLIB_STATUS_EDM_WDT2_TIMEOUT:
		dbg_printf(DBG_MORE_INFO, "CB WDT2 Timeout\n");
		g_wdt2_timeout = 1;
    	hx_drv_swreg_aon_set_sensorinit(SWREG_AON_SENSOR_INIT_NO);
		break;

	case SENSORDPLIB_STATUS_EDM_WDT3_TIMEOUT:
		dbg_printf(DBG_MORE_INFO, "CB WDT3 Timeout\n");
		g_wdt3_timeout = 1;
    	hx_drv_swreg_aon_set_sensorinit(SWREG_AON_SENSOR_INIT_NO);
		break;
		
	case SENSORDPLIB_STATUS_SENSORCTRL_WDT_OUT:
		/*
		 * TODO error happen need check sensor
		 * 1. SWRESET Sensor Control & DP
		 * 2. restart streaming flow
		 */
		dbg_printf(DBG_MORE_INFO, "WDT OUT %d\n", event);
    	hx_drv_swreg_aon_set_sensorinit(SWREG_AON_SENSOR_INIT_NO);
		break;

	case SENSORDPLIB_STATUS_CDM_FIFO_OVERFLOW:
	case SENSORDPLIB_STATUS_CDM_FIFO_UNDERFLOW:
		dbg_printf(DBG_MORE_INFO, "CDM_FIFO_ERROR %d\n", event);
    	hx_drv_swreg_aon_set_sensorinit(SWREG_AON_SENSOR_INIT_NO);
		g_xdma_abnormal = 1;
		break;

	case SENSORDPLIB_STATUS_XDMA_WDMA1_ABNORMAL1:
	case SENSORDPLIB_STATUS_XDMA_WDMA1_ABNORMAL2:
	case SENSORDPLIB_STATUS_XDMA_WDMA1_ABNORMAL3:
	case SENSORDPLIB_STATUS_XDMA_WDMA1_ABNORMAL4:
	case SENSORDPLIB_STATUS_XDMA_WDMA1_ABNORMAL5:
	case SENSORDPLIB_STATUS_XDMA_WDMA1_ABNORMAL6:
	case SENSORDPLIB_STATUS_XDMA_WDMA1_ABNORMAL7:
	case SENSORDPLIB_STATUS_XDMA_WDMA1_ABNORMAL8:
	case SENSORDPLIB_STATUS_XDMA_WDMA1_ABNORMAL9:

	case SENSORDPLIB_STATUS_XDMA_WDMA2_ABNORMAL1:
	case SENSORDPLIB_STATUS_XDMA_WDMA2_ABNORMAL2:
	case SENSORDPLIB_STATUS_XDMA_WDMA2_ABNORMAL3:
	case SENSORDPLIB_STATUS_XDMA_WDMA2_ABNORMAL4:
	case SENSORDPLIB_STATUS_XDMA_WDMA2_ABNORMAL5:
	case SENSORDPLIB_STATUS_XDMA_WDMA2_ABNORMAL6:
	case SENSORDPLIB_STATUS_XDMA_WDMA2_ABNORMAL7:

	case SENSORDPLIB_STATUS_XDMA_WDMA3_ABNORMAL1:
	case SENSORDPLIB_STATUS_XDMA_WDMA3_ABNORMAL2:
	case SENSORDPLIB_STATUS_XDMA_WDMA3_ABNORMAL3:
	case SENSORDPLIB_STATUS_XDMA_WDMA3_ABNORMAL4:
	case SENSORDPLIB_STATUS_XDMA_WDMA3_ABNORMAL5:
	case SENSORDPLIB_STATUS_XDMA_WDMA3_ABNORMAL6:
	case SENSORDPLIB_STATUS_XDMA_WDMA3_ABNORMAL7:
	case SENSORDPLIB_STATUS_XDMA_WDMA3_ABNORMAL8:
	case SENSORDPLIB_STATUS_XDMA_WDMA3_ABNORMAL9:

		dbg_printf(DBG_MORE_INFO, "WDMA123 abnormal %d\n", event);
    	hx_drv_swreg_aon_set_sensorinit(SWREG_AON_SENSOR_INIT_NO);
		g_xdma_abnormal = 1;
		break;

	case SENSORDPLIB_STATUS_XDMA_RDMA_ABNORMAL1:
	case SENSORDPLIB_STATUS_XDMA_RDMA_ABNORMAL2:
	case SENSORDPLIB_STATUS_XDMA_RDMA_ABNORMAL3:
	case SENSORDPLIB_STATUS_XDMA_RDMA_ABNORMAL4:
	case SENSORDPLIB_STATUS_XDMA_RDMA_ABNORMAL5:
		dbg_printf(DBG_MORE_INFO, "RDMA abnormal %d\n", event);
		g_xdma_abnormal = 1;
    	hx_drv_swreg_aon_set_sensorinit(SWREG_AON_SENSOR_INIT_NO);
		break;

	case SENSORDPLIB_STATUS_RSDMA_ABNORMAL1:
	case SENSORDPLIB_STATUS_RSDMA_ABNORMAL2:
	case SENSORDPLIB_STATUS_RSDMA_ABNORMAL3:
	case SENSORDPLIB_STATUS_RSDMA_ABNORMAL4:
	case SENSORDPLIB_STATUS_RSDMA_ABNORMAL5:
	case SENSORDPLIB_STATUS_RSDMA_ABNORMAL6:
	case SENSORDPLIB_STATUS_RSDMA_ABNORMAL7:
		/*
		 *  error happen need
		 * 1. SWRESET RS & RS DMA
		 * 2. Re-run flow again
		 */
		dbg_printf(DBG_MORE_INFO, "RSDMA abnormal %d\n", event);
	    g_rs_abnormal = 1;
		break;

	case SENSORDPLIB_STATUS_HOGDMA_ABNORMAL1:
	case SENSORDPLIB_STATUS_HOGDMA_ABNORMAL2:
	case SENSORDPLIB_STATUS_HOGDMA_ABNORMAL3:
	case SENSORDPLIB_STATUS_HOGDMA_ABNORMAL4:
	case SENSORDPLIB_STATUS_HOGDMA_ABNORMAL5:
	case SENSORDPLIB_STATUS_HOGDMA_ABNORMAL6:
	case SENSORDPLIB_STATUS_HOGDMA_ABNORMAL7:
		/*
		 *  error happen need
		 * 1. SWRESET HOG & HOG DMA
		 * 2. Re-run flow again
		 */
		dbg_printf(DBG_MORE_INFO, "HOGDMA abnormal %d\n", event);
		g_hog_abnormal = 1;
		break;

	case SENSORDPLIB_STATUS_CDM_MOTION_DETECT:
		/*
		 * app anything want to do
		 * */
		g_md_detect = 1;
		dbg_printf(DBG_MORE_INFO, "Motion Detect\n");
		break;
	case SENSORDPLIB_STATUS_XDMA_FRAME_READY:
    	g_cur_frame++;
        // already capture user wanted frame number
    	g_frame_ready = 1;
		dbg_printf(DBG_LESS_INFO, "XDMA_FRAME_READY : %d \n", g_cur_frame);
		break;
	case SENSORDPLIB_STATUS_XDMA_WDMA1_FINISH:
	case SENSORDPLIB_STATUS_XDMA_WDMA2_FINISH:
	case SENSORDPLIB_STATUS_XDMA_WDMA3_FINISH:
	case SENSORDPLIB_STATUS_XDMA_RDMA_FINISH:
		break;

	case SENSORDPLIB_STATUS_RSDMA_FINISH:
		/*
		 * RS Frame result ready
		 */
		g_rs_frameready = 1;
		break;
	case SENSORDPLIB_STATUS_HOGDMA_FINISH:
		/*
		 * HOG Frame result ready
		 */
		g_hog_frameready = 1;
		break;
	case SENSORDPLIB_STATUS_TIMER_FIRE_APP_NOTREADY:
		g_time++;
		break;
	case SENSORDPLIB_STATUS_TIMER_FIRE_APP_READY:
		g_time++;
		break;
	default:
		break;
	}
}

void app_dump_single_jpeginfo(uint32_t *jpeg_enc_filesize, uint32_t *jpeg_enc_addr)
{
    uint8_t frame_no;
    uint8_t buffer_no = 0;
    hx_drv_xdma_get_WDMA2_bufferNo(&buffer_no);
    hx_drv_xdma_get_WDMA2NextFrameIdx(&frame_no);
    uint32_t reg_val=0, mem_val=0;

	dbg_printf(DBG_MORE_INFO, "app_dump_single_jpeginfo:buffer_no=%d, frame_no=%d\n",buffer_no, frame_no);
    if(frame_no == 0)
    {
        frame_no = buffer_no - 1;
    }else{
        frame_no = frame_no - 1;
    }

    hx_drv_jpeg_get_EncOutRealMEMSize(&reg_val);
	*jpeg_enc_filesize = reg_val;
	*jpeg_enc_addr = app_get_jpeg_addr();

    dbg_printf(DBG_MORE_INFO, "current frame_no=%d, jpeg_size=0x%x,addr=0x%x\n",frame_no,*jpeg_enc_filesize,*jpeg_enc_addr);
}

__attribute__(( section(".bss.NoInit"))) uint8_t buf_out[54+640*480*3] __ALIGNED(32);

#pragma pack(push, 1)
typedef struct {
    uint16_t bfType;        // "BM" (0x4D42)
    uint32_t bfSize;        // 文件总大小
    uint16_t bfReserved1;   // 0
    uint16_t bfReserved2;   // 0
    uint32_t bfOffBits;     // 像素数据偏移 (54)
} BMPFileHeader;

typedef struct {
    uint32_t biSize;        // 信息头大小 (40)
    int32_t  biWidth;       // 图像宽度
    int32_t  biHeight;      // 图像高度（负值表示从上到下存储）
    uint16_t biPlanes;      // 1
    uint16_t biBitCount;    // 24 (RGB)
    uint32_t biCompression; // 0 (不压缩)
    uint32_t biSizeImage;   // 像素数据大小（含填充）
    int32_t  biXPelsPerMeter; // 0
    int32_t  biYPelsPerMeter; // 0
    uint32_t biClrUsed;     // 0
    uint32_t biClrImportant; // 0
} BMPInfoHeader;
#pragma pack(pop)

void save_rgb_to_bmp(uint8_t* bmp_data, int width, int height, const char* filename) {

    const int row_size = width * 3;                
    const int padding = (4 - (row_size % 4)) % 4;  
    const int stride = row_size + padding;            
    const uint32_t pixel_data_size = stride * height; 
    
    BMPFileHeader file_header = {
        .bfType = 0x4D42,
        .bfSize = sizeof(BMPFileHeader) + sizeof(BMPInfoHeader) + pixel_data_size,
        .bfOffBits = sizeof(BMPFileHeader) + sizeof(BMPInfoHeader)
    };
    
    BMPInfoHeader info_header = {
        .biSize = sizeof(BMPInfoHeader),
        .biWidth = width,
        .biHeight = -height,     
        .biPlanes = 1,
        .biBitCount = 24,
        .biCompression = 0,
        .biSizeImage = pixel_data_size 
    };
    
    memcpy(bmp_data, &file_header, sizeof(file_header));
    memcpy(bmp_data + sizeof(BMPFileHeader), &info_header, sizeof(info_header));
    
    fastfs_write_image(bmp_data, file_header.bfSize, filename);
}

void app_setup_dplib_4_yuv_then_jpg() {
	uint32_t jpeg_enc_filesize;
	uint32_t jpeg_enc_addr;
	uint32_t read_status;
	uint32_t w, h;
	uint32_t raw_size;
	char filename[20];

	struct mpix_image img;
	union mpix_correction_any bl = {.black_level = {.level = 0x0f}};
	union mpix_correction_any wb = {.white_balance = {.red_level = 2048, .blue_level = 2048}};
	union mpix_correction_any gc = {.gamma = {.level = 240}};

	if (cisdp_sensor_init() < 0)
	{
		xprintf("\r\nCIS nonAOS Init fail - cisdp_sensor_init\r\n");
		APP_BLOCK_FUNC();
	}

	dp_var_init();
	
	if (cisdp_dp_init(true, CISDP_INIT_TYPE_INP_CROP_1280x960_RAW, SENSORDPLIB_PATH_INP_WDMA2, app_dplib_cb, 4) < 0)
	{
		dbg_printf(DBG_MORE_INFO, "\r\nDATAPATH nonAOS Init fail- cisdp_dp_init\r\n");
		APP_BLOCK_FUNC();
	}
	
	cisdp_sensor_start();

	while( 1 )
	{
		if(g_frame_ready == 1 )
		{
			g_frame_ready = 0;
	
			w = cisdp_get_raw_width(), h = cisdp_get_raw_height();
			raw_size = w*h;
			
			printf("w: %d, h: %d, raw_size: %d\n", w, h, raw_size);
			copy_mem_to_mem(cisdp_get_raw_addr(), cisdp_get_quater_raw_addr(), w, h, 0, 0, w, h);
			
			mpix_image_from_buf(&img, (const uint8_t*)cisdp_get_quater_raw_addr(), raw_size, w, h, MPIX_FMT_SBGGR8);
			mpix_image_debayer(&img, 2);
			
			mpix_image_correction(&img, MPIX_CORRECTION_BLACK_LEVEL, &bl);
			mpix_image_correction(&img, MPIX_CORRECTION_WHITE_BALANCE, &wb);
			mpix_image_correction(&img, MPIX_CORRECTION_GAMMA, &gc);
			mpix_image_kernel(&img, MPIX_KERNEL_DENOISE, 3);

			mpix_image_convert(&img, MPIX_FMT_RGB24);
			mpix_image_to_buf(&img, &buf_out[54], raw_size*3);

			xsprintf(filename, "image%04d.bmp", g_cur_frame);
			save_rgb_to_bmp(buf_out, w, h, filename);
			
			if (cisdp_dp_init(false, CISDP_INIT_TYPE_INP_CROP_1280x960_RAW, SENSORDPLIB_PATH_INP_WDMA2, app_dplib_cb, 4) < 0)
			{
				dbg_printf(DBG_MORE_INFO, "\r\nDATAPATH nonAOS Init fail- cisdp_dp_init\r\n");
				APP_BLOCK_FUNC();
			}
			sensordplib_retrigger_capture();
		}
	}
}

/*******************************************************************************
 * Code
 ******************************************************************************/
/*!
 * @brief Main function
 */
int app_main(void) {

	printf("=========================================================\n");
	printf("================== libmpix_camera test ==================\n");
	printf("=========================================================\n");
	
#if SEND_IMAGE_SPI
	hx_drv_scu_set_PB2_pinmux(SCU_PB2_PINMUX_SPI_M_DO_1, 1);
	hx_drv_scu_set_PB3_pinmux(SCU_PB3_PINMUX_SPI_M_DI_1, 1);
	hx_drv_scu_set_PB4_pinmux(SCU_PB4_PINMUX_SPI_M_SCLK_1, 1);
	hx_drv_scu_set_PB11_pinmux(SCU_PB11_PINMUX_SPI_M_CS, 1);
	if (hx_drv_spi_mst_open_speed(SPI_SEN_PIC_CLK) != 0)
	{
		dbg_printf(DBG_MORE_INFO, "DEBUG SPI master init fail\r\n");
		sensordplib_retrigger_capture();
		return ;
	}
#else
	fatfs_init();
#endif

	app_setup_dplib_4_yuv_then_jpg();

	return 0;
}
