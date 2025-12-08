/*
 * cvapp.cpp
 *
 *  Created on: 2018~124
 *      Author: 902452
 */

#include <cstdio>
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "WE2_device.h"
#include "board.h"
#include "cvapp_yolov8_pose.h"
#include "common_config.h"
#include "cisdp_sensor.h"

#include "WE2_core.h"

#include "ethosu_driver.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "tensorflow/lite/c/common.h"
#if TFLM2209_U55TAG2205
#include "tensorflow/lite/micro/micro_error_reporter.h"
#endif
#include "img_proc_helium.h"


#include "xprintf.h"
#include "spi_master_protocol.h"
#include "cisdp_cfg.h"
#include "memory_manage.h"
// #include "yolo_postprocessing.h"
#include "send_result.h"
#include "reid.h"
#include "image_utils.h"
#include <vector>
#include <string>

// New headers for refactored code
#include "yolov8_pose_postprocess.h"
#include "reid_inference.h"

// Enable ReID inference (set to 0 to test pure YOLOv8 Pose)
#define ENABLE_REID_INFERENCE 1

// Static buffer for ReID input (128x256x3 = 98304 bytes)
// Place in .bss.NoInit to use SRAM instead of heap
static uint8_t reid_input_buffer_static[REID_INPUT_WIDTH * REID_INPUT_HEIGHT * 3] __attribute__((section(".bss.NoInit"), aligned(16)));
uint8_t* reid_input_buffer = reid_input_buffer_static;

#if ENABLE_REID_INFERENCE
// Use static allocation to avoid heap issues
static ReIDMatcher reid_matcher_static;
static ReIDMatcher* reid_matcher = &reid_matcher_static;
#endif

#define YOLOV8_POSE_INPUT_224 0
#define YOLOV8_POSE_INPUT_256 1

#if YOLOV8_POSE_INPUT_224
#define YOLOV8_POSE_INPUT_TENSOR_WIDTH   224
#define YOLOV8_POSE_INPUT_TENSOR_HEIGHT  224

#elif YOLOV8_POSE_INPUT_256
#define YOLOV8_POSE_INPUT_TENSOR_WIDTH   256
#define YOLOV8_POSE_INPUT_TENSOR_HEIGHT  256

#else
#define YOLOV8_POSE_INPUT_TENSOR_WIDTH   192
#define YOLOV8_POSE_INPUT_TENSOR_HEIGHT  192
#endif

#define INPUT_IMAGE_CHANNELS 3
#define YOLOV8_POSE_INPUT_TENSOR_CHANNEL INPUT_IMAGE_CHANNELS


#define  EACH_STEP_TICK 0
#define TOTAL_STEP_TICK 1

#ifdef TRUSTZONE_SEC
#define U55_BASE	BASE_ADDR_APB_U55_CTRL_ALIAS
#else
#ifndef TRUSTZONE
#define U55_BASE	BASE_ADDR_APB_U55_CTRL_ALIAS
#else
#define U55_BASE	BASE_ADDR_APB_U55_CTRL
#endif
#endif


using namespace std;

extern uint8_t reid_tensor_arena[]; // Reuse ReID arena for YOLO to save memory

namespace {

// Separate arenas for YOLO and ReID
// YOLO needs ~518KB, ReID needs ~1340KB
// Total ~1858KB, fits in 1924KB SRAM if other data is moved to APP_DATA
constexpr int yolo_tensor_arena_size = 520 * 1024;
constexpr int reid_tensor_arena_size = 1340 * 1024;

struct ethosu_driver ethosu_drv; /* Default Ethos-U device driver */
tflite::MicroInterpreter *yolov8_pose_int_ptr=nullptr;
TfLiteTensor *yolov8_pose_input, *(yolov8_pose_output[7]);

static const tflite::Model* s_yolov8_pose_model = nullptr;
static tflite::MicroMutableOpResolver<2>* s_yolov8_pose_op_resolver = nullptr;
static uint8_t s_pose_interpreter_buffer[sizeof(tflite::MicroInterpreter)] __attribute__((aligned(16)));

};

int dim_total_size = 0;
static float* stride_756_1;
static float* anchor_756_2;

#define CPU_CLK	0xffffff+1
uint32_t systick_1, systick_2;
uint32_t loop_cnt_1, loop_cnt_2;
static uint32_t capture_image_tick = 0;

// #endif

static void _arm_npu_irq_handler(void)
{
    /* Call the default interrupt handler from the NPU driver */
    ethosu_irq_handler(&ethosu_drv);
}

/**
 * @brief  Initialises the NPU IRQ
 **/
