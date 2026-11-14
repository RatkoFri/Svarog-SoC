# cocotb testbench for the reference UART (rtl/periph/uart.sv).
#
# Register map: 0x00 CTRL {bit1 TX_IRQ_EN, bit0 RX_IRQ_EN}, 0x04 DIV
# (clk cycles per bit), 0x08 TX (wo), 0x0C RX (ro, read clears),
# 0x10 STATUS {bit2 RX_OVERRUN, bit1 RX_AVAIL, bit0 TX_EMPTY}.

import cocotb
from cocotb.triggers import RisingEdge, FallingEdge, ClockCycles

from apb_master import apb_start, apb_read, apb_write

CTRL, DIV, TX, RX, STATUS = 0x00, 0x04, 0x08, 0x0C, 0x10
RX_IRQ_EN, TX_IRQ_EN = 1, 2
TX_EMPTY, RX_AVAIL, RX_OVERRUN = 1, 2, 4
BIT = 12   # clk cycles per bit; deliberately not a multiple of 16


async def start(dut):
    dut.Rx.value = 1                    # UART line idles high
    await apb_start(dut)


async def tx_monitor(dut, frames, nframes=1):
    """Decode 8N1 frames from the Tx pin by mid-bit sampling."""
    for _ in range(nframes):
        while dut.Tx.value == 1:        # wait for a start bit
            await RisingEdge(dut.clk)
        await ClockCycles(dut.clk, BIT // 2)     # middle of start bit
        assert dut.Tx.value == 0, "start bit not low at mid-bit"
        byte = 0
        for i in range(8):              # LSB first
            await ClockCycles(dut.clk, BIT)
            byte |= int(dut.Tx.value) << i
        await ClockCycles(dut.clk, BIT)          # stop bit
        assert dut.Tx.value == 1, "stop bit not high"
        frames.append(byte)


async def send_frame(dut, byte, stop=1):
    """Drive one 8N1 frame onto the Rx pin."""
    bits = [0] + [(byte >> i) & 1 for i in range(8)] + [stop]
    for b in bits:
        dut.Rx.value = b
        await ClockCycles(dut.clk, BIT)
    dut.Rx.value = 1


async def wait_status(dut, mask, cycles=40):
    for _ in range(cycles):
        if (await apb_read(dut, STATUS)) & mask:
            return
        await ClockCycles(dut.clk, BIT)
        await FallingEdge(dut.clk)
    raise AssertionError(f"STATUS bit {mask:#x} never set")


@cocotb.test()
async def test_reset_values(dut):
    """Every register reads its reset value; line idle, no interrupt."""
    await start(dut)
    assert await apb_read(dut, CTRL) == 0
    assert await apb_read(dut, DIV) == 0
    assert await apb_read(dut, TX) == 0
    assert await apb_read(dut, RX) == 0
    assert await apb_read(dut, STATUS) == TX_EMPTY
    assert dut.Tx.value == 1
    assert dut.Irq.value == 0


@cocotb.test()
async def test_register_readback(dut):
    """CTRL and DIV return what was written."""
    await start(dut)
    await apb_write(dut, DIV, 2604)
    assert await apb_read(dut, DIV) == 2604
    await apb_write(dut, CTRL, RX_IRQ_EN)
    assert await apb_read(dut, CTRL) == RX_IRQ_EN
    await apb_write(dut, CTRL, 0)
    assert await apb_read(dut, CTRL) == 0


@cocotb.test()
async def test_transmit_frame(dut):
    """A write to TX produces one correct 8N1 frame on the Tx pin."""
    await start(dut)
    await apb_write(dut, DIV, BIT)
    frames = []
    cocotb.start_soon(tx_monitor(dut, frames))
    await apb_write(dut, TX, 0x55)
    assert not (await apb_read(dut, STATUS)) & TX_EMPTY, "busy flag not set"
    await ClockCycles(dut.clk, BIT * 12)
    assert frames == [0x55], f"frames={[hex(f) for f in frames]}"
    await FallingEdge(dut.clk)
    assert (await apb_read(dut, STATUS)) & TX_EMPTY, "transmitter still busy"


@cocotb.test()
async def test_transmit_two_bytes(dut):
    """Two writes produce two frames with the right bytes in order."""
    await start(dut)
    await apb_write(dut, DIV, BIT)
    frames = []
    cocotb.start_soon(tx_monitor(dut, frames, nframes=2))
    await apb_write(dut, TX, 0xA3)
    await wait_status(dut, TX_EMPTY)
    await apb_write(dut, TX, 0x5C)
    await ClockCycles(dut.clk, BIT * 12)
    assert frames == [0xA3, 0x5C], f"frames={[hex(f) for f in frames]}"


@cocotb.test()
async def test_write_while_busy_is_ignored(dut):
    """A second TX write during a frame does not corrupt it."""
    await start(dut)
    await apb_write(dut, DIV, BIT)
    frames = []
    cocotb.start_soon(tx_monitor(dut, frames, nframes=2))
    await apb_write(dut, TX, 0x81)
    await apb_write(dut, TX, 0x7E)      # frame still on the line
    await ClockCycles(dut.clk, BIT * 24)
    assert frames == [0x81], f"frames={[hex(f) for f in frames]}"


@cocotb.test()
async def test_receive_frame(dut):
    """A frame on Rx lands in RX; reading RX clears RX_AVAIL."""
    await start(dut)
    await apb_write(dut, DIV, BIT)
    await send_frame(dut, 0x96)
    await FallingEdge(dut.clk)
    assert (await apb_read(dut, STATUS)) & RX_AVAIL, "no byte available"
    assert await apb_read(dut, RX) == 0x96
    assert not (await apb_read(dut, STATUS)) & RX_AVAIL, "RX_AVAIL not cleared"


@cocotb.test()
async def test_loopback(dut):
    """Tx looped to Rx: every byte value pattern survives the round trip."""
    await start(dut)
    await apb_write(dut, DIV, BIT)

    async def loop():
        while True:
            await RisingEdge(dut.clk)
            dut.Rx.value = dut.Tx.value

    cocotb.start_soon(loop())
    for byte in (0x00, 0xFF, 0x55, 0xAA, 0x01, 0x80):
        await apb_write(dut, TX, byte)
        await wait_status(dut, RX_AVAIL)
        got = await apb_read(dut, RX)
        assert got == byte, f"received {got:#04x}, sent {byte:#04x}"
        await wait_status(dut, TX_EMPTY)


@cocotb.test()
async def test_framing_error_is_dropped(dut):
    """A frame with a low stop bit is not delivered."""
    await start(dut)
    await apb_write(dut, DIV, BIT)
    await send_frame(dut, 0x42, stop=0)
    await ClockCycles(dut.clk, BIT * 2)
    await FallingEdge(dut.clk)
    assert not (await apb_read(dut, STATUS)) & RX_AVAIL


@cocotb.test()
async def test_overrun(dut):
    """A second byte before RX is read sets RX_OVERRUN; the newer wins."""
    await start(dut)
    await apb_write(dut, DIV, BIT)
    await send_frame(dut, 0x11)
    await send_frame(dut, 0x22)
    await FallingEdge(dut.clk)
    status = await apb_read(dut, STATUS)
    assert status & RX_OVERRUN and status & RX_AVAIL, f"status={status:#x}"
    assert await apb_read(dut, RX) == 0x22
    assert (await apb_read(dut, STATUS)) & (RX_OVERRUN | RX_AVAIL) == 0


@cocotb.test()
async def test_rx_irq_sets_and_clears(dut):
    """Irq rises with RX_AVAIL when enabled and falls on a read of RX."""
    await start(dut)
    await apb_write(dut, DIV, BIT)
    await send_frame(dut, 0x33)
    await FallingEdge(dut.clk)
    assert dut.Irq.value == 0, "Irq without RX_IRQ_EN"
    await apb_write(dut, CTRL, RX_IRQ_EN)
    assert dut.Irq.value == 1, "Irq not raised for a waiting byte"
    # reading another register must not clear it
    await apb_read(dut, STATUS)
    assert dut.Irq.value == 1
    assert await apb_read(dut, RX) == 0x33
    assert dut.Irq.value == 0, "Irq not cleared by reading RX"


@cocotb.test()
async def test_tx_irq_sets_and_clears(dut):
    """The transmit interrupt follows TX_EMPTY while enabled."""
    await start(dut)
    await apb_write(dut, DIV, BIT)
    await apb_write(dut, CTRL, TX_IRQ_EN)
    assert dut.Irq.value == 1, "transmitter idle, Irq expected"
    await apb_write(dut, TX, 0x0F)
    assert dut.Irq.value == 0, "Irq not cleared by writing TX"
    await ClockCycles(dut.clk, BIT * 11)
    await FallingEdge(dut.clk)
    assert dut.Irq.value == 1, "Irq not raised when the frame finished"
    await apb_write(dut, CTRL, 0)
    assert dut.Irq.value == 0, "Irq not cleared by dropping TX_IRQ_EN"
