# cocotb testbench for the AHB-Lite to APB bridge.
#
# ahb_master.py plays the CPU, apb.py plays the APB slaves and checks
# the SETUP/ACCESS protocol on every transfer.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, ClockCycles, Timer
from cocotb.utils import get_sim_time

from ahb_master import ahb_idle, ahb_run, ahb_read, ahb_write
from apb import apb_slave

BYTE, HALF, WORD = 0, 1, 2


async def start(dut, mem, wait_states=0, err_addrs=()):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    ahb_idle(dut)
    log = []
    cocotb.start_soon(apb_slave(
        dut.clk, dut.ApbSel, dut.ApbEnable, dut.ApbWrite, dut.ApbAddr,
        dut.ApbWdata, dut.ApbRdata, dut.ApbReady, dut.ApbSlvErr, mem,
        strb=dut.ApbStrb, wait_states=wait_states, err_addrs=err_addrs,
        log=log))
    dut.reset.value = 1
    for _ in range(2):
        await RisingEdge(dut.clk)
    dut.reset.value = 0
    await FallingEdge(dut.clk)
    return log


@cocotb.test()
async def test_idle(dut):
    """With no AHB transfer the APB bus stays idle and AHB is ready."""
    await start(dut, {})
    for _ in range(5):
        await Timer(3, unit="ns")
        assert dut.ApbSel.value == 0 and dut.ApbEnable.value == 0
        assert dut.AhbReady.value == 1 and dut.AhbResp.value == 0
        await FallingEdge(dut.clk)


@cocotb.test()
async def test_read(dut):
    """A read returns the slave's data in two APB cycles."""
    log = await start(dut, {0x100: 0xCAFEF00D})
    data, resp = await ahb_read(dut, 0x100)
    assert (data, resp) == (0xCAFEF00D, 0)
    assert log == [(0x100, False, 0xCAFEF00D, 0x0, 1)], log


@cocotb.test()
async def test_write(dut):
    """A word write reaches the slave with all strobes set."""
    mem = {}
    log = await start(dut, mem)
    assert await ahb_write(dut, 0x200, 0x12345678) == 0
    assert mem[0x200] == 0x12345678
    assert log == [(0x200, True, 0x12345678, 0xF, 1)], log


@cocotb.test()
async def test_strobes(dut):
    """AhbSize and the low address bits become the right byte lanes."""
    mem = {}
    log = await start(dut, mem)
    cases = [(0x300, BYTE, 0x1), (0x301, BYTE, 0x2), (0x302, BYTE, 0x4),
             (0x303, BYTE, 0x8), (0x304, HALF, 0x3), (0x306, HALF, 0xC),
             (0x308, WORD, 0xF)]
    for addr, size, strb in cases:
        await ahb_run(dut, [(addr, True, 0xA5A5A5A5, size)])
        got = log[-1]
        assert got[3] == strb, f"{hex(addr)} size {size}: strb={got[3]:#x}"
        assert got[0] == addr & ~3, "ApbAddr must be word aligned"


@cocotb.test()
async def test_read_has_no_strobes(dut):
    """ApbStrb is zero for reads, whatever the access size."""
    log = await start(dut, {0x400: 0x11223344})
    for size in (BYTE, HALF, WORD):
        await ahb_run(dut, [(0x401, False, 0, size)])
        assert log[-1][3] == 0


@cocotb.test()
async def test_back_to_back(dut):
    """Pipelined AHB transfers each take exactly two cycles."""
    mem = {0x10: 0xAAAA0001, 0x14: 0xAAAA0002}
    log = await start(dut, mem)
    t0 = get_sim_time("ns")
    results = await ahb_run(dut, [(0x10, False, 0, WORD),
                                  (0x20, True, 0x55, WORD),
                                  (0x14, False, 0, WORD),
                                  (0x20, False, 0, WORD)])
    cycles = (get_sim_time("ns") - t0) / 10
    assert [r[0] for r in results] == [0xAAAA0001, 0, 0xAAAA0002, 0x55]
    assert all(r[1] == 0 for r in results)
    assert [e[0] for e in log] == [0x10, 0x20, 0x14, 0x20]
    # one cycle for the first address phase, then two per transfer
    assert cycles == 1 + 2 * 4, f"took {cycles} cycles"


async def check_wait_states(dut, waits):
    mem = {0x40: 0x0BADF00D}
    log = await start(dut, mem, wait_states=waits)
    data, resp = await ahb_read(dut, 0x40)
    assert (data, resp) == (0x0BADF00D, 0)
    assert log[-1][4] == waits + 1, f"access lasted {log[-1][4]} cycles"
    assert await ahb_write(dut, 0x44, 0x77) == 0
    assert mem[0x44] == 0x77


@cocotb.test()
async def test_one_wait_state(dut):
    """ApbReady low for one cycle stretches ACCESS and holds AhbReady."""
    await check_wait_states(dut, 1)


@cocotb.test()
async def test_three_wait_states(dut):
    """The same with three wait states."""
    await check_wait_states(dut, 3)


@cocotb.test()
async def test_error_response(dut):
    """ApbSlvErr becomes the two-cycle AHB error response."""
    mem = {0x50: 0x1, 0x54: 0x2}
    await start(dut, mem, err_addrs=(0x54,))

    async def watch(samples):
        while True:
            await FallingEdge(dut.clk)
            await Timer(3, unit="ns")
            samples.append((int(dut.AhbReady.value), int(dut.AhbResp.value)))

    samples = []
    w = cocotb.start_soon(watch(samples))
    data, resp = await ahb_read(dut, 0x54)
    w.cancel()
    assert resp == 1, "no error reported"
    # first error cycle: resp high, ready low; second: both high
    assert (0, 1) in samples and (1, 1) in samples, samples
    assert samples.index((0, 1)) + 1 == samples.index((1, 1)), samples

    # the bridge recovers: the next transfer is clean
    data, resp = await ahb_read(dut, 0x50)
    assert (data, resp) == (0x1, 0)


@cocotb.test()
async def test_idle_transfers_are_ignored(dut):
    """AhbTrans = IDLE never starts an APB transfer."""
    log = await start(dut, {})
    dut.AhbAddr.value = 0x60
    dut.AhbWrite.value = 1
    dut.AhbTrans.value = 0
    await ClockCycles(dut.clk, 5)
    assert log == []
    assert dut.ApbSel.value == 0