static void _arm_npu_irq_init(void)
{
    const IRQn_Type ethosu_irqnum = (IRQn_Type)U55_IRQn;

    /* Register the EthosU IRQ handler in our vector table.
     * Note, this handler comes from the EthosU driver */
    EPII_NVIC_SetVector(ethosu_irqnum, (uint32_t)_arm_npu_irq_handler);

    /* Enable the IRQ */
    NVIC_EnableIRQ(ethosu_irqnum);

}

static int _arm_npu_init(bool security_enable, bool privilege_enable)
{
    int err = 0;

    /* Initialise the IRQ */
    _arm_npu_irq_init();

    /* Initialise Ethos-U55 device */
#if TFLM2209_U55TAG2205
	const void * ethosu_base_address = (void *)(U55_BASE);
#else 
	void * const ethosu_base_address = (void *)(U55_BASE);
#endif

    if (0 != (err = ethosu_init(
                            &ethosu_drv,             /* Ethos-U driver device pointer */
                            ethosu_base_address,     /* Ethos-U NPU's base address. */
                            NULL,       /* Pointer to fast mem area - NULL for U55. */
                            0, /* Fast mem region size. */
							security_enable,                       /* Security enable. */
							privilege_enable))) {                   /* Privilege enable. */
    	xprintf("failed to initalise Ethos-U device\n");
            return err;
        }

    xprintf("Ethos-U55 device initialised\n");

    return 0;
}


void anchor_stride_matrix_construct()
{
    #if DBG_APP_LOG
    printf("construct stride/anchor matrix start\r\n");
    #endif

    int strides[] = {8, 16, 32};
    int start_step = 0;

    for(int j=0; j<3; j++) {
        int stride = strides[j];
        int grid_size = YOLOV8_POSE_INPUT_TENSOR_WIDTH / stride;
        int num_anchors = grid_size * grid_size;
        int end_step = start_step + num_anchors;

        // Fill stride
        for(int i = start_step; i < end_step; i++) {
            stride_756_1[i] = (float)stride;
        }

        // Fill anchors
        for(int y = 0; y < grid_size; y++) {
            for(int x = 0; x < grid_size; x++) {
                int idx = start_step + y * grid_size + x;
                anchor_756_2[idx * 2 + 0] = 0.5f + x;
                anchor_756_2[idx * 2 + 1] = 0.5f + y;
            }
        }
        
        start_step = end_step;
    }

    #if DBG_APP_LOG
    printf("construct stride/anchor matrix done\r\n");
    #endif
}



// Helper to setup YOLO interpreter
static bool setup_yolo_interpreter() {
    if (s_yolov8_pose_model == nullptr) return false;
    
    // Create interpreter
    yolov8_pose_int_ptr = new (s_pose_interpreter_buffer) tflite::MicroInterpreter(
        s_yolov8_pose_model, *s_yolov8_pose_op_resolver,
        (uint8_t*)reid_tensor_arena, reid_tensor_arena_size);
    
    if(yolov8_pose_int_ptr->AllocateTensors()!= kTfLiteOk) {
        xprintf("Pose AllocateTensors failed\n");
        return false;
    }
    yolov8_pose_input = yolov8_pose_int_ptr->input(0);
    for(int i = 0;i < 7;i++)
    {
        yolov8_pose_output[i] = yolov8_pose_int_ptr->output(i);
    }
    return true;
}

