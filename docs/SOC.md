# Svarog SoC

`rtl/top/svarog_soc.sv` is the complete system: the Hazard3 core, the AHB-to-APB
bridge, the APB decoder and return mux, the RAM and three reference peripherals. It
boots from a memory image applied at elaboration — no boot ROM, no JTAG, no SPI
loader.

Testbench: `tb/soc/`. Component docs: `rtl/cpu/README.md`, `INTERCONNECT.md`,
`MEMORY.md`, `INTERRUPTS.md`, `rtl/periph/README.md`.

## Structure

```
              ┌──────────────────┐
              │  cpu (Hazard3)   │<──── Irq[NUM_IRQS-1:0], TimerIrq
              └────────┬─────────┘
                       │ AHB-Lite
              ┌────────┴─────────┐
              │    ahb_to_apb    │  the only APB master
              └────────┬─────────┘
                       │ APB
              ┌────────┴─────────┐
              │ apb_decoder/_mux │  one-hot PSEL, read-data mux
              └──┬─────┬─────┬───┴──┐
                RAM   UART  TIMER  GPIO
                       │      │      └─> GpioOut / GpioIn
                       │      └─ Irq ──> TimerIrq
                       └─ Tx/Rx, Irq ──> Irq[IRQ_UART]
```

**Everything is on APB, the RAM included.** One bus, one decoder, one way to add a
slave. The cost is speed: every instruction fetch is a two-cycle APB transfer. That
is accepted for a teaching system.

## Ports

| Port | Dir | Description |
|------|-----|-------------|
| `clk`, `reset` | in | Clock and synchronous, active-high reset |
| `Tx`, `Rx` | out/in | UART serial pins |
| `GpioIn`, `GpioOut` | in/out | GPIO pins, `GPIO_WIDTH` bits each |

## Parameters

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `RAM_ADDR_WIDTH` | 14 | RAM depth in words (2^14 = 64 KiB) |
| `INIT_FILE` | `""` | `$readmemh` program image, applied at elaboration |
| `GPIO_WIDTH` | 16 | GPIO pin count (the board has 16 LEDs and 16 switches) |

The address map, the slave count and the interrupt assignment are not parameters:
they come from `config/svarog_soc_pkg.sv`, which the interconnect, the CPU adapter and
this module all import.

## Address map

| Slave | Index | Base | Size |
|-------|-------|------|------|
| RAM | 0 | `0x0000_0000` | 64 KiB |
| UART | 1 | `0x2000_0000` | 4 KiB |
| TIMER | 2 | `0x2000_1000` | 4 KiB |
| GPIO | 3 | `0x2000_2000` | 4 KiB |

Peripherals live at `0x2000_0000 + n * 0x1000`. An access to any other address ends
in a bus error, which the CPU takes as an access-fault exception (`INTERCONNECT.md`).
Register maps: `rtl/periph/README.md`.

## Reset

`reset` is synchronous and active high everywhere in our RTL, so it must be held with
the clock running — the SoC has no gated clocks, so this is always satisfied. The
one exception is inside the Hazard3 core, which resets asynchronously; see
`rtl/cpu/README.md` for why that is safe here. The RAM has no reset: its contents are
the image, as modified by the program. `test_reset_is_synchronous` checks that a
mid-run reset clears the GPIO outputs and the program restarts from address 0.

## Running a program

Use `sw/`: `make run` in any example builds the image and executes it on the SoC
testbench, printing the program's UART output (`sw/README.md`). By hand:

```sh
riscv64-unknown-elf-objcopy -O binary prog.elf prog.bin
python3 scripts/mkmem.py --bin prog.bin -o prog.hex --words 16384
make -C tb/soc MODULE=test_sw INIT_FILE=$PWD/prog.hex UART_DIV=<clocks per bit>
```

## Verification

`tb/soc/test_svarog_soc.py` runs one C program (`sw/tests/soctest`) that exercises
every slave and both interrupt paths and reports **over the UART**, so the checks
happen at the SoC pins rather than by reaching inside the design. Each line of its
output proves a different path:

| Line | Proves |
|------|--------|
| `Svarog` | boot from the image, UART transmit, `.rodata` |
| `data=7 bss=0` | `.data` is in the image, `crt0` clears `.bss` |
| `bytes=44332211` | byte stores into the RAM (bridge strobes, RAM merge) |
| `gpio=a5a5` | GPIO output register read back over the bus |
| `in=1234` | GPIO input pins, driven by the testbench |
| `ticks=3` | timer interrupt taken three times and cleared by software |
| `fault=00000005` | load from an unmapped address → bus error → load access fault |
| `ready`, then echo | UART receive interrupt: characters sent to `Rx` come back incremented |
| `done` | the program ran to the end |

Other tests: GPIO pins driven, the timer interrupt line rising and falling three
times, and the synchronous reset restart.

## Toolchain note

Some Verilator packages (the pip wheel among them) ship `verilated.mk` with an empty
`CFG_CXXFLAGS_PCH_I`, which breaks the C++ build for designs large enough to use a
precompiled header. `tb/common/Makefile.include` detects that specific case and
supplies the correct `-include` flag; a correctly packaged Verilator is left
untouched.

## Not implemented

- No debug module, so no GDB on the board (`rtl/cpu/README.md`).
- No interrupt controller: all external lines share one CPU interrupt and software
  finds the source by asking each peripheral (`INTERRUPTS.md`).
- No memory protection: a program can overwrite its own code.
