# AHB-Lite master driver for the bridge and interconnect testbenches.
#
# Plays the role of the CPU on the AHB side of ahb_to_apb (signals
# AhbAddr/AhbWrite/AhbTrans/AhbSize/AhbWdata/AhbRdata/AhbReady/AhbResp).
#
# AHB is pipelined: the address phase of one transfer overlaps the data
# phase of the previous one. ahb_run() therefore takes a list of
# transfers and issues them back to back, exactly as a CPU would.
#
#   ops      list of (addr, write, wdata, size)   size: 0 byte, 1 half,
#            2 word
#   returns  list of (rdata, resp), one per transfer
#
# All driving happens on the falling clock edge.

from cocotb.triggers import RisingEdge, FallingEdge, Timer

HTRANS_IDLE = 0
HTRANS_NSEQ = 2


def ahb_idle(dut):
    dut.AhbAddr.value = 0
    dut.AhbWrite.value = 0
    dut.AhbTrans.value = HTRANS_IDLE
    dut.AhbSize.value = 2
    dut.AhbWdata.value = 0


async def ahb_run(dut, ops, timeout=200):
    pending = list(ops)
    data_op = None          # transfer currently in its data phase
    results = []
    for _ in range(timeout):
        if not pending and data_op is None:
            return results
        # address phase of the next transfer
        if pending:
            addr, write, _, size = pending[0]
            dut.AhbAddr.value = addr
            dut.AhbWrite.value = int(write)
            dut.AhbSize.value = size
            dut.AhbTrans.value = HTRANS_NSEQ
        else:
            ahb_idle(dut)
        # data phase of the previous one
        if data_op is not None and data_op[1]:
            dut.AhbWdata.value = data_op[2]
        # sample late in the low phase: the slave models answer 1 ns
        # after the falling edge and the response is combinational
        await Timer(3, unit="ns")
        if dut.AhbReady.value:
            if data_op is not None:
                results.append((int(dut.AhbRdata.value) if not data_op[1] else 0,
                                int(dut.AhbResp.value)))
            data_op = pending.pop(0) if pending else None
        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)
    raise AssertionError("AHB transfers did not complete")


async def ahb_write(dut, addr, data, size=2):
    return (await ahb_run(dut, [(addr, True, data, size)]))[0][1]


async def ahb_read(dut, addr, size=2):
    return (await ahb_run(dut, [(addr, False, 0, size)]))[0]
