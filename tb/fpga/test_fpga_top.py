# cocotb testbench for the Nexys A7 FPGA wrapper (fpga/anvil/top.sv).
#
# The SoC itself is verified in tb/soc; this checks only the board
# plumbing, which is exactly where bring-up bugs hide:
#   - the active-low CPU_RESETN button becomes an active-high SoC reset
#   - the power-on reset releases on its own
#   - GPIO reaches the LEDs, the switches reach GPIO in
#   - the UART reaches the right pins, in both directions
#
# `clk` drives the SoC directly (no divider), so a UART bit lasts
# UART_DIV clk cycles. The testbench clocks it at 20 ns = 50 MHz, the
# frequency the XDC constrains.

import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles, Timer

from uart_model import uart_monitor, uart_send, text

UART_DIV = int(os.environ.get("UART_DIV", "16"))
SWITCHES = 0x5AC3

# what sw/tests/soctest prints before it starts echoing
BOOT = ("Svarog\n"
        "data=7 bss=0\n"
        "bytes=44332211\n"
        "gpio=a5a5\n"
        f"in={SWITCHES:04x}\n"
        "ticks=3\n"
        "fault=00000005\n"
        "ready\n")


# cocotb runs every test in one simulation, and cancels the coroutines a
# test started when that test ends — so every test must start its own
# clock. What does *not* restart by itself is the SoC: the program runs
# once at boot, so a test that wants to watch it from the beginning has
# to press the reset button first.


async def start(dut, hold_reset=True, restart=True):
    """Clock running; optionally restart the SoC via the reset button.

    hold_reset: leave the button pressed on return.
    restart:    pulse the button first, so the program runs again from
                the beginning (needed by any test that observes boot).
    """
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())   # 50 MHz

    dut.uart_rx.value = 1
    dut.sw.value = SWITCHES

    if restart:
        dut.cpu_resetn.value = 0            # press reset
        await ClockCycles(dut.clk, 8)

    dut.cpu_resetn.value = 0 if hold_reset else 1
    await ClockCycles(dut.clk, 4)


async def wait_text(dut, out, expected, timeout):
    for _ in range(0, timeout, 500):
        await ClockCycles(dut.clk, 500)
        if len(out) >= len(expected):
            break
    assert text(out) == expected, \
        f"uart_tx sent {text(out)!r}, expected {expected!r}"


@cocotb.test()
async def test_power_on_reset(dut):
    """With the button never pressed, the POR still resets the SoC.

    This test must run FIRST: cocotb runs every test in one simulation,
    and power-on state exists only once — by the second test the POR
    counter has long since saturated. Keep it at the top of the file.
    """
    await start(dut, hold_reset=False, restart=False)   # pristine power-up
    await Timer(1, unit="ns")
    assert int(dut.SocReset.value) == 1, "no power-on reset asserted"
    await ClockCycles(dut.clk, 80)
    assert int(dut.SocReset.value) == 0, "power-on reset never released"


@cocotb.test()
async def test_reset_polarity(dut):
    """Holding the button (low) asserts the SoC's active-high reset."""
    await start(dut, hold_reset=True, restart=False)
    await ClockCycles(dut.clk, 20)
    assert int(dut.SocReset.value) == 1, \
        "cpu_resetn low must produce SoC reset high"
    assert int(dut.led.value) == 0, "LEDs must be off while in reset"

    dut.cpu_resetn.value = 1                 # release the button
    await ClockCycles(dut.clk, 60)
    assert int(dut.SocReset.value) == 0, \
        "releasing the button must deassert the SoC reset"


@cocotb.test()
async def test_gpio_to_leds(dut):
    """The program's GPIO writes appear on the LED pins."""
    await start(dut, hold_reset=False)
    for _ in range(100000):
        await RisingEdge(dut.clk)
        if int(dut.led.value) == 0xA5A5:
            return
    raise AssertionError(f"led is {int(dut.led.value):#06x}, expected 0xa5a5")


@cocotb.test()
async def test_uart_and_switches(dut):
    """UART output on uart_tx, including the switch value the program read."""
    await start(dut, hold_reset=False)
    out = []
    cocotb.start_soon(uart_monitor(dut.clk, dut.uart_tx, UART_DIV, out))
    await wait_text(dut, out, BOOT, 200000)


@cocotb.test()
async def test_uart_rx_pin(dut):
    """Characters sent to uart_rx are echoed back, then all LEDs light."""
    await start(dut, hold_reset=False)
    out = []
    cocotb.start_soon(uart_monitor(dut.clk, dut.uart_tx, UART_DIV, out))
    await wait_text(dut, out, BOOT, 200000)
    for ch in "xq":
        await uart_send(dut.clk, dut.uart_rx, UART_DIV, ch)
        await ClockCycles(dut.clk, 30 * UART_DIV)
    await wait_text(dut, out, BOOT + "yr" + "\ndone\n", 20000)
    assert int(dut.led.value) == 0xFFFF
