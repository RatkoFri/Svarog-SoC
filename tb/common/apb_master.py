# APB master driver for slave-unit testbenches.
#
# Drives one transfer at a time on a DUT slave port with the project
# signal names (ApbSel/ApbEnable/ApbWrite/ApbAddr/ApbWdata/ApbRdata/
# ApbReady/ApbSlvErr, and ApbStrb if the DUT has it). Complements apb.py,
# which models the *slave* side.
#
# A transfer follows the lecture state machine:
#   SETUP  : ApbSel=1, ApbEnable=0, address/write/data valid (1 cycle)
#   ACCESS : ApbEnable=1, held until ApbReady is sampled high
# All driving happens on the falling clock edge so the DUT samples
# cleanly on the rising edge.

from cocotb.clock import Clock
import cocotb
from cocotb.triggers import RisingEdge, FallingEdge, Timer


def _has(dut, name):
    try:
        getattr(dut, name)
        return True
    except AttributeError:
        return False


async def apb_start(dut, period_ns=10, reset_cycles=2):
    """Start the clock, idle the bus and apply the synchronous reset."""
    cocotb.start_soon(Clock(dut.clk, period_ns, unit="ns").start())
    for name in ("ApbSel", "ApbEnable", "ApbWrite", "ApbAddr", "ApbWdata",
                 "ApbStrb"):
        if _has(dut, name):
            getattr(dut, name).value = 0
    if _has(dut, "reset"):
        dut.reset.value = 1
        for _ in range(reset_cycles):
            await RisingEdge(dut.clk)
        dut.reset.value = 0
    await FallingEdge(dut.clk)


async def apb_transfer(dut, addr, write, data=0, strb=0xF, timeout=50):
    """One APB transfer. Returns (read data, slave error)."""
    # setup phase
    dut.ApbSel.value = 1
    dut.ApbEnable.value = 0
    dut.ApbWrite.value = int(write)
    dut.ApbAddr.value = addr
    dut.ApbWdata.value = data if write else 0
    if _has(dut, "ApbStrb"):
        dut.ApbStrb.value = strb if write else 0
    await FallingEdge(dut.clk)

    # access phase, held while the slave inserts wait states
    dut.ApbEnable.value = 1
    for _ in range(timeout):
        await Timer(1, unit="ns")
        if dut.ApbReady.value:
            rdata = int(dut.ApbRdata.value) if not write else 0
            err = bool(dut.ApbSlvErr.value)
            break
        await FallingEdge(dut.clk)
    else:
        raise AssertionError(f"ApbReady never rose for {hex(addr)}")

    # the transfer completes on this rising edge; then idle the bus
    await FallingEdge(dut.clk)
    dut.ApbSel.value = 0
    dut.ApbEnable.value = 0
    dut.ApbWrite.value = 0
    return rdata, err


async def apb_write(dut, addr, data, strb=0xF, check_err=True):
    """Write a register. Returns the slave-error flag."""
    _, err = await apb_transfer(dut, addr, True, data, strb)
    if check_err:
        assert not err, f"ApbSlvErr on write to {hex(addr)}"
    return err


async def apb_read(dut, addr, check_err=True):
    """Read a register. Returns the read data."""
    data, err = await apb_transfer(dut, addr, False)
    if check_err:
        assert not err, f"ApbSlvErr on read of {hex(addr)}"
    return data
