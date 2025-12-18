#ifndef SEND_RESULT_H
#define SEND_RESULT_H


#ifdef __cplusplus
#include <cstring>
#include <limits>
#include <type_traits>
#include <utility>
#include <vector>
#include <string>
#include <forward_list>
#endif


#include <hx_drv_uart.h>
#include <math.h>
extern "C" {
#include "hx_drv_swreg_aon.h"
#ifdef OUTPUT_VIA_I2C
#include "hx_drv_iic.h"
#include "hx_drv_scu.h"
#endif
#ifdef OUTPUT_VIA_UART
#include "hx_drv_scu.h"  // For pin mux configuration
#endif
}

// UART Configuration
// UART0 = USB Debug UART (via USB-C)
// UART1 = XIAO Connector UART (PB6=RX, PB7=TX)
#define CONSOLE_UART_ID       0   // USB Debug UART
#define XIAO_UART_ID          1   // XIAO Connector UART (PB6/PB7)
#define OUTPUT_UART_ID        XIAO_UART_ID  // Use XIAO Connector for output

// I2C Slave Configuration
#ifdef OUTPUT_VIA_I2C
#define I2C_SLAVE_ADDR      0x62    // Same as SSCMA library default address
#define I2C_SLAVE_ID        USE_DW_IIC_SLV_0  // Use I2C Slave 0 (PA2/PA3 pins = Grove connector)
#endif

#define EL_ATTR_WEAK __attribute__((weak))
#define EL_VERSION                 __TIMESTAMP__
#define CONFIG_SSCMA_CMD_MAX_LENGTH (4096)
#define KEYPOINT_NUM 17
#define FM_POINT_NUM 468
#define FM_IRIS_POINT_NUM 10
#define MAX_FACE_LAND_MARK_TRACKED_POINT 68
typedef enum {
    EL_OK      = 0,  // success
    EL_AGAIN   = 1,  // try again
    EL_ELOG    = 2,  // logic error
    EL_ETIMOUT = 3,  // timeout
    EL_EIO     = 4,  // IO error
    EL_EINVAL  = 5,  // invalid argument
    EL_ENOMEM  = 6,  // out of memory
    EL_EBUSY   = 7,  // busy
    EL_ENOTSUP = 8,  // not supported
    EL_EPERM   = 9,  // operation not permitted
} el_err_code_t;
typedef enum {
    EL_PIXEL_FORMAT_RGB888 = 0,
    EL_PIXEL_FORMAT_RGB565,
    EL_PIXEL_FORMAT_YUV422,
    EL_PIXEL_FORMAT_GRAYSCALE,
    EL_PIXEL_FORMAT_JPEG,
    EL_PIXEL_FORMAT_UNKNOWN,
} el_pixel_format_t;
typedef enum el_pixel_rotate_t {
    EL_PIXEL_ROTATE_0 = 0,
    EL_PIXEL_ROTATE_90,
    EL_PIXEL_ROTATE_180,
    EL_PIXEL_ROTATE_270,
    EL_PIXEL_ROTATE_UNKNOWN,
} el_pixel_rotate_t;
typedef struct el_img_t {
    uint8_t*          data;
    size_t            size;
    uint16_t          width;
    uint16_t          height;
    el_pixel_format_t format;
    el_pixel_rotate_t rotate;
} el_img_t;
typedef struct el_box_t {
    uint16_t x;
    uint16_t y;
    uint16_t w;
    uint16_t h;
    uint8_t  score;
    uint8_t  target;
} el_box_t;

typedef struct el_point_t {
    uint16_t x;
    uint16_t y;
    uint8_t  score;
    uint8_t  target;
} el_point_t;

typedef struct el_class_t {
    uint16_t score;
    uint16_t target;
} el_class_t;

typedef struct el_keypoint_t {
    el_box_t el_box;
    el_point_t el_keypoint[KEYPOINT_NUM];
} el_keypoint_t;


typedef struct {
	int16_t yaw;
	int16_t pitch;
	int16_t roll;
	int16_t MAR;
	int16_t REAR;
	int16_t LEAR;
    int16_t left_iris_theta;
	int16_t left_iris_phi;
	int16_t right_iris_theta;
	int16_t right_iris_phi;
}el_struct_angle;

typedef struct el_fm_point_t {
    el_box_t el_box;
    el_point_t el_fm_point[FM_POINT_NUM];
    el_point_t el_fm_iris[FM_IRIS_POINT_NUM];
    el_struct_angle el_fm_angle;
} el_fm_point_t;


