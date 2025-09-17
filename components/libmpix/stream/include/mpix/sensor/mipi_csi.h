/*
 * mipi_csi.h
 *
 * MIPI CSI interface abstraction for camera sensors
 */

#ifndef STREAM_MPIX_MIPI_CSI_H_
#define STREAM_MPIX_MIPI_CSI_H_

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C"
{
#endif

    /**
     * \enum MIPI_CSI_LANE_COUNT_E
     * \brief MIPI CSI data lane count
     */
    typedef enum
    {
        MIPI_CSI_LANE_1 = 1,
        MIPI_CSI_LANE_2 = 2,
    } mipi_csi_lane_count_t;

    /**
     * \enum MIPI_CSI_PIXEL_DEPTH_E
     * \brief MIPI CSI pixel depth (bits per pixel)
     */
    typedef enum
    {
        MIPI_CSI_PIXEL_DEPTH_8 = 8,
        MIPI_CSI_PIXEL_DEPTH_10 = 10,
    } mipi_csi_pixel_depth_t;

    /**
     * \enum MIPI_CSI_CLK_MODE_E
     * \brief MIPI CSI clock mode
     */
    typedef enum
    {
        MIPI_CSI_CLK_MODE_NON_CONTINUOUS = 0,
        MIPI_CSI_CLK_MODE_CONTINUOUS = 1,
    } mipi_csi_clk_mode_t;

    /**
     * \struct mipi_csi_timing_t
     * \brief MIPI CSI timing configuration
     */
    typedef struct
    {
        uint32_t frame_width;  ///< Frame width in pixels
        uint32_t frame_height; ///< Frame height in pixels
        uint32_t line_length;  ///< Line length including blanking
        uint32_t frame_length; ///< Frame length including blanking
    } mipi_csi_timing_t;

    /**
     * \struct mipi_csi_config_t
     * \brief MIPI CSI configuration structure
     */
    typedef struct
    {
        uint32_t clock_freq_mhz;            ///< MIPI clock frequency in MHz
        mipi_csi_lane_count_t lane_count;   ///< Number of data lanes
        mipi_csi_pixel_depth_t pixel_depth; ///< Bits per pixel
        mipi_csi_clk_mode_t clock_mode;     ///< Clock mode (continuous/non-continuous)
        mipi_csi_timing_t timing;           ///< Frame and line timing
        bool deskew_enable;                 ///< Enable lane deskew
    } mipi_csi_config_t;

    /**
     * Initialize MIPI CSI interface
     *
     * @param config MIPI CSI configuration
     * @return 0 on success, negative error code on failure
     */
    int mipi_csi_init(const mipi_csi_config_t *config);

    /**
     * Enable MIPI CSI receiver
     *
     * @return 0 on success, negative error code on failure
     */
    int mipi_csi_enable(void);

    /**
     * Disable MIPI CSI receiver
     *
     * @return 0 on success, negative error code on failure
     */
    int mipi_csi_disable(void);

    /**
     * Configure MIPI CSI parameters dynamically
     *
     * @param config New MIPI CSI configuration
     * @return 0 on success, negative error code on failure
     */
    int mipi_csi_configure(const mipi_csi_config_t *config);

    /**
     * Get MIPI CSI status
     *
     * @return 1 if enabled, 0 if disabled, negative error code on failure
     */
    int mipi_csi_get_status(void);

#ifdef __cplusplus
}
#endif

#endif /* STREAM_MPIX_MIPI_CSI_H_ */
