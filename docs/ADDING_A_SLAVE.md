# How to add a new slave to the Svarog SoC

Step-by-step instructions for attaching a new memory-mapped peripheral to the APB
bus. The running example adds a PWM peripheral at `0x2000_3000`. The bridge and the
return mux are never touched — they scale with `NUM_SLAVES` automatically.

The procedure has been validated end to end: every step below was executed on a
scratch copy of the repository, and the decoder, mux, interconnect, SoC and board
wrapper testbenches pass with the fifth slave in place.

Read `INTERCONNECT.md` first for the APB signals and the timing of a transfer.

## Checklist

| # | File | Change |
|---|------|--------|
| 1 | `config/svarog_soc_pkg.sv` | slave index, `NUM_SLAVES`, base/size |
| 2 | `rtl/interconnect/apb_decoder.sv` | one `Match` line |
| 3 | `rtl/periph/<name>.sv` | the slave itself (template below) |
| 4 | `rtl/top/svarog_soc.sv` | instantiate it; pins and `Irq` if it has any |
| 5 | `tb/common/socmap.py`, `tb/common/Makefile.include` | mirror the map, list the source |
| 6 | `tb/unit/<name>/` | unit testbench |
| 7 | `sw/bsp/svarog.h` | base address and registers for C |
| 8 | `scripts/anvil_flow.py`, `fpga/anvil/top.sv`, XDC | FPGA build: source list, pins |
| 9 | rerun the testbenches; update the docs | |

## 1. Address map (`config/svarog_soc_pkg.sv`)

Add an index, bump `NUM_SLAVES`, and define the region:

```systemverilog
  localparam int unsigned NUM_SLAVES  = 5;          // was 4
  ...
  localparam int unsigned SLAVE_PWM   = 4;

  localparam logic [31:0] PWM_BASE   = 32'h2000_3000;
  localparam logic [31:0] PWM_SIZE   = 32'h0000_1000;  // 4 KiB
```

Rules the decoder depends on:

- **Power-of-two size, naturally aligned** (`BASE % SIZE == 0`). The decoder matches
  `(Addr & ~(SIZE-1)) == BASE` — one comparator — and this only works for aligned
  power-of-two regions.
- **No overlap** with any existing region. The decoder test's one-hot check
  (`test_onehot`) will catch an overlap, but check the table in `INTERCONNECT.md`
  first anyway.
- Peripherals go at `0x2000_0000 + n * 0x1000`, 4 KiB each; take the next free `n`.
- Slave indices are consecutive from 0 and `NUM_SLAVES` is their count.

## 2. Decoder (`rtl/interconnect/apb_decoder.sv`)

Add one line to the match block:

```systemverilog
    Match[SLAVE_PWM]   = in_region(ApbAddr, PWM_BASE, PWM_SIZE);
```

That is all: `SlaveSel` is `[NUM_SLAVES-1:0]` from the package, and so are the
flattened slave vectors in `apb_mux` and `svarog_soc`, so everything resizes by
itself.

## 3. The slave module (`rtl/periph/`)

The file name must be unique in the whole design (the FPGA flow flattens all
sources into one directory) and equal to the module name.

Template for a register slave: zero wait states, no error reporting, whole-word
registers.

```systemverilog
///////////////////////////////////////////////////////////////////////
// pwm
//
// Purpose: <one line>. APB slave, zero wait states, no error
//          reporting. Registers are whole words.
//          Register map (byte offsets):
//            0x00 CTRL    RW  reset 0   bit0 ENABLE
//            0x04 PERIOD  RW  reset 0
//            0x08 DUTY    RW  reset 0
//          Unmapped offsets read as zero and ignore writes.
// Author:  <you>
// Date:    <date>
///////////////////////////////////////////////////////////////////////

module pwm (
  input  logic        clk, reset,
  // APB slave port
  input  logic        ApbSel, ApbEnable, ApbWrite,
  // only the register offset is used
  /* verilator lint_off UNUSEDSIGNAL */
  input  logic [31:0] ApbAddr,
  /* verilator lint_on UNUSEDSIGNAL */
  input  logic [31:0] ApbWdata,
  output logic [31:0] ApbRdata,
  output logic        ApbReady, ApbSlvErr,
  // function side
  output logic        PwmOut);

  localparam logic [9:0] CTRL_OFFSET   = 10'd0;   // 0x00
  localparam logic [9:0] PERIOD_OFFSET = 10'd1;   // 0x04
  localparam logic [9:0] DUTY_OFFSET   = 10'd2;   // 0x08

  logic [31:0] Ctrl, Period, Duty;
  logic        WriteEn;

  // registers are written in the access phase
  assign WriteEn = ApbSel & ApbEnable & ApbWrite;

  always_ff @(posedge clk)
    if (reset) begin
      Ctrl   <= 32'b0;
      Period <= 32'b0;
      Duty   <= 32'b0;
    end else if (WriteEn)
      case (ApbAddr[11:2])
        CTRL_OFFSET:   Ctrl   <= ApbWdata;
        PERIOD_OFFSET: Period <= ApbWdata;
        DUTY_OFFSET:   Duty   <= ApbWdata;
        default: ;
      endcase

  // read mux: combinational, so the data is valid in the access phase
  always_comb
    case (ApbAddr[11:2])
      CTRL_OFFSET:   ApbRdata = Ctrl;
      PERIOD_OFFSET: ApbRdata = Period;
      DUTY_OFFSET:   ApbRdata = Duty;
      default:       ApbRdata = 32'b0;
    endcase

  assign ApbReady  = 1'b1;    // zero wait states
  assign ApbSlvErr = 1'b0;    // no error reporting

  // ... the actual PWM counter/comparator goes here ...
  assign PwmOut = 1'b0;

endmodule
```

