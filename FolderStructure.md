## Folder organization for Svarog-SoC

1. Top-level layout

   ```
   Svarog-SoC/
   ├── config/
   ├── docs/
   ├── rtl/
   ├── tb/
   ├── sw/
   ├── fpga/
   ├── scripts/
   ├── docker/
   ├── lectures/
   ├── labs/
   ├── requirements.txt
   └── README.md
   ```

   Verification uses cocotb with Verilator as the simulator, so there is no separate
   `sim/` folder — each testbench directory under `tb/` is self-contained with its own
   cocotb Python test(s) and Makefile.

2. `config/` — parameter packages and tool configuration
   - `config/svarog_soc_pkg.sv` — address map, slave indices, `NUM_SLAVES`, interrupt
     assignment, Hazard3 configuration
   - `config/cpu.vlt` — Verilator lint waiver for the Hazard3 submodule

3. `docs/` — project documentation: `SOC.md`, `INTERCONNECT.md`, `MEMORY.md`,
   `INTERRUPTS.md`, `FPGA.md` and the how-to `ADDING_A_SLAVE.md`.
   `NamingConvention.md` and this file live at the project root so they are easy to
   find.

4. `rtl/` — synthesizable SystemVerilog source, one module per file
   - `rtl/cpu/hazard3/` — the Hazard3 core, a **git submodule** pinned to a release
     tag. Never edited.
   - `rtl/cpu/` — `cpu.sv`, the adapter that gives the core project naming;
     `patches/` for unavoidable fixes to the core (none so far); `README.md` with the
     pinned tag and the configuration
   - `rtl/interconnect/` — `ahb_to_apb` (the bridge, the only APB master),
     `apb_decoder` (one-hot `PSEL`) and `apb_mux` (read data / ready / error);
     see `docs/INTERCONNECT.md`
   - `rtl/mem/` — RAM primitive and its APB wrapper (`apb_ram`); see `docs/MEMORY.md`
   - `rtl/periph/` — reference peripherals `uart`, `timer`, `gpio`; see
     `rtl/periph/README.md`
   - `rtl/top/` — SoC top-level integration (`svarog_soc.sv`); see `docs/SOC.md`

5. `tb/` — cocotb testbenches (Verilator as SIM), mirroring the `rtl/` hierarchy
   - `tb/common/` — shared Python and make fragments:
     - `Makefile.include` — Verilator flags and the source lists (`SOC_SOURCES`, ...)
     - `apb_master.py` — APB master driver, used by every slave unit test
     - `apb.py` — APB slave model with protocol checks
     - `ahb_master.py` — AHB-Lite master driver (plays the CPU)
     - `uart_model.py` — 8N1 monitor and sender for the SoC-level tests
     - `socmap.py` — the address map, mirroring `svarog_soc_pkg.sv`
   - `tb/unit/<module>/` — one directory per RTL module: `Makefile` and
     `test_<module>.py`
   - `tb/interconnect/` — bridge + decoder + mux wired as in the SoC
   - `tb/core/` — CPU subsystem: Hazard3 + bridge + RAM, running a C program
   - `tb/soc/` — the whole SoC running a C program, checked at the pins;
     `test_sw.py` runs any image from `sw/`
   - `tb/fpga/` — the board wrapper `fpga/anvil/top.sv`
   - simulation build artifacts (`sim_build/`, `.vcd`/`.fst`, `results.xml`) are
     Verilator/cocotb outputs and are git-ignored

6. `sw/` — bare-metal software: `bsp/` (crt0 with trap entry, drivers, interrupt
   layer), `link.ld`, `rules.mk`, `examples/` and `tests/` (the programs the
   testbenches run). Builds `$readmemh` images for the SoC's `INIT_FILE`; `make run`
   in an example executes it on the SoC testbench. See `sw/README.md`.

7. `fpga/` — FPGA implementation
   - `fpga/anvil/` — Anvil (F4PGA) project sources for the Nexys A7-100T: board
     wrapper `top.sv`, `config.json`, pin constraints. `scripts/anvil_flow.py`
     flattens the design into a scratch project and runs the build.
     See `docs/FPGA.md`.

8. `scripts/` — `anvil_flow.py` (flatten, sv2v, Anvil build/program) and `mkmem.py`
   (binary to `$readmemh` image)

9. `docker/` — the toolchain image (Anvil, F4PGA, sv2v, RISC-V GCC, openFPGALoader,
   Verilator, cocotb)

10. `lectures/` — the lecture system (reaction-time meter), one git tag per lecture

11. `labs/` — lab handouts and templates. `solutions/` holds the lab solutions; it
    is git-ignored and never committed to the public repository.

12. Notes
    - Each RTL module lives in its own file, matching the module name, per the naming
      convention (`NamingConvention.md`, section 10).
    - `rtl/` and `tb/` subfolders mirror each other so a module and its testbench are
      easy to locate side by side.
    - File names must be unique across the whole design: the FPGA flow flattens
      every source into one directory, and `anvil_flow.py` refuses to run if two
      files would collide.
    - Keep tool-generated output (simulation logs, waveforms, synthesis results, build
      artifacts) out of version control via `.gitignore`; only scripts and constraints
      are checked in.
