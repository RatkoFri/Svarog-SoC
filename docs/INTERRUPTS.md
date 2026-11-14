# Interrupts

How an interrupt travels from a peripheral to a C handler, and what each side must
do. Example program: `sw/examples/irq`.

## The path

```
  peripheral ── Irq (level) ──> svarog_soc ──> cpu.sv ──> Hazard3
                                                            │ trap
                              sw/bsp/crt0.S  trap_entry <───┘ (mtvec)
                              sw/bsp/bsp.c   trap_handler ──> your handler
```

There are two interrupt inputs on the CPU:

| CPU input | Source | `mie` bit | `mcause` |
|-----------|--------|-----------|----------|
| `TimerIrq` | the timer | `MTIE` (7) | `0x8000_0007` machine timer |
| `Irq[NUM_IRQS-1:0]` | every other peripheral | `MEIE` (11) | `0x8000_000B` machine external |

The external lines are OR-ed inside the core into one interrupt. There is no
interrupt controller, so the CPU cannot tell which line fired — software asks each
peripheral (see "Handlers" below). The line indices are assigned in
`config/svarog_soc_pkg.sv`:

| Line | Constant | Peripheral |
|------|----------|------------|
| 0 | `IRQ_UART` | UART |

## Hardware rules

Every peripheral that can interrupt has an `Irq` output, and:

1. **`Irq` is a level, active high.** It stays high for as long as the cause exists
   and the interrupt is enabled in the peripheral. It is not a pulse.
2. **It has an enable bit** in one of the peripheral's registers, reset to 0, so a
   peripheral is silent until software asks for interrupts.
3. **It is cleared by a register access that the register map names** — reading a
   data register, writing a flag, moving a compare value. The banner comment of the
   module must say which.

The reference peripherals:

| Peripheral | Enable | Raised while | Cleared by |
|------------|--------|--------------|------------|
| UART, receive | `CTRL.RX_IRQ_EN` | a byte is waiting (`RX_AVAIL`) | reading `RX` |
| UART, transmit | `CTRL.TX_IRQ_EN` | the transmitter is idle (`TX_EMPTY`) | writing `TX`, or clearing the enable |
| Timer | `CTRL.IRQ_EN` | `COUNT >= CMP` | writing a larger `CMP`, `CTRL.CLEAR`, or clearing the enable |

Why a level and not a pulse: a pulse that arrives while interrupts are disabled is
lost. A level waits until the CPU is ready, and the handler's own register access
both serves the device and withdraws the request.

## What the CPU does

An interrupt is taken when its line is high, its `mie` bit is set and the global
enable `mstatus.MIE` is set. The CPU then:

1. saves the address of the interrupted instruction in `mepc`;
2. writes the cause to `mcause`;
3. clears `mstatus.MIE` (so the handler is not interrupted) and remembers the old
   value in `mstatus.MPIE`;
4. jumps to the address in `mtvec`.

`mret` at the end undoes steps 3 and 4. Exceptions (illegal instruction, bus error,
`ecall`) use the same mechanism, with the top bit of `mcause` clear.

## What the BSP does

- `crt0.S` points `mtvec` at `trap_entry` before `main` runs.
- `trap_entry` saves the caller-saved registers on the stack, calls
  `trap_handler(mcause, mepc, mtval)`, restores them and executes `mret`.
- `trap_handler` (in `bsp.c`) looks at `mcause`: for a timer interrupt it calls the
  attached timer handler; for an external interrupt it calls **every** attached
  external handler; for an exception it calls `exception_handler`.

Students only write handlers.

## Handlers

```c
#include "bsp.h"

static volatile uint32_t last_char;

static void on_uart(void)
{
    if (uart_rx_ready())                 /* is it really mine? */
        last_char = UART_RX & 0xFFu;     /* this read clears the interrupt */
}

int main(void)
{
    uart_init(BAUD);
    irq_attach(IRQ_UART, on_uart);       /* handler + enable in the CPU   */
    uart_rx_irq_enable();                /* enable in the peripheral      */
    irq_enable();                        /* global enable (mstatus.MIE)   */
    for (;;)
        ;
}
```

Rules for a handler:

- **Check your own peripheral first.** All external lines share one CPU interrupt,
  so your handler is also called when another peripheral interrupted. If your status
  flag is not set, return.
- **Clear the cause.** If the handler returns with `Irq` still high, it is entered
  again immediately and `main` never runs.
- **Keep it short**, and do not call blocking functions such as `uart_puts`: the CPU
  serves nothing else meanwhile.
- **Shared variables are `volatile`**, or the compiler may never re-read them in
  `main`.

Three enables are in series — peripheral, `mie` bit, `mstatus.MIE`. `irq_attach`
sets the middle one; the other two are explicit.

## Exceptions

`exception_handler(mcause, mepc, mtval)` is called for everything that is not an
interrupt. The BSP default prints the three values over the UART and stops:

```
TRAP mcause=00000005 mepc=000001a4 mtval=00000000
```

`mcause` 5 is a load access fault: the program read an address that no slave owns
(or a slave reported `ApbSlvErr`). 7 is the same for a store, 1 for an instruction
fetch, 2 an illegal instruction. Look `mepc` up in `build/<prog>.lst` to find the
instruction. Define your own `exception_handler` to replace the default.

## Verification

- `tb/unit/uart`, `tb/unit/timer`: `Irq` sets and clears as the register map says.
- `tb/core`: the testbench drives both CPU inputs; the C handlers run and return.
- `tb/soc`: timer interrupt, UART receive interrupt and a bus-error exception, end
  to end, observed at the pins.

## Adding an interrupt source

See step 4 of `ADDING_A_SLAVE.md`.
