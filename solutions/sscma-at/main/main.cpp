#include <stdio.h>
#include "WE2_device.h"
#include "WE2_core.h"
#include "board.h"
#include "xprintf.h"

#include "ma_codec.h"
#include "ma_server.h"
#include "resource.hpp"

static void __task(void *)
{
    MA_LOGD(MA_TAG, "Initializing Encoder");
    ma::EncoderJSON encoder;

    MA_LOGD(MA_TAG, "Initializing ATServer");
    ma::ATServer server(encoder);

    int ret = 0;

    MA_LOGD(MA_TAG, "Initializing ATServer services");
    ret = server.init();
    if (ret != MA_OK)
    {
        MA_LOGE(MA_TAG, "ATServer init failed: %d", ret);
    }

    MA_LOGD(MA_TAG, "Starting ATServer");
    ret = server.start();
    if (ret != MA_OK)
    {
        MA_LOGE(MA_TAG, "ATServer start failed: %d", ret);
    }

    MA_LOGD(MA_TAG, "ATServer started");
    while (1)
    {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

int main(void)
{

    board_init();

    puts("Build date: " __DATE__ " " __TIME__);
    if (xTaskCreate(__task, "__task", 20480, NULL, 3, NULL) != pdPASS)
    {
        puts("__task creation failed!");
        while (1)
        {
        }
    }

    vTaskStartScheduler();
    return 0;
}