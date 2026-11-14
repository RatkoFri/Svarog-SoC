# Known Bugs

Tracks known issues in Svarog — RTL, software, testbenches, or the FPGA flow —
that are not fixed yet. Add a new entry when a bug is found but not
immediately fixed; move it to "Fixed" (or delete it) once resolved, noting
the commit that fixed it.

## Index

| ID | Title | Component | Severity | Status |
|----|-------|-----------|----------|--------|
| BUG-CLOCK | SoC clock frequency on the board is not confirmed | fpga, sw | High | Open |
| TODO-IRQ | Add a CLINT and a global interrupt controller | periph, cpu, sw | Low | Open |

**Component:** `cpu`, `interconnect`, `mem`, `periph/<name>`, `sw`,
`fpga`, `tb`, or `docs`.
**Severity:** `Critical` (wrong results / crash), `High` (breaks a feature),
`Medium` (workaround exists), `Low` (cosmetic, style, minor).
**Status:** `Open`, `In progress`, `Blocked`, `Fixed`.

<!--
---

## TEMPLATE BUG-XXX: <short title>

- **Component:** <e.g. periph/uart, sw/bsp, fpga>
- **Severity:** <Critical | High | Medium | Low>
- **Status:** <Open | In progress | Blocked | Fixed>
- **Reported by:** <name>, <YYYY-MM-DD>
- **Affects:** <commit/branch, or "all" if long-standing>

**Description**
What is wrong, in one or two sentences.

**Steps to reproduce**
1. ...
2. ...

**Expected behavior**
What should happen.

**Actual behavior**
What happens instead (include error output, waveform observation, or test
failure if relevant).

**Workaround**
How to avoid hitting it in the meantime, if any. Omit if none.

**Notes / root cause**
Any investigation so far — suspected cause, related modules, links to a
testbench run or `docs/*.md` section. Omit while unknown.

**Resolution** *(fill in when Status becomes Fixed)*
Fixed in <commit hash / PR>. Brief note on the actual fix.
-->

---

## BUG-CLOCK: SoC clock frequency on the board is not confirmed

- **Component:** fpga, sw
- **Severity:** High
- **Status:** Open
- **Reported by:** Ratko Pilipovic, 2026-11-14
- **Affects:** all

**Description**
`fpga/anvil/top.sv` feeds the board clock pin (E3) straight into the SoC, as HIPV
does. The XDC constrains that pin at 20 ns and `CPU_HZ` defaults to 50 MHz, but the
oscillator on the Nexys A7 is 100 MHz. Which frequency really reaches the SoC has
not been measured on a board for this design.

**Steps to reproduce**
1. Build and flash any UART example (`make APP=hello all`).
2. Open a terminal at 19200 8N1.

**Expected behavior**
Readable text at 19200 baud.

**Actual behavior**
Not tested yet. If the clock is 100 MHz the text is garbled at 19200 and readable
at 38400, and every software delay runs twice as fast.

**Workaround**
Build the software with the real frequency: `make CPU_HZ=100000000 ...`. Timing
analysis still uses the XDC period, so that also needs to match.

**Notes / root cause**
Three numbers must agree: the real clock, the XDC `create_clock` period and `CPU_HZ`
(`docs/FPGA.md`, "Clock frequency"). The clean fix under the coding rules is a
PLL/MMCM in `top.sv` producing the constrained frequency; whether F4PGA handles that
primitive has not been checked.

---

## TODO-IRQ: Add a CLINT and a global interrupt controller

- **Component:** periph, cpu, sw
- **Severity:** Low (enhancement, not a bug)
- **Status:** Open
- **Reported by:** Ratko Pilipovic, 2026-11-14
- **Affects:** all

**Description**
Interrupts work today without either module: the timer drives `timer_irq`
directly, `soft_irq` is tied to 0, and every external `Irq` line goes straight into
Hazard3's `irq` vector, where the lines are OR-ed into `mip.meip`. The BSP therefore
calls every attached external handler and each handler must check its own
peripheral. Planned: two APB slaves that replace this.

**Plan**
- **CLINT**: `MTIME` (64-bit free-running) and `MTIMECMP` drive `timer_irq`; `MSIP`
  drives `soft_irq` (new `SoftIrq` port on `cpu.sv`).
- **Global interrupt controller**: all peripheral `Irq` lines in, one line out to
  the core's `irq` (`NUM_IRQS` of the core becomes 1). Registers `PENDING`,
  `ENABLE` (per line) and `CLAIM` (lowest pending enabled line); the BSP then calls
  exactly the right handler.
- Touches: `svarog_soc_pkg.sv`, `svarog_soc.sv`, `cpu.sv`, the interrupt layer in
  `sw/bsp/`, `tb/soc`, `docs/INTERRUPTS.md`, `docs/ADDING_A_SLAVE.md` (step 4); unit
  testbenches for both new modules.

**Open decisions (the user's)**
1. CLINT register layout: the standard SiFive map (`MSIP` 0x0000, `MTIMECMP` 0x4000,
   `MTIME` 0xBFF8) needs a 64 KiB region and breaks the
   `0x2000_0000 + n * 0x1000` rule. Proposed: a compact 4 KiB layout with the same
   register names.
2. Does the CLINT replace `rtl/periph/timer.sv` or sit next to it? Proposed: replace
   it (one time source; the `timer_*` BSP functions read `MTIME`; the counter can no
   longer be stopped or cleared).
3. Controller complexity: proposed a simple one — no priorities, no
   claim/complete — since the lines are levels cleared by the peripheral. A full
   PLIC brings nothing for two or three sources.

**Notes**
The controller would be publicly visible in `rtl/periph/`. If lab V5 asks students
to build such a module, this would publish a solution — check against the V5
handout before implementing.

---

<!-- Copy the template for each new bug, replacing BUG-XXX with the next
     free number, and add a row to the Index table. -->
