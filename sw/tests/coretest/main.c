/*
 * coretest — program for the CPU subsystem testbench (tb/core).
 *
 * That testbench has the CPU, the bridge and the RAM only: no UART to
 * report over. Results therefore go into a fixed block of RAM that the
 * testbench reads straight out of the memory array, and the testbench
 * drives the two interrupt inputs itself.
 *
 * RESULT[0]  progress marker: 1 = ready for interrupts, DONE at the end
 * RESULT[1]  sum 1..100                       (loops, branches)
 * RESULT[2]  123 * 456                        (libgcc multiply)
 * RESULT[3]  1000000 / 7                      (libgcc divide)
 * RESULT[4]  word assembled from four sb      (byte stores)
 * RESULT[5]  word assembled from two sh       (halfword stores)
 * RESULT[6]  sign/zero extending byte loads   (lb / lbu)
 * RESULT[7]  timer interrupts taken           (the testbench drops the
 * RESULT[8]  external interrupts taken         line when these change)
 * RESULT[9]  mcause of the ecall exception
 * RESULT[10] .data value, RESULT[11] .bss value
 */

#include "bsp.h"

/* 4 KiB below the top of the 64 KiB RAM: clear of the image and of the
 * stack, which starts at the top and stays far smaller than 4 KiB */
#define RESULT ((volatile uint32_t *)0x0000F000u)
#define DONE   0x600D600Du

static volatile uint32_t initialised = 0xCAFE0001u;     /* .data */
static volatile uint32_t zeroed;                        /* .bss */

static volatile uint32_t timer_irqs, external_irqs;

static void on_timer(void)
{
    RESULT[7] = ++timer_irqs;
}

static void on_external(void)
{
    RESULT[8] = ++external_irqs;
}

/* replaces the BSP default: record the cause and step over the ecall */
void exception_handler(uint32_t mcause, uint32_t mepc, uint32_t mtval)
{
    (void)mtval;
    RESULT[9] = mcause;
    csr_write(mepc, mepc + 4u);
}

int main(void)
{
    volatile uint32_t a = 123u, b = 456u, n = 1000000u, d = 7u;
    volatile uint8_t  bytes[4];
    volatile uint16_t halves[2];
    volatile int8_t   negative = -2;

    for (uint32_t i = 0; i < 12u; i++)
        RESULT[i] = 0;

    uint32_t sum = 0;
    for (uint32_t i = 1; i <= 100u; i++)
        sum += i;
    RESULT[1] = sum;
    RESULT[2] = a * b;
    RESULT[3] = n / d;

    bytes[0] = 0x11; bytes[1] = 0x22; bytes[2] = 0x33; bytes[3] = 0x44;
    RESULT[4] = (uint32_t)bytes[0] | ((uint32_t)bytes[1] << 8)
              | ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 24);

    halves[0] = 0xCAFE; halves[1] = 0xBEEF;
    RESULT[5] = (uint32_t)halves[0] | ((uint32_t)halves[1] << 16);

    /* -2 sign-extended is 0xFFFFFFFE, zero-extended 0xFE */
    RESULT[6] = (uint32_t)(int32_t)negative + (uint32_t)(uint8_t)negative;

    RESULT[10] = initialised;
    RESULT[11] = zeroed;

    __asm__ volatile ("ecall");

    irq_attach(IRQ_TIMER, on_timer);
    irq_attach(0, on_external);
    irq_enable();
    RESULT[0] = 1;                      /* tell the testbench we are ready */

    while (timer_irqs < 2u || external_irqs < 2u)
        ;

    irq_disable();
    RESULT[0] = DONE;
    return 0;
}
