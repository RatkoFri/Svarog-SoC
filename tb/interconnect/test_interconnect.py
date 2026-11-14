# cocotb testbench for the whole interconnect: bridge + decoder + mux,
# wired as in svarog_soc (interconnect_tb.sv). The testbench plays the
# CPU on the AHB side and every slave on the APB side, so it checks
# what a slave author relies on: PSEL is one-hot and reaches only the
# addressed slave, and that slave's data, wait states and errors get
# back to the CPU.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer
from cocotb.utils import get_sim_time

from ahb_master import ahb_idle, ahb_run, ahb_read, ahb_write
from socmap import SLAVE, REGIONS, HOLES, NUM_SLAVES

WORD = 2


class Slaves:
    """All APB slaves at once, driven on the flattened slave ports."""

    def __init__(self, dut, wait_states=None, errors=()):
        self.dut = dut
        self.mem = [dict() for _ in range(NUM_SLAVES)]
        self.wait_states = wait_states or [0] * NUM_SLAVES
        self.errors = set(errors)           # slave indices that error
        self.transfers = []                 # (slave, addr, write)

    def drive(self, rdata, ready, err):
        self.dut.SlaveRdata.value = sum(w << (32 * i) for i, w in enumerate(rdata))
        self.dut.SlaveReady.value = ready
        self.dut.SlaveSlvErr.value = err

    async def run(self):
        dut = self.dut
        waited = 0
        self.drive([0] * NUM_SLAVES, 0, 0)
        while True:
            await FallingEdge(dut.clk)
            await Timer(1, unit="ns")
            sel = int(dut.SlaveSel.value)
            assert bin(sel).count("1") <= 1, f"PSEL not one-hot: {sel:b}"
            if sel == 0:
                self.drive([0] * NUM_SLAVES, 0, 0)
                waited = 0
                continue
            s = sel.bit_length() - 1
            addr = int(dut.ApbAddr.value)
            if not dut.ApbEnable.value:          # setup
                waited = 0
                self.drive([0] * NUM_SLAVES, 0, 0)
                continue
            if waited < self.wait_states[s]:     # access, wait state
                waited += 1
                self.drive([0] * NUM_SLAVES, 0, 0)
                continue
            rdata = [0xBAD00000 + i for i in range(NUM_SLAVES)]
            if dut.ApbWrite.value:
                self.mem[s][addr] = int(dut.ApbWdata.value)
            else:
                rdata[s] = self.mem[s].get(addr, 0)
            # every other slave is "ready" with junk: it must not leak
            self.drive(rdata, (1 << NUM_SLAVES) - 1,
                       (1 << s) if s in self.errors else 0)
            await RisingEdge(dut.clk)
            self.transfers.append((s, addr, bool(dut.ApbWrite.value)))


async def start(dut, **kwargs):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    ahb_idle(dut)
    slaves = Slaves(dut, **kwargs)
    cocotb.start_soon(slaves.run())
    dut.reset.value = 1
    for _ in range(2):
        await RisingEdge(dut.clk)
    dut.reset.value = 0
    await FallingEdge(dut.clk)
    return slaves


@cocotb.test()
async def test_routing_per_slave(dut):
    """A write then a read at each region reaches exactly that slave."""
    slaves = await start(dut)
    for name, (base, size) in REGIONS.items():
        s = SLAVE[name]
        for offset in (0, size - 4):
            value = 0xC0000000 | (s << 16) | (offset & 0xFFFF)
            assert await ahb_write(dut, base + offset, value) == 0
            data, resp = await ahb_read(dut, base + offset)
            assert (data, resp) == (value, 0), f"{name}+{offset:#x}: {data:#x}"
            assert slaves.mem[s][base + offset] == value
    for s, mem in enumerate(slaves.mem):
        assert len(mem) == 2, f"slave {s} saw {len(mem)} addresses"


@cocotb.test()
async def test_unmapped_address_errors(dut):
    """An address in no region gives an AHB error and selects no slave."""
    slaves = await start(dut)
    for addr in HOLES:
        _, resp = await ahb_read(dut, addr)
        assert resp == 1, f"{hex(addr)}: no error response"
        assert await ahb_write(dut, addr, 0x1) == 1
    assert slaves.transfers == [], "an unmapped access reached a slave"
    # and the bus still works afterwards
    base = REGIONS["GPIO"][0]
    assert await ahb_write(dut, base, 0x5A) == 0
    assert (await ahb_read(dut, base)) == (0x5A, 0)


@cocotb.test()
async def test_wait_states_per_slave(dut):
    """A slow slave stretches only its own transfers."""
    waits = [0] * NUM_SLAVES
    waits[SLAVE["UART"]] = 3
    await start(dut, wait_states=waits)

    async def cycles(addr):
        t0 = get_sim_time("ns")
        await ahb_read(dut, addr)
        return (get_sim_time("ns") - t0) / 10

    fast = await cycles(REGIONS["GPIO"][0])
    slow = await cycles(REGIONS["UART"][0])
    assert slow == fast + 3, f"fast {fast} cycles, slow {slow} cycles"


@cocotb.test()
async def test_slave_error(dut):
    """A slave's ApbSlvErr reaches the CPU; other slaves are unaffected."""
    await start(dut, errors=(SLAVE["TIMER"],))
    _, resp = await ahb_read(dut, REGIONS["TIMER"][0])
    assert resp == 1
    _, resp = await ahb_read(dut, REGIONS["UART"][0])
    assert resp == 0


@cocotb.test()
async def test_back_to_back_across_slaves(dut):
    """Pipelined transfers to different slaves stay in order."""
    slaves = await start(dut)
    ops = []
    for i, (name, (base, _)) in enumerate(REGIONS.items()):
        ops.append((base + 8, True, 0x100 + i, WORD))
    for name, (base, _) in REGIONS.items():
        ops.append((base + 8, False, 0, WORD))
    results = await ahb_run(dut, ops)
    n = len(REGIONS)
    assert [r[0] for r in results[n:]] == [0x100 + i for i in range(n)]
    assert [t[0] for t in slaves.transfers] == \
        [SLAVE[name] for name in REGIONS] * 2