int cv_yolov8_pose_init(bool security_enable, bool privilege_enable, uint32_t model_addr) {
	dim_total_size = 0;
    int strides[] = {8, 16, 32};
    for(int stride : strides) {
        dim_total_size += pow((YOLOV8_POSE_INPUT_TENSOR_WIDTH/stride), 2);
    }

	stride_756_1 = (float*)calloc(dim_total_size, sizeof(float));
	anchor_756_2 = (float*)calloc(dim_total_size * 2, sizeof(float));
	
    anchor_stride_matrix_construct();
	int ercode = 0;

	// Use separate arenas
    // extern uint8_t reid_tensor_arena[]; // Defined in reid.cpp
	xprintf("YOLO Arena [%p] (Shared with ReID), ReID Arena [extern]\r\n", reid_tensor_arena);

    // Initialize NPU first (before any model that uses Ethos-U)
	if(_arm_npu_init(security_enable, privilege_enable)!=0)
		return -1;

#if ENABLE_REID_INFERENCE
    // Initialize ReID
    // reid_matcher is now statically allocated, so no new() needed
    // reid_matcher = new ReIDMatcher();
    
    xprintf("Initializing ReID Matcher...\n");
    // Use model from Flash
    if (!reid_matcher->init((void*)REID_MODEL_FLASH_ADDR, 0)) {
        xprintf("ReID init failed\n");
    } else {
        xprintf("ReID init success\n");
    }
    xprintf("ReID input buffer at %p (static, %d bytes)\n", reid_input_buffer, REID_INPUT_WIDTH * REID_INPUT_HEIGHT * 3);
#else
    xprintf("ReID disabled (ENABLE_REID_INFERENCE=0)\n");
#endif

	if(model_addr != 0) {
		s_yolov8_pose_model = tflite::GetModel((const void *)model_addr);

		if (s_yolov8_pose_model->version() != TFLITE_SCHEMA_VERSION) {
			xprintf(
				"[ERROR] yolov8_pose_model's schema version %d is not equal "
				"to supported version %d\n",
				s_yolov8_pose_model->version(), TFLITE_SCHEMA_VERSION);
			return -1;
		}
		else {
			xprintf("yolov8_pose_model model's schema version %d\n", s_yolov8_pose_model->version());
		}
		
		// Initialize op resolver (once)
		static tflite::MicroMutableOpResolver<2> yolov8_pose_op_resolver;
		yolov8_pose_op_resolver.AddTranspose();
		if (kTfLiteOk != yolov8_pose_op_resolver.AddEthosU()){
			xprintf("Failed to add Arm NPU support to op resolver.");
			return false;
		}
		s_yolov8_pose_op_resolver = &yolov8_pose_op_resolver;
		
		// Create initial interpreter
        if (!setup_yolo_interpreter()) {
            return -1;
        }
	}
	xprintf("initial done\n");
	return ercode;
}