Notes:

- **Write only in the access phase** (`ApbSel & ApbEnable & ApbWrite`). In the setup
  phase `ApbEnable` is low; a slave that writes on `ApbSel & ApbWrite` alone still
  works with this bridge but breaks the protocol, and `tb/common/apb_master.py`
  will show it in your unit test (see step 6).
- **`ApbSel` is yours alone.** `ApbEnable`, `ApbWrite`, `ApbAddr` and `ApbWdata` are
  shared by all slaves and change during other slaves' transfers — every write
  enable and every read side effect must include `ApbSel`.
- **Read side effects** (a read that clears a flag or pops a byte) must happen once,
  in the access phase: `ApbSel & ApbEnable & ~ApbWrite`. With `ApbReady` tied high
  the access phase lasts exactly one clock.
- **`ApbAddr[11:2]` is the register number**: the low two bits are always zero and
  the bits above 11 only chose your slave.
- **Slow slaves** hold `ApbReady` low for as many access cycles as they need; the
  bridge and the CPU wait. Then every write enable and side effect must also include
  `ApbReady`, so it happens once, at the end.
- **Errors**: drive `ApbSlvErr` high together with `ApbReady` to make the CPU take
  an access-fault exception — e.g. for an offset with no register.
- Peripherals do not get `ApbStrb`: registers are written as whole words.
- Pins that come from outside the FPGA are asynchronous to `clk`: pass them through
  a 2-FF synchroniser and mark it with a `CDC` comment, as `gpio.sv` does.

## 4. SoC top (`rtl/top/svarog_soc.sv`)

Instantiate the slave and connect it to the bus at its index; add its pins to the
port list of `svarog_soc`:

```systemverilog
   // PWM pin
   output logic                  PwmOut);
  ...
  pwm pwm(.clk(clk), .reset(reset),
          .ApbSel(SlaveSel[SLAVE_PWM]), .ApbEnable(ApbEnable),
          .ApbWrite(ApbWrite), .ApbAddr(ApbAddr), .ApbWdata(ApbWdata),
          .ApbRdata(SlaveRdata[SLAVE_PWM*32 +: 32]),
          .ApbReady(SlaveReady[SLAVE_PWM]), .ApbSlvErr(SlaveSlvErr[SLAVE_PWM]),
          .PwmOut(PwmOut));
```

Three connections are per-slave (`SlaveSel`, `SlaveRdata`, `SlaveReady` /
`SlaveSlvErr` at your index); the rest are the shared bus signals. Forgetting
`SlaveReady` leaves it undriven and the first access to your slave hangs the CPU.

**If the slave interrupts**, give it a level `Irq` output that follows the rules in
`INTERRUPTS.md`, add a line to the package and connect it:

```systemverilog
  localparam int unsigned NUM_IRQS = 2;             // was 1
  localparam int unsigned IRQ_PWM  = 1;
```

```systemverilog
          .PwmOut(PwmOut), .Irq(Irq[IRQ_PWM]));
```

and mirror `IRQ_PWM` / `NUM_IRQS` in `tb/common/socmap.py` and `sw/bsp/svarog.h`.

## 5. Testbench map and source list (`tb/common/`)

Mirror the package in `socmap.py` — the decoder and interconnect testbenches derive
everything from these dicts:

```python
SLAVE = { "RAM": 0, "UART": 1, "TIMER": 2, "GPIO": 3, "PWM": 4 }
REGIONS = { ...,
    "PWM": (0x2000_3000, 0x0000_1000),
}
```

`HOLES` in the same file lists addresses that must decode to nothing. It contains
`0x2000_3000` ("just past the last peripheral") — that address is now mapped, so
**move the hole** to `0x2000_4000`.

Add the source to `PERIPH_SOURCES` in `Makefile.include`, so the SoC-level
testbenches compile it:

```make
                  $(RTL_DIR)/periph/gpio.sv \
                  $(RTL_DIR)/periph/pwm.sv
```

## 6. Unit testbench (`tb/unit/pwm/`)

