/*
 * bsp.h — small board-support layer for the Svarog SoC.
 *
 * Polling drivers for the UART, timer and GPIO, tiny print helpers, and
 * the interrupt layer: crt0.S saves the context and calls the C trap
 * handler in bsp.c, which calls the handler you attached. You only
 * write handlers.
 */

#ifndef BSP_H
#define BSP_H

#include <stdint.h>
#include "svarog.h"

/* Core clock frequency in Hz, used to convert baud rates and delays.
 * The default is the SoC clock the XDC constrains. Override at build
 * time with -DCPU_HZ=... */
#ifndef CPU_HZ
#define CPU_HZ 50000000u
#endif

/* ---- UART -------------------------------------------------------- */
void uart_init(uint32_t baud);
void uart_putc(char c);             /* blocking */
void uart_puts(const char *s);      /* no newline translation */
int  uart_rx_ready(void);
char uart_getc(void);               /* blocking */
static inline void uart_rx_irq_enable(void)
{ UART_CTRL = UART_CTRL | UART_CTRL_RX_IRQ_EN; }
static inline void uart_rx_irq_disable(void)
{ UART_CTRL = UART_CTRL & ~UART_CTRL_RX_IRQ_EN; }

/* ---- formatted output (tiny, no libc) ---------------------------- */
void print_dec(int32_t v);
void print_udec(uint32_t v);
void print_hex(uint32_t v);         /* 8 digits, no 0x prefix */
void print_hex8(uint8_t v);

/* ---- GPIO -------------------------------------------------------- */
static inline void gpio_write(uint32_t value) { GPIO_OUT = value; }
static inline uint32_t gpio_read_out(void)    { return GPIO_OUT; }
static inline uint32_t gpio_read_in(void)     { return GPIO_IN; }

/* ---- timer ------------------------------------------------------- */
void     timer_start(void);                  /* clear, then run freely */
void     timer_stop(void);
uint64_t timer_get(void);                    /* 64-bit, tear-free read */
void     timer_set_compare(uint64_t value);
uint64_t timer_get_compare(void);
void     timer_irq_enable(void);
void     timer_irq_disable(void);
void     delay_cycles(uint32_t cycles);      /* busy wait on the timer */

/* ---- interrupts -------------------------------------------------- */
typedef void (*irq_handler_t)(void);

/*
 * Attach a handler to an interrupt source and enable that source in
 * the CPU. `irq` is IRQ_TIMER or an external line (IRQ_UART, ...).
 *
 * All external lines share one CPU interrupt, so on an external
 * interrupt every attached external handler is called: a handler must
 * check its own peripheral's status and return if there is nothing to
 * do. Interrupts are levels — the handler must clear the cause in the
 * peripheral (as its register map says), or it is called again.
 */
void irq_attach(uint32_t irq, irq_handler_t handler);
void irq_detach(uint32_t irq);
void irq_enable(void);              /* global enable (mstatus.MIE) */
void irq_disable(void);

/*
 * Called for every exception (not interrupt): illegal instruction, bus
 * error, ecall, ... The default prints mcause/mepc/mtval over the UART
 * and stops. Define your own function with this name to replace it.
 */
void exception_handler(uint32_t mcause, uint32_t mepc, uint32_t mtval);

/* ---- CSR access -------------------------------------------------- */
#define csr_read(csr) __extension__({ uint32_t v_; \
    __asm__ volatile ("csrr %0, " #csr : "=r"(v_)); v_; })
#define csr_write(csr, value) \
    __asm__ volatile ("csrw " #csr ", %0" : : "r"((uint32_t)(value)))
#define csr_set(csr, bits) \
    __asm__ volatile ("csrs " #csr ", %0" : : "r"((uint32_t)(bits)))
#define csr_clear(csr, bits) \
    __asm__ volatile ("csrc " #csr ", %0" : : "r"((uint32_t)(bits)))

#define MSTATUS_MIE  (1u << 3)
#define MIE_MTIE     (1u << 7)     /* machine timer interrupt */
#define MIE_MEIE     (1u << 11)    /* machine external interrupt */

#define MCAUSE_INTERRUPT    0x80000000u
#define MCAUSE_M_TIMER      7u
#define MCAUSE_M_EXTERNAL   11u

#endif /* BSP_H */
