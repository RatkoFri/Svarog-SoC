/*
 * soctest — program for the SoC and board-wrapper testbenches (tb/soc,
 * tb/fpga). It exercises every slave and both interrupt paths and
 * reports over the UART, so the testbench checks everything at the
 * pins. Each line proves a different path:
 *
 *   Svarog          boot, UART transmit, .rodata
 *   data=7 bss=0    .data in the image, .bss cleared by crt0
 *   bytes=44332211  byte stores into the RAM (APB strobes)
 *   gpio=a5a5       GPIO output register read back over the bus
 *   in=....         GPIO input pins (driven by the testbench)
 *   ticks=3         timer interrupt, taken three times
 *   fault=00000005  load from an unmapped address -> bus error ->
 *                   load access fault exception
 *   ready           now echoing: every received character comes back
 *                   through the UART receive interrupt, incremented
 *   done            after the character 'q' (echoed as 'r')
 *
 * The GPIO outputs show progress: 0xA5A5 early on, 0xFFFF at the end.
 */

#include "bsp.h"

#define TICK_CYCLES 2000u
#define UNMAPPED    (*(volatile uint32_t *)0x10000000u)

static volatile uint32_t counter = 7;       /* .data */
static volatile uint32_t zeroed;            /* .bss */

static volatile uint32_t ticks;
static volatile uint32_t fault_cause;
static volatile uint32_t quit;

static void on_timer(void)
{
    if (++ticks < 3u)
        timer_set_compare(timer_get_compare() + TICK_CYCLES);
    else
        timer_irq_disable();
}

static void on_uart(void)
{
    if (!uart_rx_ready())
        return;
    char c = (char)(UART_RX & 0xFFu);       /* the read clears the irq */
    uart_putc((char)(c + 1));
    if (c == 'q')
        quit = 1;
}

/* replaces the BSP default: record the cause and skip the instruction */
void exception_handler(uint32_t mcause, uint32_t mepc, uint32_t mtval)
{
    (void)mtval;
    fault_cause = 0x80000000u | mcause;     /* top bit: "a fault happened" */
    csr_write(mepc, mepc + 4u);
}

int main(void)
{
    volatile uint8_t bytes[4];

    uart_init(BAUD);
    uart_puts("Svarog\n");

    uart_puts("data=");
    print_udec(counter);
    uart_puts(" bss=");
    print_udec(zeroed);
    uart_putc('\n');

    bytes[0] = 0x11; bytes[1] = 0x22; bytes[2] = 0x33; bytes[3] = 0x44;
    uart_puts("bytes=");
    print_hex((uint32_t)bytes[0] | ((uint32_t)bytes[1] << 8)
              | ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 24));
    uart_putc('\n');

    gpio_write(0xA5A5u);
    uart_puts("gpio=");
    print_hex8((uint8_t)(gpio_read_out() >> 8));
    print_hex8((uint8_t)gpio_read_out());
    uart_putc('\n');

    uart_puts("in=");
    print_hex8((uint8_t)(gpio_read_in() >> 8));
    print_hex8((uint8_t)gpio_read_in());
    uart_putc('\n');

    /* timer interrupt */
    irq_attach(IRQ_TIMER, on_timer);
    timer_start();
    timer_set_compare(TICK_CYCLES);
    timer_irq_enable();
    irq_enable();
    while (ticks < 3u)
        ;
    uart_puts("ticks=");
    print_udec(ticks);
    uart_putc('\n');

    /* bus error: nothing is mapped at 0x1000_0000 */
    (void)UNMAPPED;
    uart_puts("fault=");
    print_hex(fault_cause & 0x7FFFFFFFu);
    uart_putc('\n');

    /* UART receive interrupt */
    irq_attach(IRQ_UART, on_uart);
    uart_rx_irq_enable();
    uart_puts("ready\n");
    while (!quit)
        ;
    uart_rx_irq_disable();

    uart_puts("\ndone\n");
    gpio_write(0xFFFFu);
    return 0;
}
