/*
 * svarog.h — Svarog SoC memory map and register definitions.
 *
 * Mirrors config/svarog_soc_pkg.sv and the peripheral register maps in
 * rtl/periph/README.md. Keep the two in step.
 */

#ifndef SVAROG_H
#define SVAROG_H

#include <stdint.h>

#define REG32(addr) (*(volatile uint32_t *)(addr))

/* ------------------------------------------------------------------ */
/* address map: peripherals sit at 0x2000_0000 + n * 0x1000            */
/* ------------------------------------------------------------------ */
#define RAM_BASE    0x00000000u
#define UART_BASE   0x20000000u
#define TIMER_BASE  0x20001000u
#define GPIO_BASE   0x20002000u

/* ------------------------------------------------------------------ */
/* interrupts                                                          */
/* ------------------------------------------------------------------ */
/* External interrupt lines (index into the CPU's irq vector). They all
 * arrive as one machine external interrupt, mcause 11. */
#define IRQ_UART    0u
#define NUM_IRQS    1u
/* The timer has its own line: machine timer interrupt, mcause 7. */
#define IRQ_TIMER   31u

/* ------------------------------------------------------------------ */
/* UART (8N1, one-byte buffers)                                        */
/* ------------------------------------------------------------------ */
#define UART_CTRL    REG32(UART_BASE + 0x00)
#define UART_DIV     REG32(UART_BASE + 0x04)  /* clk cycles per bit */
#define UART_TX      REG32(UART_BASE + 0x08)  /* write starts a frame */
#define UART_RX      REG32(UART_BASE + 0x0C)  /* read clears RX_AVAIL */
#define UART_STATUS  REG32(UART_BASE + 0x10)

#define UART_CTRL_RX_IRQ_EN     (1u << 0)
#define UART_CTRL_TX_IRQ_EN     (1u << 1)

#define UART_STATUS_TX_EMPTY    (1u << 0)
#define UART_STATUS_RX_AVAIL    (1u << 1)
#define UART_STATUS_RX_OVERRUN  (1u << 2)

/* ------------------------------------------------------------------ */
/* timer (64-bit up counter with a 64-bit compare)                     */
/* ------------------------------------------------------------------ */
#define TIMER_CTRL     REG32(TIMER_BASE + 0x00)
#define TIMER_COUNT_LO REG32(TIMER_BASE + 0x04)  /* read-only */
#define TIMER_COUNT_HI REG32(TIMER_BASE + 0x08)  /* read-only */
#define TIMER_CMP_LO   REG32(TIMER_BASE + 0x0C)
#define TIMER_CMP_HI   REG32(TIMER_BASE + 0x10)

#define TIMER_CTRL_ENABLE  (1u << 0)
#define TIMER_CTRL_CLEAR   (1u << 1)   /* write 1: zero the counter */
#define TIMER_CTRL_IRQ_EN  (1u << 2)

/*
 * The interrupt is a level: IRQ_EN & (COUNT >= CMP). It is cleared by
 * moving the compare value ahead of the counter (as with mtimecmp), by
 * clearing the counter, or by dropping IRQ_EN.
 */

/* ------------------------------------------------------------------ */
/* GPIO                                                                */
/* ------------------------------------------------------------------ */
#define GPIO_OUT  REG32(GPIO_BASE + 0x00)  /* drives the pins, reads back */
#define GPIO_IN   REG32(GPIO_BASE + 0x04)  /* synchronised input pins */

/*
 * Peripheral registers are whole 32-bit words: always access them with
 * 32-bit loads and stores (which REG32 does).
 */

#endif /* SVAROG_H */
