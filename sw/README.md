# Svarog software

Bare-metal C for the Svarog SoC. No operating system and no C library; interrupts
and exceptions are handled by a small layer in the BSP.

```
sw/
├── bsp/            startup and drivers
│   ├── crt0.S      reset entry (gp/sp, zero .bss, call main) and trap entry
│   ├── svarog.h    memory map, peripheral registers, interrupt numbers
│   └── bsp.h/.c    UART, timer, GPIO drivers, print helpers, interrupt layer
├── link.ld         linker script (see "Memory layout" below)
├── rules.mk        shared build rules
├── examples/
│   ├── hello/      UART output, .data and .bss
│   ├── blink/      GPIO walking bit with timer delays
│   ├── timer/      reading the 64-bit counter
│   ├── echo/       UART receive by polling (interactive)
│   └── irq/        timer interrupt and UART receive interrupt
└── tests/          programs the testbenches run (tb/core, tb/soc, tb/fpga)
```

## Toolchain

Any RV32I bare-metal GCC with an `rv32i/ilp32` multilib. On Debian/Ubuntu:

```sh
sudo apt install gcc-riscv64-unknown-elf
```

The default prefix is `riscv64-unknown-elf-` (it builds RV32I via multilib). Override
with `CROSS=`, and use `TOOLFLAGS=-B/path/to/bin/` if the toolchain lives outside its
configured prefix. The Docker image has everything (`make docker-shell`).

Programs are compiled for `rv32i_zicsr`: the core has no multiply, divide or
compressed instructions (`rtl/cpu/README.md`).

## Building and running

```sh
cd sw/examples/hello
make                 # -> build/hello.{elf,bin,hex,lst,map}
make run             # run it on the simulated SoC, print the UART output
make size dump clean
```

`make` in `sw/` builds every example; `make run` runs them all.

`build/<prog>.hex` is the `$readmemh` image for the SoC's `INIT_FILE` parameter —
synthesis-time initialization, the same file the FPGA flow puts in the bitstream
(`docs/MEMORY.md`). From the top level, `make APP=hello fpga` builds the bitstream
with it.

**`make run` simulates.** A real baud rate or a half-second delay would take
millions of simulated clock cycles, so `make run` builds a second image in
`build/sim/` with a fast UART (16 clocks per bit) and whatever `SIM_DEFS` the
example's Makefile sets to shorten its delays. The image in `build/` — the one for
the board — is not affected.

If an example has an `expected.txt`, `make run` checks that the UART output starts
with it and stops as soon as that much has been printed, so running an example is a
regression test, also for programs that never return. Without one it just prints
what the program produced.

Useful variables: `CPU_HZ` (default 50 MHz; used for baud maths and delays, must
match the real clock — see `BUG-CLOCK` in `KnownBugs.md`), `BAUD` (19200), `OPT`
(`-Os`), `DEFS` (extra `-D...`), `RAM_ADDR_WIDTH` (14 → 64 KiB, must match the SoC),
`RUN_CYCLES`.

## Memory layout

One RAM at address 0 holds everything (`docs/MEMORY.md`):

| Address | Contents |
|---------|----------|
| `0x0000_0000` | `.text`: `_start` (the reset vector), `trap_entry`, code |
| | `.rodata`, `.data`, `.bss` |
| | free |
| `0x0001_0000` (top) | stack, growing down |

The whole image is in the RAM from the start, so `.data` is linked where it runs and
there is no startup copy; `crt0.S` only zeroes `.bss`. The link fails if the image
leaves less than 2 KiB for the stack. Nothing checks the stack at run time.

Peripherals are at `0x2000_0000 + n * 0x1000`; the names are in `bsp/svarog.h`.
Reading or writing an address that nothing owns raises an exception.

## Interrupts

`docs/INTERRUPTS.md` has the whole story. In short:

```c
static void on_timer(void)
{
    timer_set_compare(timer_get_compare() + PERIOD);   /* clears the interrupt */
    ticks++;
}

irq_attach(IRQ_TIMER, on_timer);    /* handler + CPU enable for that source */
timer_irq_enable();                 /* enable in the peripheral             */
irq_enable();                       /* global enable                        */
```

A handler must clear the cause in the peripheral, must be short, and shares data
with `main` only through `volatile` variables. External interrupt handlers
(`IRQ_UART`, ...) are all called on any external interrupt, so each checks its own
peripheral first.

An exception — bus error, illegal instruction — prints
`TRAP mcause=... mepc=... mtval=...` over the UART and stops. Find `mepc` in
`build/<prog>.lst`.

## Notes on the C environment

- **RV32I has no multiply or divide.** GCC emits calls to libgcc helpers
  (`__mulsi3`, `__udivsi3`, ...), so `libgcc` is linked even though libc is not. Prefer
  shifts over `/` and `%` in hot code.
- **No libc**: no `printf`, `malloc`, or string functions. `bsp.h` provides
  `uart_puts`, `print_dec`, `print_udec`, `print_hex`.
- **`volatile` matters.** Peripheral registers are `volatile` in `svarog.h`; so must
  be every variable shared with an interrupt handler.
- **Peripheral registers are whole words.** Access them through `REG32` only; a
  `char` or `short` pointer to a register does not do what you expect, because
  peripherals ignore the byte lanes.
- **`main` returning** parks in a spin loop in `crt0.S`.
- The linker warns that the image has an RWX segment. That is accurate — code and
  data share one RAM — and harmless.

## Peripheral notes worth knowing

- **UART**: `DIV` is clock cycles per bit. No FIFO: read each byte before the next
  one arrives, or `RX_OVERRUN` is set and the older byte is lost.
- **Timer**: the interrupt is a level, `COUNT >= CMP`. Clear it by moving the compare
  ahead; `timer_set_compare` writes the two halves in an order that cannot match by
  accident.
- **GPIO**: 16 outputs (LEDs) and 16 inputs (switches).

Register maps: `rtl/periph/README.md`.
