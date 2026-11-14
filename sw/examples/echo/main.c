/*
 * echo — read characters from the UART and echo them back, mirroring
 * the character onto the GPIO pins. Polling: the loop spins on the
 * receive-available status bit. The irq example does the same with the
 * receive interrupt.
 *
 * Interactive: connect a serial terminal on the board. `make run` only
 * shows the greeting, since nothing types in simulation.
 */

#include "bsp.h"

int main(void)
{
    uart_init(BAUD);

    uart_puts("echo\n");

    for (;;) {
        char c = uart_getc();       /* blocks on UART_STATUS_RX_AVAIL */

        gpio_write((uint32_t)(uint8_t)c);

        if (c == '\r')              /* terminals send CR, echo a newline */
            uart_putc('\n');
        uart_putc(c);

        if (c == 'q') {             /* quit */
            uart_puts("\nbye\n");
            return 0;
        }
    }
}