Every slave gets one. `Makefile`:

```make
TOPLEVEL_DIR := $(abspath ../../..)

TOPLEVEL = pwm
MODULE   = test_pwm
VERILOG_SOURCES = $(TOPLEVEL_DIR)/rtl/periph/pwm.sv

include $(TOPLEVEL_DIR)/tb/common/Makefile.include
```

`test_pwm.py`, using the shared APB driver:

```python
import cocotb

from apb_master import apb_start, apb_read, apb_write

CTRL, PERIOD, DUTY = 0x00, 0x04, 0x08


@cocotb.test()
async def test_reset_values(dut):
    await apb_start(dut)                 # clock, idle bus, reset
    for reg in (CTRL, PERIOD, DUTY):
        assert await apb_read(dut, reg) == 0


@cocotb.test()
async def test_register_readback(dut):
    await apb_start(dut)
    await apb_write(dut, PERIOD, 1000)
    await apb_write(dut, DUTY, 250)
    assert await apb_read(dut, PERIOD) == 1000
    assert await apb_read(dut, DUTY) == 250
```

`apb_write` / `apb_read` drive a proper SETUP + ACCESS transfer, wait for
`ApbReady` and fail the test on `ApbSlvErr`. The minimum to check: every register
reads its reset value, a write followed by a read returns the new value, read-only
registers stay read-only, the function pins do what the registers say, and `Irq`
(if any) sets and clears as the register map promises. `tb/unit/gpio`,
`tb/unit/timer` and `tb/unit/uart` are worked examples.

Run it with `make` in `tb/unit/pwm` (`WAVES=1` for a waveform).

## 7. Software (`sw/bsp/svarog.h`)

```c
#define PWM_BASE    0x20003000u

#define PWM_CTRL    REG32(PWM_BASE + 0x00)
#define PWM_PERIOD  REG32(PWM_BASE + 0x04)
#define PWM_DUTY    REG32(PWM_BASE + 0x08)

#define PWM_CTRL_ENABLE  (1u << 0)
```

A driver is then a few lines of C in your program, or in `bsp.c` / `bsp.h` if every
program should have it. Test it on the simulated SoC with `make run` in an example
directory before going to the board.

## 8. FPGA build

- Add the file to the `RTL` list in `scripts/anvil_flow.py`:

  ```python
      "rtl/periph/gpio.sv",
      "rtl/periph/pwm.sv",
  ```

- If the slave has pins: add a port to `fpga/anvil/top.sv`, connect it to the new
  `svarog_soc` port, and add the pin to `fpga/anvil/Nexys-A7-100T-Master.xdc`
  (pin names are in the Digilent master XDC shipped with Anvil):

  ```systemverilog
            output logic        pwm_out);
    ...
        .GpioIn(sw), .GpioOut(led),
        .PwmOut(pwm_out));
  ```

  ```tcl
  set_property PACKAGE_PIN C17 [get_ports {pwm_out}]
  set_property IOSTANDARD LVCMOS33 [get_ports {pwm_out}]
  ```

`top.sv` uses no packages, so nothing else changes there.

## 9. Rerun the testbenches, update the docs

```sh
make test          # everything, from the top level
```

or one at a time: `tb/unit/apb_decoder`, `tb/unit/apb_mux`, `tb/interconnect`
(their tests iterate over `SLAVE` / `REGIONS`, so the new slave is covered without
editing them), your `tb/unit/pwm`, then `tb/soc` and `tb/fpga`.

Add the region to the address-map tables in `INTERCONNECT.md` and `SOC.md`, and the
register map to the module's banner comment (and `rtl/periph/README.md` for a
peripheral that stays in the SoC).

## Common mistakes

| Symptom | Cause |
|---------|-------|
| First access to the new slave hangs the CPU | `SlaveReady[SLAVE_X]` not connected, or the slave never raises `ApbReady` |
| Program stops with `TRAP mcause=00000005` or `00000007` | The address is not in any region: wrong base in `svarog.h`, or the decoder line is missing |
| `test_width_follows_the_map` fails | `socmap.py` and the package disagree on the number of slaves |
| `test_onehot` fails after the edit | New region overlaps an existing one (check size and alignment) |
| `test_unmapped` fails | The new region absorbed an address that `HOLES` lists — move the hole |
| Register changes during another slave's transfer | A write enable without `ApbSel` |
| A read-to-clear flag clears too early, or a FIFO pops twice | Side effect not qualified with `ApbEnable` (and `ApbReady` in a slow slave) |
| Reads return the wrong byte lanes in C | The register was accessed with a `char` or `short` pointer; use `REG32` |
| Interrupt handler never returns to `main` | The handler does not clear the cause, so the level `Irq` stays high |
| `anvil_flow.py`: filename collision | Two source files with the same name; rename the new one |
| Simulation works, FPGA build cannot find the module | File not added to `RTL` in `scripts/anvil_flow.py` |
