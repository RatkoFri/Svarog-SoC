# Interconnect: AHB-Lite to APB

The Svarog bus is APB with **one master** — the bridge — and N slaves. Three small
modules in `rtl/interconnect/` make it up:

| Module | Role |
|--------|------|
| `ahb_to_apb` | bridge from the CPU's AHB-Lite port; the APB master state machine |
| `apb_decoder` | address → one-hot `PSEL`, plus a decode-error flag |
| `apb_mux` | returns the selected slave's read data, ready and error |

Testbenches: `tb/unit/ahb_to_apb`, `tb/unit/apb_decoder`, `tb/unit/apb_mux`, and
`tb/interconnect` for the three wired together as in the SoC.

## APB signals

The signal set is APB3, as in the lectures, with project names:

| APB name | Project name | Driven by | Meaning |
|----------|--------------|-----------|---------|
| `PSEL` | `ApbSel` | decoder | this slave is addressed |
| `PENABLE` | `ApbEnable` | bridge | second and later cycles of a transfer |
| `PWRITE` | `ApbWrite` | bridge | 1 = write, 0 = read |
| `PADDR` | `ApbAddr` | bridge | byte address, word aligned |
| `PWDATA` | `ApbWdata` | bridge | write data |
| `PRDATA` | `ApbRdata` | slave | read data |
| `PREADY` | `ApbReady` | slave | the transfer completes this cycle |
| `PSLVERR` | `ApbSlvErr` | slave | the transfer failed |

`PCLK` and `PRESETn` are the SoC's `clk` and (active-high, synchronous) `reset`.

**One APB4 signal is added, for the RAM only:** `ApbStrb` (`PSTRB`), the byte lanes
of a write. C code stores bytes and halfwords, and the RAM must know which bytes to
change. Peripherals do not receive `ApbStrb`: their port list is exactly the table
above, and their registers are whole 32-bit words. Software must therefore access
peripheral registers with 32-bit loads and stores, which the `REG32` macro in
`sw/bsp/svarog.h` does.

## A transfer

```
            IDLE │ SETUP │ ACCESS │ IDLE
  clk      __/‾‾\__/‾‾\__/‾‾\__/‾‾\__
  ApbSel   ______/‾‾‾‾‾‾‾‾‾‾‾‾‾\______
  ApbEnable_____________/‾‾‾‾‾‾\______
  ApbAddr  ------<   valid     >------
  ApbReady -------------/‾‾‾‾‾‾\------   (slave; low = wait state)
```

- **SETUP** (exactly one cycle): `ApbSel` high, `ApbEnable` low; address, direction
  and write data are valid and stay stable until the transfer ends.
- **ACCESS**: `ApbEnable` high. The transfer completes on the first rising clock edge
  where `ApbReady` is high. A slave that needs more time holds `ApbReady` low.

What a slave must do:

- write its registers when `ApbSel & ApbEnable & ApbWrite` (with `ApbReady` tied
  high that is exactly one clock per write);
- have `ApbRdata` valid in the access phase;
- drive `ApbReady` high to finish, and `ApbSlvErr` high in that same cycle to report
  an error (tie it low if the slave reports none).

## The bridge

`ahb_to_apb` has the lecture's three states plus one for errors:

| State | APB | AHB |
|-------|-----|-----|
| `IDLE` | idle | `AhbReady` high, waiting for an address phase |
| `SETUP` | `ApbSel` | `AhbReady` low (data phase stretched) |
| `ACCESS` | `ApbSel`, `ApbEnable` | `AhbReady` follows `ApbReady` |
| `ERROR` | idle | second cycle of the AHB error response |

An AHB address phase is captured when `AhbReady` is high and `AhbTrans[1]` is set.
When a transfer completes, a new address phase can be captured in that same cycle,
so back-to-back transfers take **two cycles each** (measured in
`test_back_to_back`); the first one after idle takes three.

`AhbWdata` is valid during the whole AHB data phase, which is SETUP + ACCESS, so it
is passed straight to `ApbWdata`. `ApbStrb` is derived from `AhbSize` and the low
address bits and is zero for reads. `ApbAddr` is word aligned.

**Errors.** `ApbSlvErr` at the end of a transfer becomes the two-cycle AHB error
response (`AhbResp` high with `AhbReady` low, then both high). Hazard3 turns it into
an access-fault exception: `mcause` 1 for an instruction fetch, 5 for a load, 7 for a
store.

## Decoder and mux

`apb_decoder` matches the address against every region in `svarog_soc_pkg` with one
comparator each — `(Addr & ~(SIZE-1)) == BASE` — which is why regions must be
**power-of-two sized and naturally aligned**. It outputs:

- `SlaveSel[NUM_SLAVES-1:0]`: one-hot `PSEL`, all zero when the bus is idle;
- `DecErr`: a transfer is in progress and addresses no region.

`apb_mux` selects `ApbRdata`, `ApbReady` and `ApbSlvErr` of the slave with `PSEL`
set. On `DecErr` it answers by itself with `ApbReady` and `ApbSlvErr` both high, so
an access to an unmapped address ends at once in a bus error instead of hanging the
CPU.

The slave side uses flattened packed vectors, because the coding standard does not
allow arrays of signals as ports: slave `s` owns bit `s` of `SlaveSel`, `SlaveReady`
and `SlaveSlvErr`, and bits `[s*32 +: 32]` of `SlaveRdata`. The indices are the
`SLAVE_*` constants in the package. `ApbEnable`, `ApbWrite`, `ApbAddr` and `ApbWdata`
go to every slave unchanged.

## Address map

| Slave | Index | Base | Size |
|-------|-------|------|------|
| RAM | 0 | `0x0000_0000` | `0x0001_0000` (64 KiB) |
| UART | 1 | `0x2000_0000` | `0x0000_1000` (4 KiB) |
| TIMER | 2 | `0x2000_1000` | `0x0000_1000` (4 KiB) |
| GPIO | 3 | `0x2000_2000` | `0x0000_1000` (4 KiB) |

The map is defined once, in `config/svarog_soc_pkg.sv`, and mirrored in
`tb/common/socmap.py` and `sw/bsp/svarog.h`. To add a slave, follow
`ADDING_A_SLAVE.md`.

## Known simplifications

- One transfer at a time, two cycles minimum: APB is not pipelined.
- A slave sees the full 32-bit `ApbAddr` and uses only the low 12 bits; addresses
  inside a region that hold no register read as zero (the reference peripherals do
  not report them as errors).
- No `PPROT`, no `PSTRB` on peripherals.
