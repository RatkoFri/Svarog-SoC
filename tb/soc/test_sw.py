# Run an arbitrary program image on the SoC and capture its UART output.
#
# Used by `make run` in sw/: the image comes from INIT_FILE, so this
# testbench does not care what the program does — it boots the SoC,
# decodes whatever the program prints, and logs it.
#
# Environment:
#   UART_DIV    clock cycles per bit (must match what the program sets)
#   RUN_CYCLES  how long to run at most
#   EXPECT_FILE golden file: the output must start with its contents.
#               The run stops as soon as that much has been printed, so
#               programs that never return can be checked too.
#   EXPECT      same, as a literal string (\n for a newline)
# With neither set the test only reports the output and checks that the
# program printed something.

import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles

from uart_model import uart_monitor, text

UART_DIV = int(os.environ.get("UART_DIV", "16"))
RUN_CYCLES = int(os.environ.get("RUN_CYCLES") or "300000")

# unset or empty means "just report what the program printed"
EXPECT_FILE = os.environ.get("EXPECT_FILE") or None
EXPECT = os.environ.get("EXPECT") or None
if EXPECT_FILE:
    with open(EXPECT_FILE) as f:
        EXPECT = f.read()
elif EXPECT is not None:
    EXPECT = EXPECT.replace("\\n", "\n")


@cocotb.test()
async def run_program(dut):
    """Boot the image in INIT_FILE and report what it prints."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.Rx.value = 1
    dut.GpioIn.value = 0
    dut.reset.value = 1
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.reset.value = 0

    out = []
    cocotb.start_soon(uart_monitor(dut.clk, dut.Tx, UART_DIV, out))
    step = 1000
    for _ in range(0, RUN_CYCLES, step):
        await ClockCycles(dut.clk, step)
        if EXPECT is not None and len(out) >= len(EXPECT):
            break

    got = text(out)
    dut._log.info("UART output (%d bytes):\n%s", len(out), got)

    if EXPECT is not None:
        assert got[:len(EXPECT)] == EXPECT, \
            f"UART output {got!r} does not match expected {EXPECT!r}"
    else:
        assert out, "the program produced no UART output"
