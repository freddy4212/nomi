#ifndef EVENT_HANDLER_CONFIG_H
#define EVENT_HANDLER_CONFIG_H

/* Event Handler configuration header */
/* This file provides unified interface for different event handler modules */

#ifdef __cplusplus
extern "C" {
#endif

/* Module availability checks */
#define HAS_EVT_DATAPATH()      (defined(EVT_DATAPATH_ENABLED))
#define HAS_EVT_I2CCOMM()       (defined(EVT_I2CCOMM_ENABLED))
#define HAS_EVT_UARTCOMM()      (defined(EVT_UARTCOMM_ENABLED))
#define HAS_EVT_CM55MMB()       (defined(EVT_CM55MMB_ENABLED))
#define HAS_EVT_CM55MMB_NBAPP() (defined(EVT_CM55MMB_NBAPP_ENABLED))
#define HAS_EVT_CM55MTIMER()    (defined(EVT_CM55MTIMER_ENABLED))
#define HAS_EVT_CM55STIMER()    (defined(EVT_CM55STIMER_ENABLED))

/* Include appropriate headers based on enabled modules */
#ifdef EVT_DATAPATH_ENABLED
    #include "evt_datapath/evt_datapath.h"
    #define EVENT_HANDLER_DATAPATH_AVAILABLE
#endif

#ifdef EVT_I2CCOMM_ENABLED
    #include "evt_i2ccomm/evt_i2ccomm.h"
    #define EVENT_HANDLER_I2CCOMM_AVAILABLE
#endif

#ifdef EVT_UARTCOMM_ENABLED
    #include "evt_uartcomm/evt_uartcomm.h"
    #define EVENT_HANDLER_UARTCOMM_AVAILABLE
#endif

#ifdef EVT_CM55MMB_ENABLED
    #include "evt_cm55mmb/evt_cm55mmb.h"
    #define EVENT_HANDLER_CM55MMB_AVAILABLE
#endif

#ifdef EVT_CM55MMB_NBAPP_ENABLED
    #include "evt_cm55mmb_nbapp/evt_cm55mmb_nbapp.h"
    #define EVENT_HANDLER_CM55MMB_NBAPP_AVAILABLE
#endif

#ifdef EVT_CM55MTIMER_ENABLED
    #include "evt_cm55mtimer/evt_cm55mtimer.h"
    #define EVENT_HANDLER_CM55MTIMER_AVAILABLE
#endif

#ifdef EVT_CM55STIMER_ENABLED
    #include "evt_cm55stimer/evt_cm55stimer.h"
    #define EVENT_HANDLER_CM55STIMER_AVAILABLE
#endif

/**
 * @brief Get list of enabled event handler modules
 * @return String describing enabled modules
 */
static inline const char* event_handler_get_enabled_modules(void) {
    static char modules[256] = "";
    
    if (modules[0] == '\0') {  // Build string only once
        #ifdef EVT_DATAPATH_ENABLED
        strcat(modules, "EVT_DATAPATH ");
        #endif
        #ifdef EVT_I2CCOMM_ENABLED
        strcat(modules, "EVT_I2CCOMM ");
        #endif
        #ifdef EVT_UARTCOMM_ENABLED
        strcat(modules, "EVT_UARTCOMM ");
        #endif
        #ifdef EVT_CM55MMB_ENABLED
        strcat(modules, "EVT_CM55MMB ");
        #endif
        #ifdef EVT_CM55MMB_NBAPP_ENABLED
        strcat(modules, "EVT_CM55MMB_NBAPP ");
        #endif
        #ifdef EVT_CM55MTIMER_ENABLED
        strcat(modules, "EVT_CM55MTIMER ");
        #endif
        #ifdef EVT_CM55STIMER_ENABLED
        strcat(modules, "EVT_CM55STIMER ");
        #endif
        
        if (modules[0] == '\0') {
            strcpy(modules, "None");
        }
    }
    
    return modules;
}

/**
 * @brief Initialize all enabled event handler modules
 * @return 0 on success, negative on error
 */
static inline int event_handler_init_all(void) {
    int ret = 0;
    
    #ifdef EVT_DATAPATH_ENABLED
    // Initialize data path event handler
    // ret |= evt_datapath_init();
    #endif
    
    #ifdef EVT_I2CCOMM_ENABLED
    // Initialize I2C communication event handler
    // ret |= evt_i2ccomm_init();
    #endif
    
    #ifdef EVT_UARTCOMM_ENABLED
    // Initialize UART communication event handler
    // ret |= evt_uartcomm_init();
    #endif
    
    #ifdef EVT_CM55MMB_ENABLED
    // Initialize CM55M mailbox event handler
    // ret |= evt_cm55mmb_init();
    #endif
    
    #ifdef EVT_CM55MMB_NBAPP_ENABLED
    // Initialize CM55M mailbox non-blocking app event handler
    // ret |= evt_cm55mmb_nbapp_init();
    #endif
    
    #ifdef EVT_CM55MTIMER_ENABLED
    // Initialize CM55M timer event handler
    // ret |= evt_cm55mtimer_init();
    #endif
    
    #ifdef EVT_CM55STIMER_ENABLED
    // Initialize CM55S timer event handler
    // ret |= evt_cm55stimer_init();
    #endif
    
    return ret;
}

#ifdef __cplusplus
}
#endif

#endif /* EVENT_HANDLER_CONFIG_H */
