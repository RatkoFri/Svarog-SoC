/*
 * bsp.c — Svarog SoC drivers and the C side of trap handling.
 */

#include "bsp.h"

/* ------------------------------------------------------------------ */
/* UART                                                               */
/* ------------------------------------------------------------------ */

void uart_init(uint32_t baud)
{
    /* DIV is the number of core clocks per bit */
    UART_DIV = CPU_HZ / baud;
    UART_CTRL = 0;
}

void uart_putc(char c)
{
    while (!(UART_STATUS & UART_STATUS_TX_EMPTY))
        ;                       /* wait for the transmitter */
    UART_TX = (uint8_t)c;
}

void uart_puts(const char *s)
{
    while (*s)
        uart_putc(*s++);
}

int uart_rx_ready(void)
{
    return (UART_STATUS & UART_STATUS_RX_AVAIL) != 0;
}

char uart_getc(void)
{
    while (!uart_rx_ready())
        ;
    return (char)(UART_RX & 0xFFu);
}

/* ------------------------------------------------------------------ */
/* formatted output                                                    */
/* ------------------------------------------------------------------ */

void print_udec(uint32_t v)
{
    char buf[10];
    int n = 0;

    if (v == 0) {
        uart_putc('0');
        return;
    }
    while (v > 0 && n < 10) {
        buf[n++] = (char)('0' + (v % 10u));
        v /= 10u;
    }
    while (n > 0)
        uart_putc(buf[--n]);
}

void print_dec(int32_t v)
{
    if (v < 0) {
        uart_putc('-');
        /* negate as unsigned so INT32_MIN survives */
        print_udec((uint32_t)0 - (uint32_t)v);
    } else {
        print_udec((uint32_t)v);
    }
}

static char hex_digit(uint32_t nibble)
{
    return (char)(nibble < 10u ? '0' + nibble : 'a' + nibble - 10u);
}

void print_hex(uint32_t v)
{
    for (int i = 28; i >= 0; i -= 4)
        uart_putc(hex_digit((v >> i) & 0xFu));
}

void print_hex8(uint8_t v)
{
    uart_putc(hex_digit((uint32_t)(v >> 4) & 0xFu));
    uart_putc(hex_digit((uint32_t)v & 0xFu));
}

/* ------------------------------------------------------------------ */
/* timer                                                               */
/* ------------------------------------------------------------------ */

void timer_start(void)
{
    /* zero the counter and run; the interrupt enable is left as it is */
    TIMER_CTRL = (TIMER_CTRL & TIMER_CTRL_IRQ_EN)
               | TIMER_CTRL_CLEAR | TIMER_CTRL_ENABLE;
}

void timer_stop(void)
{
    TIMER_CTRL = TIMER_CTRL & ~TIMER_CTRL_ENABLE;
}

uint64_t timer_get(void)
{
    /* Re-read the high word to detect a carry between the two reads. */
    uint32_t hi = TIMER_COUNT_HI;
    uint32_t lo = TIMER_COUNT_LO;
    uint32_t hi2 = TIMER_COUNT_HI;

    if (hi != hi2) {
        lo = TIMER_COUNT_LO;            /* low word wrapped, re-read it */
        hi = hi2;
    }
    return ((uint64_t)hi << 32) | lo;
}

void timer_set_compare(uint64_t value)
{
    /* Park the low word at its maximum first, so the comparison cannot
     * match a half-written value (the mtimecmp idiom). */
    TIMER_CMP_LO = 0xFFFFFFFFu;
    TIMER_CMP_HI = (uint32_t)(value >> 32);
    TIMER_CMP_LO = (uint32_t)value;
}

uint64_t timer_get_compare(void)
{
    return ((uint64_t)TIMER_CMP_HI << 32) | TIMER_CMP_LO;
}

void timer_irq_enable(void)
{
    TIMER_CTRL = TIMER_CTRL | TIMER_CTRL_IRQ_EN;
}

void timer_irq_disable(void)
{
    TIMER_CTRL = TIMER_CTRL & ~TIMER_CTRL_IRQ_EN;
}

void delay_cycles(uint32_t cycles)
{
    uint64_t target = timer_get() + cycles;
    while (timer_get() < target)
        ;
}

/* ------------------------------------------------------------------ */
/* interrupts and exceptions                                           */
/* ------------------------------------------------------------------ */

static irq_handler_t timer_handler;
static irq_handler_t external_handlers[NUM_IRQS];

void irq_attach(uint32_t irq, irq_handler_t handler)
{
    if (irq == IRQ_TIMER) {
        timer_handler = handler;
        csr_set(mie, MIE_MTIE);
    } else if (irq < NUM_IRQS) {
        external_handlers[irq] = handler;
        csr_set(mie, MIE_MEIE);
    }
}

void irq_detach(uint32_t irq)
{
    if (irq == IRQ_TIMER) {
        csr_clear(mie, MIE_MTIE);
        timer_handler = 0;
    } else if (irq < NUM_IRQS) {
        external_handlers[irq] = 0;
        for (uint32_t i = 0; i < NUM_IRQS; i++)
            if (external_handlers[i])
                return;                 /* another line is still in use */
        csr_clear(mie, MIE_MEIE);
    }
}

void irq_enable(void)
{
    csr_set(mstatus, MSTATUS_MIE);
}

void irq_disable(void)
{
    csr_clear(mstatus, MSTATUS_MIE);
}

__attribute__((weak))
void exception_handler(uint32_t mcause, uint32_t mepc, uint32_t mtval)
{
    uart_puts("\nTRAP mcause=");
    print_hex(mcause);
    uart_puts(" mepc=");
    print_hex(mepc);
    uart_puts(" mtval=");
    print_hex(mtval);
    uart_putc('\n');
    for (;;)
        ;                               /* stop here */
}

/*
 * Called from trap_entry in crt0.S with the caller-saved registers
 * already on the stack. Runs with interrupts disabled (the CPU clears
 * mstatus.MIE on trap entry and mret restores it).
 */
void trap_handler(uint32_t mcause, uint32_t mepc, uint32_t mtval)
{
    if (!(mcause & MCAUSE_INTERRUPT)) {
        exception_handler(mcause, mepc, mtval);
        return;
    }

    uint32_t cause = mcause & ~MCAUSE_INTERRUPT;

    if (cause == MCAUSE_M_TIMER) {
        if (timer_handler)
            timer_handler();
        else
            csr_clear(mie, MIE_MTIE);   /* nobody to clear it: mask it */
    } else if (cause == MCAUSE_M_EXTERNAL) {
        int handled = 0;
        for (uint32_t i = 0; i < NUM_IRQS; i++)
            if (external_handlers[i]) {
                external_handlers[i]();
                handled = 1;
            }
        if (!handled)
            csr_clear(mie, MIE_MEIE);
    }
}
