#include <stdio.h>
#include "WE2_device.h"
#include "WE2_core.h"
#include "board.h"
#include "xprintf.h"
#include "FreeRTOS.h"
#include "task.h"

void task_function(void *pvParameters)
{
    while (1)
    {
        xprintf("freertos hello world\n");
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

int main(void)
{

    board_init();

    // create task
    xTaskCreate(task_function, "task_name", 1024, NULL, 1, NULL);

    vTaskStartScheduler();

    for (;;)
        ;
    return 0;
}