# CPU subsystem testbench: Hazard3 (through rtl/cpu/cpu.sv), the
# AHB-to-APB bridge and the APB RAM, running a real C program
# (sw/tests/coretest). There are no peripherals here, so the program
# leaves its results in a block of RAM and the testbench reads the
# memory array directly; the testbench also plays the interrupt sources.
#
# The whole run is one test: the program boots once.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles

RESULT_WORD = 0xF000 // 4       # RESULT[] in sw/tests/coretest/main.c
DONE = 0x600D600D

EXPECTED = {
    1: (5050, "sum 1..100"),
    2: (123 * 456, "libgcc multiply"),
    3: (1000000 // 7, "libgcc divide"),
    4: (0x44332211, "byte stores"),
    5: (0xBEEFCAFE, "halfword stores"),
    6: ((0xFFFFFFFE + 0xFE) & 0xFFFFFFFF, "lb / lbu extension"),
    7: (2, "timer interrupts"),
    8: (2, "external interrupts"),
    9: (11, "mcause of ecall from M-mode"),
    10: (0xCAFE0001, ".data value"),
    11: (0, ".bss value"),
}


def result(dut, index):
    return int(dut.ram.ram.mem[RESULT_WORD + index].value)


async def wait_result(dut, index, value, timeout, what):
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if result(dut, index) == value:
            return
    raise AssertionError(
        f"timeout waiting for {what}: RESULT[{index}] = {result(dut, index):#x}")


async def pulse_irq(dut, signal, index, count, name):
    """Raise a level interrupt and drop it once the handler has run."""
    await ClockCycles(dut.clk, 20)
    signal.value = 1
    await wait_result(dut, index, count, 2000, f"{name} interrupt {count}")
    signal.value = 0


@cocotb.test()
async def test_program(dut):
    """The C program runs to completion and every result is right."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.Irq.value = 0
    dut.TimerIrq.value = 0
    dut.reset.value = 1
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.reset.value = 0

    # the program computes, takes an ecall, then enables interrupts
    await wait_result(dut, 0, 1, 60000, "the program to reach its interrupt phase")
    assert result(dut, 7) == 0 and result(dut, 8) == 0, \
        "an interrupt was taken with both lines low"

    # interrupts are levels: each line stays high until its handler ran
    await pulse_irq(dut, dut.TimerIrq, 7, 1, "timer")
    await pulse_irq(dut, dut.Irq, 8, 1, "external")
    await pulse_irq(dut, dut.Irq, 8, 2, "external")
    await pulse_irq(dut, dut.TimerIrq, 7, 2, "timer")

    await wait_result(dut, 0, DONE, 5000, "the program to finish")

    for index, (value, what) in EXPECTED.items():
        got = result(dut, index)
        assert got == value, f"{what}: RESULT[{index}] = {got:#x}, expected {value:#x}"


@cocotb.test()
async def test_reset_restarts(dut):
    """A synchronous reset restarts the program from the reset vector."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.Irq.value = 0
    dut.TimerIrq.value = 0
    assert result(dut, 0) == DONE, "run test_program first"
    dut.reset.value = 1
    await ClockCycles(dut.clk, 4)
    dut.reset.value = 0
    # the program clears its result block first, then reaches phase 1
    await wait_result(dut, 0, 1, 60000, "the program to restart")
    assert result(dut, 1) == 5050
