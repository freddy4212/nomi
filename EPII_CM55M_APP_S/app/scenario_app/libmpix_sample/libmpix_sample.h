

#ifndef APP_SCENARIO_LIBMPIX_SAMPLE_
#define APP_SCENARIO_LIBMPIX_SAMPLE_

#define APP_BLOCK_FUNC() do{ \
	__asm volatile("b    .");\
	}while(0)

int app_main(void);

#endif /* APP_SCENARIO_LIBMPIX_SAMPLE_ */
