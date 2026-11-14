/*
 * blink — walk a bit across the 16 GPIO outputs, using the timer for
 * the delay. On the FPGA this is an LED chaser; in simulation the
 * pattern is visible on GpioOut (and echoed over the UART).
 */

#include "bsp.h"

#define STEPS 16

/* Step time in clock cycles: a quarter of a second on the board.
 * `make run` builds the simulated image with a short step instead
 * (SIM_DEFS in the Makefile). */
#ifndef DELAY_CYCLES
#define DELAY_CYCLES (CPU_HZ / 4u)
#endif

int main(void)
{
    uart_init(BAUD);
    timer_start();

    uart_puts("blink\n");

    for (;;) {
        for (int step = 0; step < STEPS; step++) {
            uint32_t pattern = 1u << step;
            gpio_write(pattern);

            /* report the pattern so the run is verifiable in simulation */
            print_hex8((uint8_t)(pattern >> 8));
            print_hex8((uint8_t)pattern);
            uart_putc('\n');

            delay_cycles(DELAY_CYCLES);
        }
    }
}
