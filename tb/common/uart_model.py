# UART helpers for the SoC-level testbenches: decode what the SoC sends
# and send bytes to it, at the pins, as 8N1 frames.
#
# `bit_cycles` is the number of clock cycles per bit — the value the
# program wrote to the UART's DIV register.

from cocotb.triggers import RisingEdge, ClockCycles, Timer


async def _sample(clk, pin):
    """Read a pin just after a clock edge, once it has settled."""
    await RisingEdge(clk)
    await Timer(1, unit="ns")
    return int(pin.value)


async def uart_monitor(clk, tx, bit_cycles, out):
    """Decode frames off `tx` forever, appending bytes to the list `out`.

    Resynchronises on every frame: waits for the line to be idle, then
    for a start bit, so a low level out of reset is not taken for one.
    """
    while True:
        while await _sample(clk, tx) != 1:      # idle
            pass
        while await _sample(clk, tx) != 0:      # start bit
            pass
        await ClockCycles(clk, bit_cycles // 2)  # middle of the start bit
        byte = 0
        for i in range(8):                      # LSB first
            await ClockCycles(clk, bit_cycles)
            await Timer(1, unit="ns")
            byte |= int(tx.value) << i
        out.append(byte)


async def uart_send(clk, rx, bit_cycles, data):
    """Send bytes (or a str) to the SoC on its `rx` pin."""
    if isinstance(data, str):
        data = data.encode()
    for byte in data:
        bits = [0] + [(byte >> i) & 1 for i in range(8)] + [1]
        for b in bits:
            rx.value = b
            await ClockCycles(clk, bit_cycles)


def text(out):
    return "".join(chr(b) for b in out)
