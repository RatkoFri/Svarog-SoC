# cocotb testbench for the APB RAM wrapper (rtl/mem/apb_ram.sv).
#
# 256 words, initialised from mem_init.hex through INIT_FILE.

import random

import cocotb
from cocotb.triggers import ClockCycles, FallingEdge

from apb_master import apb_start, apb_read, apb_write
from gen_init import pattern, WORDS


@cocotb.test()
async def test_init_image(dut):
    """The $readmemh image is readable straight after elaboration."""
    await apb_start(dut)
    for i in (0, 1, 2, 100, WORDS - 1):
        got = await apb_read(dut, 4 * i)
        assert got == pattern(i) & 0xFFFFFFFF, f"word {i}: {got:#010x}"


@cocotb.test()
async def test_word_write_read(dut):
    """A word written is the word read back; neighbours are untouched."""
    await apb_start(dut)
    await apb_write(dut, 0x40, 0xDEADBEEF)
    assert await apb_read(dut, 0x40) == 0xDEADBEEF
    assert await apb_read(dut, 0x3C) == pattern(0x3C // 4) & 0xFFFFFFFF
    assert await apb_read(dut, 0x44) == pattern(0x44 // 4) & 0xFFFFFFFF


@cocotb.test()
async def test_byte_strobes(dut):
    """Each strobe bit writes exactly its byte lane (sb)."""
    await apb_start(dut)
    await apb_write(dut, 0x80, 0x00000000)
    expected = 0
    for lane, byte in enumerate((0x11, 0x22, 0x33, 0x44)):
        await apb_write(dut, 0x80, byte << (8 * lane), strb=1 << lane)
        expected |= byte << (8 * lane)
        assert await apb_read(dut, 0x80) == expected


@cocotb.test()
async def test_halfword_strobes(dut):
    """Two-lane strobes write one half and keep the other (sh)."""
    await apb_start(dut)
    await apb_write(dut, 0x84, 0xAAAAAAAA)
    await apb_write(dut, 0x84, 0x0000BEEF, strb=0b0011)
    assert await apb_read(dut, 0x84) == 0xAAAABEEF
    await apb_write(dut, 0x84, 0xCAFE0000, strb=0b1100)
    assert await apb_read(dut, 0x84) == 0xCAFEBEEF


@cocotb.test()
async def test_no_strobe_no_write(dut):
    """A write with all strobes low leaves the word unchanged."""
    await apb_start(dut)
    await apb_write(dut, 0x88, 0x12345678)
    await apb_write(dut, 0x88, 0xFFFFFFFF, strb=0)
    assert await apb_read(dut, 0x88) == 0x12345678


@cocotb.test()
async def test_write_only_in_access_phase(dut):
    """The setup phase alone must not write the memory."""
    await apb_start(dut)
    await apb_write(dut, 0x8C, 0x0BADF00D)
    dut.ApbSel.value = 1
    dut.ApbEnable.value = 0
    dut.ApbWrite.value = 1
    dut.ApbAddr.value = 0x8C
    dut.ApbWdata.value = 0xFFFFFFFF
    dut.ApbStrb.value = 0xF
    await ClockCycles(dut.clk, 2)
    await FallingEdge(dut.clk)
    dut.ApbSel.value = 0
    dut.ApbWrite.value = 0
    assert await apb_read(dut, 0x8C) == 0x0BADF00D


@cocotb.test()
async def test_zero_wait_states(dut):
    """The RAM is always ready and never reports an error."""
    await apb_start(dut)
    assert dut.ApbReady.value == 1
    assert dut.ApbSlvErr.value == 0


@cocotb.test()
async def test_random_against_model(dut):
    """Random byte/half/word writes and reads against a Python model."""
    await apb_start(dut)
    rng = random.Random(1)
    # the RAM has no reset and earlier tests wrote to it (cocotb runs
    # every test in one simulation), so the model starts from a read-out
    model = {i: await apb_read(dut, 4 * i) for i in range(WORDS)}
    for _ in range(300):
        word = rng.randrange(WORDS)
        if rng.random() < 0.5:
            strb = rng.choice((0x1, 0x2, 0x4, 0x8, 0x3, 0xC, 0xF))
            data = rng.getrandbits(32)
            mask = sum(0xFF << (8 * i) for i in range(4) if (strb >> i) & 1)
            model[word] = (model[word] & ~mask) | (data & mask)
            await apb_write(dut, 4 * word, data, strb=strb)
        else:
            got = await apb_read(dut, 4 * word)
            assert got == model[word], \
                f"word {word}: read {got:#010x}, model {model[word]:#010x}"