int cv_yolov8_pose_run(struct_yolov8_pose_algoResult *algoresult_yolov8_pose) {
	int ercode = 0;
    static std::vector<std::vector<float>> cached_reid_vectors;
    float w_scale;
    float h_scale;
    uint32_t img_w = app_get_raw_width();
    uint32_t img_h = app_get_raw_height();
    uint32_t ch = app_get_raw_channels();
    uint32_t raw_addr = app_get_raw_addr();
    uint32_t expand = 0;
	std::forward_list<el_keypoint_t> el_keypoint_algo;
	static uint32_t frame_count = 0;  // Frame counter for debug output
	frame_count++;

	#if DBG_APP_LOG
    xprintf("raw info: w[%d] h[%d] ch[%d] addr[%x]\n",img_w, img_h, ch, raw_addr);
	#endif

	#if TOTAL_STEP_TICK
		SystemGetTick(&systick_1, &loop_cnt_1);
	#endif

    if(s_yolov8_pose_model != nullptr) {
    	//get image from sensor and resize
		w_scale = (float)(img_w - 1) / (YOLOV8_POSE_INPUT_TENSOR_WIDTH - 1);
		h_scale = (float)(img_h - 1) / (YOLOV8_POSE_INPUT_TENSOR_HEIGHT - 1);

        #if EACH_STEP_TICK
            SystemGetTick(&systick_1, &loop_cnt_1);
        #endif
		hx_lib_image_resize_BGR8U3C_to_RGB24_helium((uint8_t*)raw_addr, (uint8_t*)yolov8_pose_input->data.data,  
		                    img_w, img_h, ch, 
                        	YOLOV8_POSE_INPUT_TENSOR_WIDTH, YOLOV8_POSE_INPUT_TENSOR_HEIGHT, w_scale,h_scale);
		#if EACH_STEP_TICK						
            SystemGetTick(&systick_2, &loop_cnt_2);
            xprintf("Tick for resize image BGR8U3C_to_RGB24_helium for yolov8 POSE:[%d]\r\n",(loop_cnt_2-loop_cnt_1)*CPU_CLK+(systick_1-systick_2));							
		#endif
        #if EACH_STEP_TICK
            SystemGetTick(&systick_1, &loop_cnt_1);
        #endif
        
        // //uint8 to int8
		for (int i = 0; i < yolov8_pose_input->bytes; ++i) {
			*((int8_t *)yolov8_pose_input->data.data+i) = *((int8_t *)yolov8_pose_input->data.data+i) - 128;
    	}

        #if EACH_STEP_TICK
            SystemGetTick(&systick_2, &loop_cnt_2);
            xprintf("Tick for Invoke for uint8toint8 for YOLOV8_POSE:[%d]\r\n\n",(loop_cnt_2-loop_cnt_1)*CPU_CLK+(systick_1-systick_2));    
        #endif	


        #if EACH_STEP_TICK
		SystemGetTick(&systick_1, &loop_cnt_1);
        #endif

		TfLiteStatus invoke_status = yolov8_pose_int_ptr->Invoke();

        #if EACH_STEP_TICK
			SystemGetTick(&systick_2, &loop_cnt_2);
			xprintf("Tick for invoke of yolov8n pose:[%d]\r\n",(loop_cnt_2-loop_cnt_1)*CPU_CLK+(systick_1-systick_2));	
        #endif

		if(invoke_status != kTfLiteOk)
		{
			xprintf("yolov8n pose invoke fail\n");
			sensordplib_retrigger_capture();  // Must retrigger to continue event loop
			return -1;
		}
		else
		{
			#if DBG_APP_LOG
			xprintf("yolov8n pose invoke pass\n");
			#endif
		}

        #if EACH_STEP_TICK
            SystemGetTick(&systick_1, &loop_cnt_1);
        #endif
		//retrieve output data


		yolov8_pose_post_processing(
            yolov8_pose_int_ptr,
            0.50, 
            0.45, 
            algoresult_yolov8_pose,
            el_keypoint_algo,
            dim_total_size,
            anchor_756_2,
            stride_756_1,
            img_w,
            img_h,
            YOLOV8_POSE_INPUT_TENSOR_WIDTH,
            YOLOV8_POSE_INPUT_TENSOR_HEIGHT
        );

#if ENABLE_REID_INFERENCE
        bool people_detected = !el_keypoint_algo.empty();
        
        // Logic: Run ReID if:
        // 1. People are detected AND
        // 2. (It's a scheduled frame OR we don't have cached vectors yet)
        if (people_detected) {
            if (frame_count % 5 == 0 || cached_reid_vectors.empty()) {
                cached_reid_vectors.clear(); // Clear old before new run
                run_reid_pipeline(
                    el_keypoint_algo,
                    raw_addr,
                    img_w,
                    img_h,
                    reid_matcher,
                    reid_input_buffer,
                    cached_reid_vectors
                );

                if (!setup_yolo_interpreter()) {
                    xprintf("Failed to restore YOLO interpreter!\n");
                }
            }
            // Else: reuse cached_reid_vectors
        } else {
            cached_reid_vectors.clear(); // No people, clear cache
        }
#endif // ENABLE_REID_INFERENCE

		#if EACH_STEP_TICK
			SystemGetTick(&systick_2, &loop_cnt_2);
			xprintf("Tick for Invoke for YOLOV8_POSE_post_processing:[%d]\r\n\n",(loop_cnt_2-loop_cnt_1)*CPU_CLK+(systick_1-systick_2));    
        #endif

		#if DBG_APP_LOG
			xprintf("yolov8 pose done\r\n");
		#endif
    }


#ifdef UART_SEND_ALOGO_RESEULT
	#if TOTAL_STEP_TICK						
		SystemGetTick(&systick_2, &loop_cnt_2);
		algoresult_yolov8_pose->algo_tick = (loop_cnt_2-loop_cnt_1)*CPU_CLK+(systick_1-systick_2) + capture_image_tick;				
	#endif
uint32_t judge_case_data;
uint32_t g_trans_type;
hx_drv_swreg_aon_get_appused1(&judge_case_data);
g_trans_type = (judge_case_data>>16);
if( g_trans_type == 0 || g_trans_type == 2)// transfer type is (UART) or (UART & SPI) 
{	
	//invalid dcache to let uart can send the right jpeg img out
	hx_InvalidateDCache_by_Addr((volatile void *)app_get_jpeg_addr(), sizeof(uint8_t) *app_get_jpeg_sz());

	el_img_t temp_el_jpg_img = el_img_t{};
	temp_el_jpg_img.data = (uint8_t *)app_get_jpeg_addr();
	temp_el_jpg_img.size = app_get_jpeg_sz();
	temp_el_jpg_img.width = app_get_raw_width();
	temp_el_jpg_img.height = app_get_raw_height();
	temp_el_jpg_img.format = EL_PIXEL_FORMAT_JPEG;
	temp_el_jpg_img.rotate = EL_PIXEL_ROTATE_0;

    // Send results using the modular function in send_result.cpp
    send_yolov8_pose_reid_results(
        frame_count,
        el_keypoint_algo,
        algoresult_yolov8_pose->algo_tick,
        cached_reid_vectors,
        &temp_el_jpg_img
    );
}
	set_model_change_by_uart();
#endif	
	
	SystemGetTick(&systick_1, &loop_cnt_1);
	//recapture image
	sensordplib_retrigger_capture();

	SystemGetTick(&systick_2, &loop_cnt_2);
	capture_image_tick = (loop_cnt_2-loop_cnt_1)*CPU_CLK+(systick_1-systick_2);	
	
	return ercode;
}

int cv_yolov8_pose_deinit()
{
	free(stride_756_1);
	free(anchor_756_2);
	return 0;
}

