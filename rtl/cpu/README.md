# Processor: Hazard3

The Svarog SoC uses [Hazard3](https://github.com/Wren6991/Hazard3) by Luke Wren
(Apache-2.0) — the core family used in the RP2350. Verilog, 3-stage pipeline,
AHB-Lite master, standard RISC-V M-mode traps.

| | |
|---|---|
| Location | `rtl/cpu/hazard3/` — **git submodule**, not copied into this repository |
| Pinned version | tag **`v1.1.1`**, commit `8af992930f71a69b0e06c38734c1094f41a05ca0` (upstream `stable`) |
| Top module used | `hazard3_cpu_1port` (single AHB-Lite port) |
| Our adapter | `rtl/cpu/cpu.sv` |

Fetch it with `git clone --recursive`, or `git submodule update --init` in an
existing clone. Hazard3's own nested submodules are only needed for its own tests,
not for building the core — do not pass `--recursive` to `submodule update`.

## Rules

- **Never edit files inside `rtl/cpu/hazard3/`.** The version is frozen for the
  semester; changing the pinned tag is a deliberate, separate decision.
- If a fix to the core is ever unavoidable, it lives as a patch file in
  `rtl/cpu/patches/`, applied by the build, marked `SVAROG FIX`, and recorded in
  `KnownBugs.md`. There are none today.
- Configuration is done at instantiation, from `config/svarog_soc_pkg.sv` — never in
  the submodule's `hazard3_config.vh`.

## Configuration

Set in `svarog_soc_pkg.sv` (`CPU_*` constants) and applied in `cpu.sv`:

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `RESET_VECTOR` | `0x0000_0000` | first instruction: word 0 of the RAM |
| `MTVEC_INIT` | `0x0000_0000` | `crt0.S` sets the real trap vector |
| `EXTENSION_A`, `_C`, `_M` | 0 | plain **RV32I**; libgcc supplies multiply/divide |
| `CSR_M_MANDATORY`, `CSR_M_TRAP` | 1 | **Zicsr** and M-mode traps (`mtvec`, `mie`, `mcause`, ...) |
| `CSR_COUNTER` | 0 | no performance counters |
| `U_MODE`, `PMP_REGIONS` | 0 | M-mode only, no PMP |
| `DEBUG_SUPPORT` | 0 | no debug module (see below) |
| `NUM_IRQS` | from the package | external interrupt lines |
| `EXTENSION_XH3IRQ` | 0 (default) | no Hazard3 interrupt controller: external lines are OR-ed into `mip.meip` |

Software must be compiled for the same ISA: `-march=rv32i_zicsr -mabi=ilp32`
(`sw/rules.mk`).

## The adapter `cpu.sv`

Interface changes only; the core is instantiated as-is:

- project naming: `clk`, active-high `reset`, UpperCamelCase ports with an `Ahb`
  prefix;
- only the AHB-Lite signals the SoC uses are brought out (`AhbAddr`, `AhbWrite`,
  `AhbTrans`, `AhbSize`, `AhbWdata`, `AhbRdata`, `AhbReady`, `AhbResp`); burst,
  protection, lock, master-id and exclusive-access outputs are left unused;
- the power-control handshakes are tied back, debug and system-bus-access ports are
  tied off;
- `Irq[NUM_IRQS-1:0]` → `irq` (machine external interrupt, `mcause` 11),
  `TimerIrq` → `timer_irq` (machine timer interrupt, `mcause` 7).

**Reset.** Hazard3 resets asynchronously (`negedge rst_n`), which the project standard
does not use anywhere else. The adapter drives `rst_n` from the SoC's synchronous
`reset`, which comes from a flip-flop (`fpga/anvil/top.sv`), so both edges are aligned
to `clk` and the signal is glitch free.

## Lint

Hazard3's style is not the project standard, so the whole submodule is waived in
`config/cpu.vlt`. `cpu.sv` is not waived and compiles clean under Verilator `-Wall`.
Testbenches that include the core add `$(CPU_SOURCES)` and `EXTRA_ARGS += $(CPU_ARGS)`
(the include path for the core's `.vh` headers) from `tb/common/Makefile.include`.

## Debug (not available yet)

Hazard3 has a RISC-V debug module, and upstream shows its JTAG-DTM tunnelled through
the Artix-7 TAP (`BSCANE2`) on an Arty A7 with Vivado. Whether F4PGA handles `BSCANE2`
and whether OpenOCD reaches the Nexys A7's FTDI the same way is **not verified**, so
the core is built with `DEBUG_SUPPORT = 0` and there is no GDB-on-board flow.
