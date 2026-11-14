# cocotb testbench for apb_decoder (SoC address decode, one-hot PSEL).

import cocotb
from cocotb.triggers import Timer

from socmap import SLAVE, REGIONS, HOLES, NUM_SLAVES


async def decode(dut, addr, sel=1):
    dut.ApbAddr.value = addr
    dut.ApbSel.value = sel
    await Timer(1, unit="ns")
    return int(dut.SlaveSel.value), int(dut.DecErr.value)


@cocotb.test()
async def test_width_follows_the_map(dut):
    """socmap.py and svarog_soc_pkg.sv agree on the number of slaves."""
    assert len(dut.SlaveSel) == NUM_SLAVES


@cocotb.test()
async def test_region_extents(dut):
    """First and last address of every region hit, one past does not."""
    for name, (base, size) in REGIONS.items():
        for addr in (base, base + 4, base + size - 4):
            sel, err = await decode(dut, addr)
            assert err == 0 and sel == 1 << SLAVE[name], \
                f"{name}: {hex(addr)} decoded as sel={sel:b} err={err}"
        sel, _ = await decode(dut, base + size)
        assert not (sel & (1 << SLAVE[name])), \
            f"{name}: {hex(base + size)} still selects the region"


@cocotb.test()
async def test_onehot(dut):
    """The select is always one-hot or all-zero: regions never overlap."""
    for name, (base, size) in REGIONS.items():
        for addr in (base, base + size // 2, base + size - 4):
            sel, _ = await decode(dut, addr)
            assert bin(sel).count("1") == 1, f"{hex(addr)}: sel={sel:b}"


@cocotb.test()
async def test_unmapped(dut):
    """Addresses outside every region raise DecErr with no select."""
    for addr in HOLES:
        sel, err = await decode(dut, addr)
        assert err == 1 and sel == 0, f"{hex(addr)}: sel={sel:b} err={err}"


@cocotb.test()
async def test_idle_bus_selects_nothing(dut):
    """Without ApbSel from the bridge there is no PSEL and no error."""
    for name, (base, _) in REGIONS.items():
        sel, err = await decode(dut, base, sel=0)
        assert sel == 0 and err == 0, f"{name}: sel={sel:b} err={err} while idle"
    sel, err = await decode(dut, HOLES[0], sel=0)
    assert sel == 0 and err == 0
