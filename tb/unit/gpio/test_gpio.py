# cocotb testbench for the reference GPIO (rtl/periph/gpio.sv).
#
# Register map: 0x00 OUT (RW), 0x04 IN (RO, 2-FF synchronised).

import cocotb
from cocotb.triggers import ClockCycles, FallingEdge

from apb_master import apb_start, apb_read, apb_write

OUT, IN = 0x00, 0x04


async def start(dut):
    dut.GpioIn.value = 0
    await apb_start(dut)


@cocotb.test()
async def test_reset_values(dut):
    """Every register reads its reset value."""
    await start(dut)
    assert int(dut.GpioOut.value) == 0, "outputs not zero after reset"
    assert await apb_read(dut, OUT) == 0
    assert await apb_read(dut, IN) == 0


@cocotb.test()
async def test_output_register(dut):
    """A write to OUT drives the pins and reads back."""
    await start(dut)
    for value in (0xA5A5, 0x0001, 0x8000, 0xFFFF, 0x0000):
        await apb_write(dut, OUT, value)
        assert int(dut.GpioOut.value) == value, f"pins={int(dut.GpioOut.value):#x}"
        assert await apb_read(dut, OUT) == value


@cocotb.test()
async def test_write_only_in_access_phase(dut):
    """The setup phase alone must not write the register."""
    await start(dut)
    dut.ApbSel.value = 1
    dut.ApbEnable.value = 0
    dut.ApbWrite.value = 1
    dut.ApbAddr.value = OUT
    dut.ApbWdata.value = 0x1234
    await ClockCycles(dut.clk, 2)
    await FallingEdge(dut.clk)
    assert int(dut.GpioOut.value) == 0, "register written without ApbEnable"
    dut.ApbSel.value = 0
    dut.ApbWrite.value = 0


@cocotb.test()
async def test_input_register(dut):
    """IN reflects the pins after the two synchroniser flops."""
    await start(dut)
    for value in (0x3C3C, 0x8001, 0x0000):
        dut.GpioIn.value = value
        await ClockCycles(dut.clk, 2)
        await FallingEdge(dut.clk)
        assert await apb_read(dut, IN) == value


@cocotb.test()
async def test_in_is_read_only(dut):
    """A write to IN changes nothing."""
    await start(dut)
    dut.GpioIn.value = 0x00F0
    await ClockCycles(dut.clk, 3)
    await FallingEdge(dut.clk)
    await apb_write(dut, IN, 0xFFFF)
    assert await apb_read(dut, IN) == 0x00F0
    assert int(dut.GpioOut.value) == 0


@cocotb.test()
async def test_unmapped_offset(dut):
    """Offsets with no register read zero, ignore writes, raise no error."""
    await start(dut)
    await apb_write(dut, OUT, 0x00FF)
    await apb_write(dut, 0x08, 0xDEAD)
    assert await apb_read(dut, 0x08) == 0
    assert await apb_read(dut, OUT) == 0x00FF


@cocotb.test()
async def test_synchronous_reset(dut):
    """Reset clears the output register on a clock edge."""
    await start(dut)
    await apb_write(dut, OUT, 0xBEEF)
    dut.reset.value = 1
    await ClockCycles(dut.clk, 2)
    dut.reset.value = 0
    await FallingEdge(dut.clk)
    assert int(dut.GpioOut.value) == 0
