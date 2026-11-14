# Svarog-SoC

Teaching RISC-V SoC for the NDN course (FRI UL): a Hazard3 core on an APB bus, built
with Anvil/F4PGA for the Digilent Nexys A7-100T, verified with cocotb + Verilator.

Named after Svarog, the Slavic god of fire and smithing: the processor comes ready
made, and the course is about forging the devices around it — APB peripherals and
their C drivers.

```
     Hazard3 (cpu.sv adapter)
              │ AHB-Lite
         ahb_to_apb bridge
              │ APB
   apb_decoder / apb_mux ──> one-hot PSEL, read-data mux
              │
     ram   uart   timer   gpio   ...   <your peripherals>
                  └──── Irq lines ────> Hazard3 irq / timer_irq
```

## Getting the sources

The processor is a git submodule, so clone recursively:

    git clone --recursive https://github.com/RatkoFri/Svarog-SoC.git

or, in an existing clone, `git submodule update --init`.

## Where things are

- Coding standard: `NamingConvention.md`; project layout: `FolderStructure.md`
- SoC top level: `docs/SOC.md`; bus: `docs/INTERCONNECT.md`; memory: `docs/MEMORY.md`
- Interrupts, from the peripheral to the C handler: `docs/INTERRUPTS.md`
- **Adding your own peripheral: `docs/ADDING_A_SLAVE.md`**
- Processor (Hazard3, pinned tag, configuration): `rtl/cpu/README.md`
- Reference peripherals and their register maps: `rtl/periph/README.md`
- Software (bare-metal C, BSP, examples): `sw/README.md`
- FPGA synthesis (Anvil / F4PGA, Nexys A7-100T): `docs/FPGA.md`
- Known issues: `KnownBugs.md`

## Status

| Component | State |
|-----------|-------|
| CPU adapter (`cpu.sv`) around Hazard3 v1.1.1, RV32I + Zicsr | implemented + tested |
| interconnect (`ahb_to_apb`, `apb_decoder`, `apb_mux`) | implemented + tested |
| memory (`apb_ram`, synth-time init) | implemented + tested |
| reference peripherals (`uart`, `timer`, `gpio`) with interrupts | implemented + tested |
| `svarog_soc` top level | implemented + tested |
| software: BSP with trap handling, linker script, C examples | implemented + tested in simulation |
| FPGA flow: Anvil project, board wrapper, flattening script | wrapper simulated; **bitstream not built yet, nothing verified on the board** |
| lecture system, lab handouts and templates | not started (`lectures/`, `labs/`) |

## Verification

cocotb + Verilator at every level. Run any testbench with:

    cd tb/unit/<module>   # or tb/interconnect, tb/core, tb/soc, tb/fpga
    make                  # options: WAVES=1, TESTCASE=<test>, SIM_BUILD=<dir>

`make test` at the top level runs them all. `tb/core`, `tb/soc` and `tb/fpga` run real
C programs from `sw/tests/`, so they need the RISC-V GCC as well.

If the repo is on a cloud-synced drive, build outside it: `make SIM_BUILD=/tmp/sb`.
Python dependencies: `pip install -r requirements.txt`; Verilator >= 5.036 required.

## Software and FPGA in one line

    make APP=blink sw         # compile sw/examples/blink
    make APP=blink fpga       # ... and build a bitstream with it baked in
    make APP=blink program    # flash the board
    make -C sw/examples/blink run   # or run it on the simulated SoC

## Docker

`docker/` holds an image with the whole toolchain: Anvil, F4PGA, sv2v, the
RISC-V GCC, openFPGALoader, and Verilator + cocotb for the testbenches. The
top-level Makefile drives it:

    make docker-build              # build the image (once; downloads several GB)
    make docker-shell              # shell in the container, repo mounted at /work
    make docker-all APP=blink      # any Makefile target, prefixed with docker-

Inside the container the user has your UID/GID, so generated files belong to you.

**USB on Linux:** the container sees USB devices automatically, including a
board plugged in after it started, so `make docker-program` and the UART
console (`/dev/ttyUSB*`) work. `docker/run.sh` bind-mounts the host's `/dev`
and lets the container use USB, USB-serial and CDC-ACM devices, without
running it `--privileged`.

**macOS / Windows:** Docker Desktop runs containers in a VM that cannot reach
USB devices. Build in the container, then flash from the host:

    make docker-fpga APP=blink
    brew install openfpgaloader    # once
    make program-host

## Acknowledgments

- The processor is [Hazard3](https://github.com/Wren6991/Hazard3) by Luke Wren
  (Apache-2.0), used unmodified as a git submodule.
- The SoC structure, verification flow and tooling follow the author's
  [HIPV SoC](https://github.com/RatkoFri/HIPV-SoC).
- The Docker setup is based on [anvil-docker](https://github.com/jurevreca12/anvil-docker)
  by Jure Vreča ([`jurevreca12`](https://github.com/jurevreca12)), which packages the
  [Anvil](https://github.com/LogiSmith/Anvil) / F4PGA installer in a container.
