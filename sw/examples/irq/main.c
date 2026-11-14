/*
 * irq — interrupts on the Svarog SoC.
 *
 *   timer interrupt   a periodic tick: the handler moves the compare
 *                     value one period ahead, which clears the
 *                     interrupt, and counts the tick
 *   UART interrupt    the handler reads the received character (the
 *                     read clears the interrupt) and hands it to main
 *
 * main only prints: everything that needs attention arrives through a
 * handler. Variables shared with a handler are volatile.
 */

#include "bsp.h"

/* Tick period in clock cycles: half a second on the board.
 * `make run` builds the simulated image with a short period instead
 * (SIM_DEFS in the Makefile). */
#ifndef TICK_CYCLES
#define TICK_CYCLES (CPU_HZ / 2u)
#endif

#define TICKS 5u

static volatile uint32_t ticks;
static volatile uint32_t rx_char;       /* 0x100 | character when valid */

static void on_timer(void)
{
    /* schedule the next tick: this also clears the interrupt */
    timer_set_compare(timer_get_compare() + TICK_CYCLES);
    ticks++;
}

static void on_uart(void)
{
    if (uart_rx_ready())
        rx_char = 0x100u | (UART_RX & 0xFFu);   /* reading RX clears it */
}

int main(void)
{
    uart_init(BAUD);
    uart_puts("irq\n");

    irq_attach(IRQ_TIMER, on_timer);
    irq_attach(IRQ_UART, on_uart);

    timer_start();
    timer_set_compare(TICK_CYCLES);
    timer_irq_enable();
    uart_rx_irq_enable();
    irq_enable();

    uint32_t printed = 0;
    for (;;) {
        if (printed != ticks && printed < TICKS) {
            printed++;
            gpio_write(printed);
            uart_puts("tick ");
            print_udec(printed);
            uart_putc('\n');
            if (printed == TICKS) {
                timer_irq_disable();
                uart_puts("type something\n");
            }
        }

        if (rx_char) {
            char c = (char)rx_char;
            rx_char = 0;
            uart_putc(c);
        }
    }
}