typedef struct el_fd_fl_t {
    el_box_t el_box;
    el_point_t el_fl[MAX_FACE_LAND_MARK_TRACKED_POINT];
    el_struct_angle el_fl_angle;
} el_fd_fl_t;

typedef struct el_fd_fl_el_9pt_t {
    el_box_t el_box;
    el_point_t el_fl[MAX_FACE_LAND_MARK_TRACKED_POINT];
    el_point_t left_eye_landmark[9];
	el_point_t right_eye_landmark[9];
    el_struct_angle el_fl_angle;
} el_fd_fl_el_9pt_t;

/**
 * @brief Algorithm Types
 */
typedef enum {
    EL_ALGO_TYPE_UNDEFINED = 0u,
    EL_ALGO_TYPE_FOMO      = 1u,
    EL_ALGO_TYPE_PFLD      = 2u,
    EL_ALGO_TYPE_YOLO      = 3u,
    EL_ALGO_TYPE_IMCLS     = 4u
} el_algorithm_type_t;
typedef struct el_model_info_t {
    uint8_t             id;
    el_algorithm_type_t type;
    uint32_t            addr_flash;
    uint32_t            size;
    const uint8_t*      addr_memory;
} el_model_info_t;

constexpr inline std::size_t lengthof(const char* s) {
    std::size_t size = 0;
    while (*(s + size) != '\0') ++size;
    return size;
}

template <class T, std::size_t N> constexpr inline std::size_t lengthof(const T (&)[N]) noexcept { return N; }

inline std::size_t lengthof(const std::string& s) { return s.length(); }

// template <typename... Args> constexpr inline decltype(auto) concat_strings(Args&&... args) {
//     std::size_t length{(lengthof(args) + ...)};  // try calculate total length at compile time
//     std::string result;
//     result.reserve(length + 1);  // preallocate memory, avoid repeatly allocate memory while appendings
//     (result.append(std::forward<Args>(args)), ...);
//     return result;
// }

template <typename... Args> constexpr inline decltype(auto) concat_strings(Args&&... args) {
    std::size_t length{(lengthof(args) + ...)};
    std::string result;
    result.reserve(length);
    (result.append(std::forward<Args>(args)), ...);
    return result;
}



el_err_code_t send_bytes(const char* buffer, size_t size) ;
el_err_code_t read_bytes(char* buffer, size_t size);
el_err_code_t read_bytes_nonblock(char* buffer, size_t size);
void set_model_change_by_uart();
std::string img_2_json_str(el_img_t* img);
void event_reply(std::string data);
void send_device_id();
template <typename T> constexpr std::string  results_2_json_str(const std::forward_list<T>& results);

std::string  box_results_2_json_str(std::forward_list<el_box_t>& results);
std::string  fm_point_results_2_json_str(std::forward_list<el_fm_point_t>& results);
std::string  keypoint_results_2_json_str(std::forward_list<el_keypoint_t>& results);
std::string  img_res_2_json_str(const el_img_t* img);
std::string  algo_tick_2_json_str(uint32_t algo_tick);
std::string  fd_fl_results_2_json_str(std::forward_list<el_fd_fl_t>& results);
std::string  fd_fl_el_9t_results_2_json_str(std::forward_list<el_fd_fl_el_9pt_t>& results);
std::string  fm_face_bbox_results_2_json_str(std::forward_list<el_box_t>& results);

void send_yolov8_pose_reid_results(
    uint32_t frame_count,
    std::forward_list<el_keypoint_t>& el_keypoint_algo,
    uint32_t algo_tick,
    const std::vector<std::vector<float>>& reid_vectors,
    el_img_t* img
);

// Output interface initialization and functions
#ifdef OUTPUT_VIA_I2C
/**
 * @brief Initialize I2C slave interface for Grove connector output
 * @return EL_OK on success
 */
el_err_code_t i2c_output_init(void);

/**
 * @brief Send bytes via I2C slave (master reads from us)
 * @param buffer Data to send
 * @param size Size of data
 * @return EL_OK on success
 */
el_err_code_t i2c_send_bytes(const char* buffer, size_t size);
#endif

/**
 * @brief Initialize all output interfaces based on compile options
 */
#ifdef __cplusplus
extern "C" {
#endif
void output_init(void);
#ifdef __cplusplus
}
#endif

#endif // SEND_RESULT_H