# FPGA synthesis with Anvil

Building Svarog for the Digilent Nexys A7-100T using
[Anvil](https://logismith.github.io/Anvil/), which drives the open-source F4PGA
toolchain (Yosys + VPR — no Vivado).

Project: `fpga/anvil/`. Build script: `scripts/anvil_flow.py`.
Wrapper testbench: `tb/fpga/`.

> **Status: not yet run.** The flow below is HIPV's, adapted to this design. The
> board wrapper is verified in simulation (`tb/fpga`) and the script's source
> collection was checked, but sv2v, Anvil and the board have **not** been exercised
> on Svarog yet. The open points are listed under "Not verified yet" — read them
> before the first build.

## How Anvil works

A single-file Python CLI that orchestrates F4PGA, `sv2v` and `openFPGALoader`. It
adds a project model on top:

- **`config.json`** — board, top module, module list, params.
- **Modules** — versioned directories `modules/<name>@<version>/` with a
  `module.json` declaring `depends`.
- **Boards** — `boards.json` maps a board to its part, target and master XDC.
- **SoC flow** (optional) — a module containing `soc.json` makes Anvil compile
  `firmware/` and generate a RAM module.

The `Makefile` in a project is **regenerated on every synth**. Never edit it.

```
anvil build      # firmware (if any) + bitstream
anvil program    # openFPGALoader
anvil modules    # list available modules
anvil test       # Icarus-based testbench runner (separate from F4PGA)
```

## Constraints the flow works around

Found in HIPV by reading `anvil.py` and running the tools; they apply here unchanged.

**1. Source collection is not recursive.** Anvil collects sources with `os.listdir`,
so only files sitting *directly* in the project root are seen. A tree like
`rtl/cpu/hazard3/hdl/arith/` would be silently ignored. RTL must be flat — the build
script checks that every basename is unique and fails loudly if two would collide.

**2. Anvil runs sv2v once per file.** A file containing
`import svarog_soc_pkg::*;` converted in isolation has no package in scope, so the
design cannot go through Anvil's own conversion.

**3. The RTL needs sv2v.** The Yosys in F4PGA does not accept `import pkg::*`, so
bypassing sv2v is not an option either.

**4. Hazard3 uses `include`d headers.** Its Verilog pulls in `hazard3_config.vh` and
friends, which a flat directory of `.v` files would not find.

**The resolution:** `scripts/anvil_flow.py` does the conversion itself. It collects
our RTL plus the Hazard3 files named in the submodule's own list
(`rtl/cpu/hazard3/hdl/hazard3.f`), runs sv2v **once over the whole design** — with
the Hazard3 header directory on the include path — and drops finished `.v` files in
one scratch project directory. Packages resolve, headers are expanded, and Anvil
sees plain Verilog. Anvil itself stays unmodified and the submodule is never
touched.

The scratch directory (`build/anvil-work/` by default) is **wiped at the start of
every run**, so a build can never pick up stale Verilog from a previous one. Nothing
in it is meant to be edited or committed.

## Board wrapper

`fpga/anvil/top.sv` is board plumbing only:

| Concern | What it does |
|---------|--------------|
| Clock | The board clock pin drives the SoC directly. See "Clock frequency" below. |
| Reset | `CPU_RESETN` is active-low; two flops synchronise it into the clock domain and it is inverted to the SoC's active-high `reset`. |
| Power-on | A 4-bit counter holds reset for 15 clocks after configuration, so the SoC starts cleanly even if the button is never pressed. The combined reset is registered, because Hazard3 uses it as an asynchronous reset. |
| GPIO | 16 slide switches → `GpioIn`, 16 LEDs ← `GpioOut`. |
| UART | `uart_tx` → D4 (Digilent's `UART_RXD_OUT`), `uart_rx` ← C4 (`UART_TXD_IN`). The naming is from the USB bridge's point of view, which is easy to get backwards. |

The wrapper deliberately uses no packages and no type parameters, so it survives any
conversion path.

Pin assignments in `fpga/anvil/Nexys-A7-100T-Master.xdc` are taken from the Digilent
master XDC shipped with Anvil. SW8 and SW9 are in a 1.8 V bank (`LVCMOS18`).

> **Clock frequency.** Three things must agree on one number:
>
> - the clock that really reaches the SoC;
> - the XDC constraint (`create_clock -period 20.00`, i.e. 50 MHz), which timing
>   analysis checks;
> - `CPU_HZ` in `sw/rules.mk` (default `50000000`), from which the BSP computes the
>   UART divider and delays.
>
> The wrapper and the numbers are HIPV's. The oscillator on the Nexys A7 is 100 MHz,
> and the wrapper does not divide it, so the first number is **not confirmed** — this
> is `BUG-CLOCK` in `KnownBugs.md`. If the UART is garbled at the configured baud
> rate but readable at twice that rate, the SoC is running at 100 MHz: build the
> software with `CPU_HZ=100000000` and correct the XDC period.

## Build flow

```sh
make APP=hello sw          # build a program
make APP=hello fpga        # flatten, convert, synthesise with it baked in
make APP=hello program     # flash the board
```

or the script directly:

```sh
python3 scripts/anvil_flow.py build --firmware sw/examples/hello/build/hello.hex
python3 scripts/anvil_flow.py program        # flash the existing build
python3 scripts/anvil_flow.py prepare        # stop after flattening, inspect it
python3 scripts/anvil_flow.py clean          # remove the scratch directory
python3 scripts/anvil_flow.py build --work /tmp/svarog --keep --sv2v /path/to/sv2v
```

What a run does, in order:

1. wipe the scratch project directory (`--keep` skips this, for debugging);
2. read the Hazard3 file list; fail with a hint if the submodule is missing;
3. check every source has a unique basename;
4. run sv2v once over the package, Hazard3, our RTL and `top.sv`;
5. delete the empty file the package leaves behind (an empty output for anything
   else is an error);
6. copy `config.json` (with an empty module list), the XDC, and the firmware image;
7. run `anvil build`, then `anvil program` if asked.

The firmware image is referenced by `top.sv` as `INIT_FILE("firmware.hex")` and
resolved relative to the directory synthesis runs in — the scratch project root.
The program is part of the bitstream: a new program means a new `make fpga`.

## Verification before hardware

`tb/fpga/` simulates the wrapper itself, since bring-up bugs live in board plumbing
rather than in the SoC (which `tb/soc/` already covers): reset polarity, power-on
reset release, GPIO↔LED and switch↔GPIO mapping, and the UART on the right pins in
both directions, decoded as real 8N1 frames. Run with `make` in `tb/fpga`.

Two consequences of cocotb running every test in one simulation shaped this
testbench, and both are easy to trip over:

- **The power-on-reset test must stay first** — power-on state exists only once.
- **Every test starts its own clock and presses the reset button.** cocotb cancels
  the coroutines a test started when that test ends, so a shared clock would stop
  after the first test; and the program only runs at boot, so a test that watches
  boot has to restart the SoC itself.

## Not verified yet

Each of these is a first-build risk. None has been tried on Svarog.

- **sv2v over Hazard3.** The core is plain Verilog with `include`s inside parameter
  lists and `` `default_nettype none ``; the single sv2v pass is expected to handle
  it, but has not been run. If it fails, run `anvil_flow.py prepare` and look at the
  sv2v message.
- **F4PGA synthesis of Hazard3.** The core is known to build with Yosys for other
  FPGAs upstream; the F4PGA Yosys version and VPR have not seen it here. Its
  asynchronous reset flops and its register file (`RESET_REGFILE = 0`, meant to
  infer RAM) are the things to watch in the synthesis log.
- **Block RAM inference.** `sync_single_port_RAM` with `$readmemh` is the same style
  HIPV's dual-port RAM used successfully; the single-port, read-first variant is
  expected to map to `RAMB36E1` as well.
- **Timing.** HIPV met 20 ns and not 10 ns. The longest path here probably runs
  through the APB RAM's read-merge-write. No timing report exists yet.
- **Clock frequency** — `BUG-CLOCK`, above.
- **Docker image.** `docker/` is HIPV's image with the names changed; it has not
  been rebuilt for this repository.

## Things to expect on first bring-up

- **Baud rate.** The BSP computes the UART divider as `CPU_HZ / BAUD`. The defaults
  (`CPU_HZ=50000000`, `BAUD=19200`) give 2604 clock cycles per bit. Set the terminal
  to 19200 8N1.
- **Reset button.** `CPU_RESETN` is active-low, and is the red button, not one of
  the coloured push buttons.
- **BRAM budget.** 64 KiB of memory is 16 RAMB36 of 135.

## Not used

`anvil test` (Icarus) would hit the same per-file sv2v limitation as synthesis; all
verification uses cocotb + Verilator instead. Anvil's `soc.json` firmware flow is
deliberately unused — it assumes its own `link.ld`, `startup.S` and generated RAM
module, which would replace the `sw/` toolchain and the APB RAM.
