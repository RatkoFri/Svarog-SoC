# cocotb testbench for apb_mux (read data / ready / error return path).

import cocotb
from cocotb.triggers import Timer

from socmap import NUM_SLAVES


def flat(words):
    """Pack one 32-bit word per slave into the flattened vector."""
    return sum(w << (32 * i) for i, w in enumerate(words))


async def drive(dut, sel, rdata, ready, slverr, decerr=0):
    dut.SlaveSel.value = sel
    dut.DecErr.value = decerr
    dut.SlaveRdata.value = flat(rdata)
    dut.SlaveReady.value = ready
    dut.SlaveSlvErr.value = slverr
    await Timer(1, unit="ns")
    return (int(dut.ApbRdata.value), int(dut.ApbReady.value),
            int(dut.ApbSlvErr.value))


@cocotb.test()
async def test_selects_each_slave(dut):
    """The selected slave's data, ready and error reach the master."""
    words = [0x1000_0000 + i for i in range(NUM_SLAVES)]
    for s in range(NUM_SLAVES):
        # only the selected slave is ready: the others must not leak
        got = await drive(dut, 1 << s, words, 1 << s, 0)
        assert got == (words[s], 1, 0), f"slave {s}: {got}"
        # selected slave inserts a wait state while the others are ready
        all_ready = (1 << NUM_SLAVES) - 1
        got = await drive(dut, 1 << s, words, all_ready & ~(1 << s), 0)
        assert got[1] == 0, f"slave {s}: wait state not passed on"
        # selected slave reports an error
        got = await drive(dut, 1 << s, words, 1 << s, 1 << s)
        assert got == (words[s], 1, 1), f"slave {s}: error not passed on"


@cocotb.test()
async def test_idle(dut):
    """With no slave selected the mux returns zeros and is not ready."""
    words = [0xFFFF_FFFF] * NUM_SLAVES
    all_ones = (1 << NUM_SLAVES) - 1
    assert await drive(dut, 0, words, all_ones, all_ones) == (0, 0, 0)


@cocotb.test()
async def test_decode_error(dut):
    """An unmapped transfer completes at once with an error."""
    words = [0xFFFF_FFFF] * NUM_SLAVES
    assert await drive(dut, 0, words, 0, 0, decerr=1) == (0, 1, 1)
