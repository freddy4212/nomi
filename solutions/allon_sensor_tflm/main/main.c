#include <stdio.h>
#include "WE2_device.h"
#include "WE2_core.h"
#include "board.h"
#include "xprintf.h"
#include "allon_sensor_tflm.h"

int main(void)
{

    board_init();

    app_main();

    for (;;)
    {
        board_delay_ms(1000);
    }

    return 0;
}