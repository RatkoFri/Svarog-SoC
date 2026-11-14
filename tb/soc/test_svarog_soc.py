# SoC-level cocotb testbench: the whole svarog_soc running a real C
# program (sw/tests/soctest), loaded at elaboration through INIT_FILE —
# the same path the FPGA flow uses. The program exercises every slave
# and both interrupt paths and reports over the UART, so the checks
# happen at the SoC pins.

import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles, Timer

from uart_model import uart_monitor, uart_send, text

UART_DIV = int(os.environ.get("UART_DIV", "16"))
SWITCHES = 0x1234

# what sw/tests/soctest prints before it starts echoing; see the list
# in its main.c for the path each line proves
BOOT = ("Svarog\n"
        "data=7 bss=0\n"
        "bytes=44332211\n"
        "gpio=a5a5\n"
        f"in={SWITCHES:04x}\n"
        "ticks=3\n"
        "fault=00000005\n"
        "ready\n")


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.Rx.value = 1              # UART line idles high
    dut.GpioIn.value = SWITCHES
    dut.reset.value = 1
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.reset.value = 0
    out = []
    cocotb.start_soon(uart_monitor(dut.clk, dut.Tx, UART_DIV, out))
    return out


async def wait_text(dut, out, expected, timeout):
    for _ in range(0, timeout, 500):
        await ClockCycles(dut.clk, 500)
        if len(out) >= len(expected):
            break
    assert text(out) == expected, \
        f"UART output {text(out)!r}, expected {expected!r}"


@cocotb.test()
async def test_program_reports_over_uart(dut):
    """The program boots, uses every slave and reports the right lines."""
    out = await start(dut)
    await wait_text(dut, out, BOOT, 200000)


@cocotb.test()
async def test_uart_receive_interrupt(dut):
    """Characters sent to Rx come back through the receive interrupt."""
    out = await start(dut)
    await wait_text(dut, out, BOOT, 200000)
    for ch in "abq":
        await uart_send(dut.clk, dut.Rx, UART_DIV, ch)
        await ClockCycles(dut.clk, 30 * UART_DIV)     # let the echo go out
    await wait_text(dut, out, BOOT + "bcr" + "\ndone\n", 20000)
    assert int(dut.GpioOut.value) == 0xFFFF, "final GPIO pattern missing"


@cocotb.test()
async def test_gpio_pins(dut):
    """The program drives the GPIO output pins."""
    await start(dut)
    for _ in range(100000):
        await RisingEdge(dut.clk)
        if int(dut.GpioOut.value) == 0xA5A5:
            return
    raise AssertionError(f"GpioOut is {int(dut.GpioOut.value):#06x}")


@cocotb.test()
async def test_timer_interrupt_line(dut):
    """The timer raises its interrupt three times and software clears it."""
    await start(dut)
    rises = 0
    previous = 0
    for _ in range(200000):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        now = int(dut.TimerIrq.value)
        rises += (now == 1 and previous == 0)
        previous = now
        if rises == 3 and now == 0:
            break
    assert rises == 3, f"TimerIrq rose {rises} times, expected 3"
    assert previous == 0, "TimerIrq left asserted"


@cocotb.test()
async def test_reset_is_synchronous(dut):
    """Reset with the clock running restarts the program from address 0."""
    out = await start(dut)
    await wait_text(dut, out, BOOT, 200000)
    assert int(dut.GpioOut.value) == 0xA5A5, "program did not run"

    dut.reset.value = 1
    await ClockCycles(dut.clk, 4)
    dut.reset.value = 0
    await Timer(1, unit="ns")
    assert int(dut.GpioOut.value) == 0, "GPIO not cleared by reset"

    # and the program prints everything again from the start
    del out[:]
    await wait_text(dut, out, BOOT, 200000)
