# cocotb testbench for the reference timer (rtl/periph/timer.sv).
#
# Register map: 0x00 CTRL {bit2 IRQ_EN, bit1 CLEAR (w), bit0 ENABLE},
# 0x04 COUNT_LO, 0x08 COUNT_HI (ro), 0x0C CMP_LO, 0x10 CMP_HI.
# Irq = IRQ_EN & (COUNT >= CMP), registered.

import cocotb
from cocotb.triggers import ClockCycles, FallingEdge

from apb_master import apb_start, apb_read, apb_write

CTRL, COUNT_LO, COUNT_HI, CMP_LO, CMP_HI = 0x00, 0x04, 0x08, 0x0C, 0x10
ENABLE, CLEAR, IRQ_EN = 1, 2, 4


@cocotb.test()
async def test_reset_values(dut):
    """Every register reads its reset value; no interrupt out of reset."""
    await apb_start(dut)
    assert await apb_read(dut, CTRL) == 0
    assert await apb_read(dut, COUNT_LO) == 0
    assert await apb_read(dut, COUNT_HI) == 0
    assert await apb_read(dut, CMP_LO) == 0xFFFFFFFF
    assert await apb_read(dut, CMP_HI) == 0xFFFFFFFF
    assert dut.Irq.value == 0


@cocotb.test()
async def test_register_readback(dut):
    """Writable registers return what was written."""
    await apb_start(dut)
    await apb_write(dut, CMP_LO, 0x12345678)
    await apb_write(dut, CMP_HI, 0x9ABCDEF0)
    assert await apb_read(dut, CMP_LO) == 0x12345678
    assert await apb_read(dut, CMP_HI) == 0x9ABCDEF0
    await apb_write(dut, CTRL, IRQ_EN)
    assert await apb_read(dut, CTRL) == IRQ_EN
    await apb_write(dut, CTRL, 0)
    assert await apb_read(dut, CTRL) == 0


@cocotb.test()
async def test_counts_only_when_enabled(dut):
    """The counter advances one per clock while ENABLE is set."""
    await apb_start(dut)
    await ClockCycles(dut.clk, 5)
    await FallingEdge(dut.clk)
    assert await apb_read(dut, COUNT_LO) == 0, "counted while disabled"

    await apb_write(dut, CTRL, ENABLE)
    first = await apb_read(dut, COUNT_LO)
    await ClockCycles(dut.clk, 20)
    await FallingEdge(dut.clk)
    second = await apb_read(dut, COUNT_LO)
    # a read takes two clocks (setup + access), plus the 20 waited
    assert second - first == 22, f"advanced by {second - first}"

    await apb_write(dut, CTRL, 0)
    held = await apb_read(dut, COUNT_LO)
    await ClockCycles(dut.clk, 10)
    await FallingEdge(dut.clk)
    assert await apb_read(dut, COUNT_LO) == held, "kept counting after stop"


@cocotb.test()
async def test_count_registers_are_read_only(dut):
    await apb_start(dut)
    await apb_write(dut, COUNT_LO, 0x1234)
    await apb_write(dut, COUNT_HI, 0x5678)
    assert await apb_read(dut, COUNT_LO) == 0
    assert await apb_read(dut, COUNT_HI) == 0


@cocotb.test()
async def test_clear(dut):
    """CLEAR zeroes the counter, is self-clearing and keeps ENABLE."""
    await apb_start(dut)
    await apb_write(dut, CTRL, ENABLE)
    await ClockCycles(dut.clk, 30)
    await FallingEdge(dut.clk)
    assert await apb_read(dut, COUNT_LO) > 20
    await apb_write(dut, CTRL, ENABLE | CLEAR)
    assert await apb_read(dut, CTRL) == ENABLE, "CLEAR must read as 0"
    assert await apb_read(dut, COUNT_LO) < 10, "counter was not cleared"


@cocotb.test()
async def test_carry_into_high_word(dut):
    """The counter is 64 bits wide: the low word carries into the high."""
    await apb_start(dut)
    dut.Count.value = 0xFFFFFFF0
    await FallingEdge(dut.clk)
    await apb_write(dut, CTRL, ENABLE)
    await ClockCycles(dut.clk, 40)
    await FallingEdge(dut.clk)
    assert await apb_read(dut, COUNT_HI) == 1
    assert await apb_read(dut, COUNT_LO) < 0x100


@cocotb.test()
async def test_irq_sets_and_clears(dut):
    """Irq rises at the compare value and falls when the compare moves."""
    await apb_start(dut)
    await apb_write(dut, CMP_HI, 0)
    await apb_write(dut, CMP_LO, 50)
    await apb_write(dut, CTRL, ENABLE | IRQ_EN)
    assert dut.Irq.value == 0, "interrupt before the compare value"

    for _ in range(100):
        await FallingEdge(dut.clk)
        if dut.Irq.value == 1:
            break
    else:
        raise AssertionError("Irq never rose")
    count = int(dut.Count.value)
    assert 50 <= count <= 52, f"Irq rose at count {count}"

    # the interrupt is a level: it stays until software acts
    await ClockCycles(dut.clk, 10)
    await FallingEdge(dut.clk)
    assert dut.Irq.value == 1

    # moving the compare ahead of the counter clears it
    await apb_write(dut, CMP_LO, 1000)
    await FallingEdge(dut.clk)
    assert dut.Irq.value == 0, "Irq not cleared by a new compare value"


@cocotb.test()
async def test_irq_enable_gates_the_output(dut):
    """Without IRQ_EN a compare match raises nothing; CLEAR drops Irq."""
    await apb_start(dut)
    await apb_write(dut, CMP_HI, 0)
    await apb_write(dut, CMP_LO, 10)
    await apb_write(dut, CTRL, ENABLE)
    await ClockCycles(dut.clk, 30)
    await FallingEdge(dut.clk)
    assert dut.Irq.value == 0, "Irq without IRQ_EN"

    await apb_write(dut, CTRL, ENABLE | IRQ_EN)
    await FallingEdge(dut.clk)
    assert dut.Irq.value == 1

    await apb_write(dut, CTRL, ENABLE)
    await FallingEdge(dut.clk)
    assert dut.Irq.value == 0, "dropping IRQ_EN must clear Irq"

    await apb_write(dut, CTRL, IRQ_EN | CLEAR)
    await FallingEdge(dut.clk)
    assert dut.Irq.value == 0, "CLEAR must drop Irq (count below compare)"


@cocotb.test()
async def test_synchronous_reset(dut):
    await apb_start(dut)
    await apb_write(dut, CMP_LO, 5)
    await apb_write(dut, CMP_HI, 0)
    await apb_write(dut, CTRL, ENABLE | IRQ_EN)
    await ClockCycles(dut.clk, 20)
    dut.reset.value = 1
    await ClockCycles(dut.clk, 2)
    dut.reset.value = 0
    await FallingEdge(dut.clk)
    assert dut.Irq.value == 0
    assert await apb_read(dut, CTRL) == 0
    assert await apb_read(dut, COUNT_LO) == 0
    assert await apb_read(dut, CMP_LO) == 0xFFFFFFFF
