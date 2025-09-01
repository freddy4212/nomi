#include <stdio.h>
#include "WE2_device.h"
#include "WE2_core.h"
#include "board.h"
#include "xprintf.h"

int main(void)
{
	
	board_init();

    while (1)
    {
        xprintf("c hello world\n");
        board_delay_ms(1000);
    }
	return 0;

}