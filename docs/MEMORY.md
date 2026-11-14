# Memory subsystem

The Svarog SoC has **one** RAM, at address 0, behind an APB slave port like every
other device. Code, constants, data and the stack all live in it. DDR2 on the board
is not used.

Files: `rtl/mem/apb_ram.sv` (APB wrapper), `rtl/mem/sync_single_port_RAM.sv` (RAM
primitive). Testbench: `tb/unit/apb_ram/`. Image tooling: `scripts/mkmem.py`.

## Structure

```
  APB ──> apb_ram ──> sync_single_port_RAM   (INIT_FILE image)
```

The primitive is a plain synchronous single-port RAM: one address, one write enable,
read data one clock after the address, read-first on a write. It maps onto FPGA block
RAM.

## APB timing

Zero wait states — `ApbReady` is tied high:

| Phase | What the RAM does |
|-------|-------------------|
| SETUP | reads the addressed word (the address is stable from here on) |
| ACCESS, read | the word is on `ApbRdata` |
| ACCESS, write | merges the bytes selected by `ApbStrb` into the word just read and writes it back |

The one-clock read latency of block RAM fits APB exactly: the address is presented
in SETUP and the data is needed in ACCESS.

**Byte and halfword stores by read-modify-write.** The primitive has no byte write
enables. Because every transfer reads the word in SETUP anyway, a write simply merges
`(old & ~mask) | (new & mask)` in ACCESS — no extra cycle, and the primitive stays
simple. `ApbStrb` comes from the bridge (`INTERCONNECT.md`); the RAM is the only
slave that uses it.

Reads always return the whole word; the CPU picks the byte or halfword it asked for.

## Initialization (synthesis time)

`INIT_FILE` is a `$readmemh` image applied in an `initial` block at elaboration. This
is synthesis-time initialization: the contents are folded into the block RAM
initialization of the bitstream, and Verilator reads the same file in simulation. No
JTAG, no SPI flash loader, no boot ROM. Changing the program means rebuilding the
bitstream.

Format: one 32-bit word per line, 8 hex digits, ascending word address from word 0.

`sw/rules.mk` builds the image for every program:

```sh
riscv64-unknown-elf-objcopy -O binary prog.elf prog.bin
python3 scripts/mkmem.py --bin prog.bin -o prog.hex --words 16384
```

`--words` pads to the memory depth with `nop` and refuses images that do not fit.
Unset `INIT_FILE` (the default `""`) leaves the array uninitialized.

Since the whole image — `.data` included — is in the RAM from the start, initialised
variables are linked where they run and need no startup copy; `crt0.S` only zeroes
`.bss` (`sw/link.ld`).

`tb/unit/apb_ram` demonstrates the flow: its Makefile generates `mem_init.hex` before
elaboration and passes it through `-GINIT_FILE`, exactly as a synthesis flow would;
`test_init_image` then checks the values are readable at reset.

## Size

`ADDR_WIDTH` is the depth in 32-bit words; the default 14 gives 64 KiB (16 RAMB36 of
the 135 on the xc7a100t). The decoder gives the RAM a 64 KiB region. If you change
the depth, change `RAM_SIZE` in `svarog_soc_pkg.sv`, `LENGTH` in `sw/link.ld` and
`RAM_WORDS` / `RAM_ADDR_WIDTH` in `sw/rules.mk` together.

## Known simplifications

- Every access, instruction fetch included, is a two-cycle APB transfer. A direct
  AHB-Lite RAM port would be faster; it is deliberately not done, so that the RAM is
  a slave like any other.
- No reset: after a reset the RAM holds the image as the program last modified it,
  so a program must not rely on `.data` being pristine after a warm reset.
- Addresses beyond the RAM depth but inside its region wrap.
- No protection: a program can overwrite its own code.
