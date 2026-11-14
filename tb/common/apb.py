# Reusable APB slave model for Svarog testbenches.
#
# Sits on the master side of a DUT (the bridge, or the whole
# interconnect) and answers transfers from a dict of word-aligned byte
# address -> 32-bit word; writes honour the byte strobes.
#
#   wait_states  number of extra ACCESS cycles before ready
#   err_addrs    addresses that complete with a slave error
#
# The model also checks the protocol the lectures describe: every
# transfer has exactly one SETUP cycle before ACCESS, and the address,
# direction and write data stay stable from SETUP to the end of ACCESS.
# Completed transfers are appended to `log` as
# (addr, write, data, strb, access_cycles).

from cocotb.triggers import RisingEdge, FallingEdge, Timer


async def apb_slave(clk, sel, enable, write, addr, wdata, rdata, ready, slverr,
                    mem, strb=None, wait_states=0, err_addrs=(), log=None,
                    default=0):
    ready.value = 0
    slverr.value = 0
    rdata.value = 0
    setup = None           # (addr, write, wdata) seen in the setup phase
    waited = 0
    while True:
        await FallingEdge(clk)
        await Timer(1, unit="ns")
        if not sel.value:
            assert not enable.value, "ApbEnable high without ApbSel"
            ready.value = 0
            slverr.value = 0
            setup = None
            await RisingEdge(clk)
            continue

        a = int(addr.value)
        w = bool(write.value)
        if not enable.value:
            # setup phase
            assert setup is None, "two SETUP cycles in a row"
            setup = (a, w, int(wdata.value) if w else None)
            waited = 0
            ready.value = 0
            slverr.value = 0
            await RisingEdge(clk)
            continue

        # access phase
        assert setup is not None, "ACCESS without a preceding SETUP"
        assert (a, w) == setup[:2], "address/direction changed during a transfer"
        if w:
            assert int(wdata.value) == setup[2], "write data changed during a transfer"

        if waited < wait_states:
            waited += 1
            ready.value = 0
            await RisingEdge(clk)
            continue

        ready.value = 1
        err = a in err_addrs
        slverr.value = int(err)
        word = a & 0xFFFFFFFC
        s = int(strb.value) if strb is not None else (0xF if w else 0)
        if w:
            if not err:
                mask = 0
                for i in range(4):
                    if (s >> i) & 1:
                        mask |= 0xFF << (8 * i)
                mem[word] = (mem.get(word, 0) & ~mask) | (int(wdata.value) & mask)
            data = int(wdata.value)
        else:
            data = mem.get(word, default)
            rdata.value = data
        await RisingEdge(clk)          # the transfer completes here
        if log is not None:
            log.append((a, w, data, s, waited + 1))
        setup = None
