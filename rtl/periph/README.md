# Reference peripherals

APB slaves that are part of the Svarog SoC's own infrastructure: the BSP, the
examples and the testbenches depend on them. The peripherals built in the labs are
separate modules with their own names.

| File | Role |
|------|------|
| `uart.sv`, `uart_tx.sv`, `uart_rx.sv` | UART, 8N1, one-byte buffers, receive/transmit interrupt |
| `timer.sv` | 64-bit timer with compare, the machine timer interrupt |
| `gpio.sv` | output and input pins |

All three follow the slave conventions in `docs/INTERCONNECT.md`: registers are
written in the access phase, reads are combinational, `ApbReady` is tied high (zero
wait states), `ApbSlvErr` is tied low, registers are whole 32-bit words, and unmapped
offsets read as zero. Each has a unit testbench in `tb/unit/<name>/`.

## Register maps

Offsets are in bytes from the peripheral's base address.

### UART (`0x2000_0000`)

| Offset | Name | Access | Reset | Description |
|--------|------|--------|-------|-------------|
| 0x00 | CTRL | RW | 0 | bit0 `RX_IRQ_EN`, bit1 `TX_IRQ_EN` |
| 0x04 | DIV | RW | 0 | clock cycles per bit (16 bits): `CPU_HZ / baud` |
| 0x08 | TX | WO | – | write sends the low byte; ignored while a frame is being sent; reads 0 |
| 0x0C | RX | RO | 0 | last received byte; **the read clears `RX_AVAIL` and `RX_OVERRUN`** |
| 0x10 | STATUS | RO | 1 | bit0 `TX_EMPTY`, bit1 `RX_AVAIL`, bit2 `RX_OVERRUN` |

`Irq = (RX_IRQ_EN & RX_AVAIL) | (TX_IRQ_EN & TX_EMPTY)`, a level. The receive
interrupt is cleared by reading RX; the transmit interrupt by writing TX or by
clearing `TX_IRQ_EN`. External interrupt line `IRQ_UART`.

There is no FIFO: a byte that arrives before the previous one was read overwrites it
and sets `RX_OVERRUN`. A frame with a bad stop bit is dropped. The receiver samples
in the middle of each bit, so `DIV` needs no particular alignment.

### Timer (`0x2000_1000`)

| Offset | Name | Access | Reset | Description |
|--------|------|--------|-------|-------------|
| 0x00 | CTRL | RW | 0 | bit0 `ENABLE`, bit1 `CLEAR` (write 1 zeroes the counter, reads 0), bit2 `IRQ_EN` |
| 0x04 | COUNT_LO | RO | 0 | counter, low word |
| 0x08 | COUNT_HI | RO | 0 | counter, high word |
| 0x0C | CMP_LO | RW | 0xFFFF_FFFF | compare, low word |
| 0x10 | CMP_HI | RW | 0xFFFF_FFFF | compare, high word |

The counter advances every clock while `ENABLE` is set.
`Irq = IRQ_EN & (COUNT >= CMP)`, a level, registered (it follows a register write one
clock later). It is cleared by writing a compare value above the counter, by `CLEAR`,
or by clearing `IRQ_EN` — the `mtime`/`mtimecmp` idea. It drives the CPU's machine
timer interrupt, not an external line. The compare resets to all ones, so nothing
fires until software programs it.

### GPIO (`0x2000_2000`)

| Offset | Name | Access | Reset | Description |
|--------|------|--------|-------|-------------|
| 0x00 | OUT | RW | 0 | drives `GpioOut`, reads back |
| 0x04 | IN | RO | – | `GpioIn` after a 2-FF synchroniser |

`WIDTH` pins each way (16 in the SoC: the LEDs and the slide switches). No interrupt.
