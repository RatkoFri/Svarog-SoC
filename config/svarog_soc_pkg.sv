///////////////////////////////////////////////////////////////////////
// svarog_soc_pkg
//
// Purpose: SoC-level constants for Svarog: APB slave indices, the
//          address map, the interrupt assignment and the Hazard3
//          configuration. Imported by the interconnect, the CPU
//          adapter and the SoC top level so they all agree.
//          sw/bsp/svarog.h and tb/common/socmap.py mirror this file —
//          keep the three in step.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

// not every unit uses every constant; that is fine for a shared package
/* verilator lint_off UNUSEDPARAM */
package svarog_soc_pkg;

  // APB slaves
  localparam int unsigned NUM_SLAVES  = 4;
  localparam int unsigned SLAVE_RAM   = 0;
  localparam int unsigned SLAVE_UART  = 1;
  localparam int unsigned SLAVE_TIMER = 2;
  localparam int unsigned SLAVE_GPIO  = 3;

  // address map: BASE is the first address, SIZE the region size in
  // bytes. Regions must be power-of-two sized and naturally aligned so
  // the decoder can compare the upper address bits only.
  // Peripherals live at 0x2000_0000 + n * 0x1000.
  localparam logic [31:0] RAM_BASE   = 32'h0000_0000;
  localparam logic [31:0] RAM_SIZE   = 32'h0001_0000;  // 64 KiB
  localparam logic [31:0] UART_BASE  = 32'h2000_0000;
  localparam logic [31:0] UART_SIZE  = 32'h0000_1000;  // 4 KiB
  localparam logic [31:0] TIMER_BASE = 32'h2000_1000;
  localparam logic [31:0] TIMER_SIZE = 32'h0000_1000;  // 4 KiB
  localparam logic [31:0] GPIO_BASE  = 32'h2000_2000;
  localparam logic [31:0] GPIO_SIZE  = 32'h0000_1000;  // 4 KiB

  // interrupts
  // External interrupt lines into Hazard3's irq vector. They are OR-ed
  // into mip.meip (mcause 11). The timer has its own line, timer_irq
  // (mip.mtip, mcause 7), and is therefore not listed here.
  localparam int unsigned NUM_IRQS = 1;
  localparam int unsigned IRQ_UART = 0;

  // Hazard3 configuration (see rtl/cpu/hazard3/hdl/hazard3_config.vh).
  // RV32I + Zicsr, M-mode only, no PMP, no debug.
  localparam logic [31:0] CPU_RESET_VECTOR  = 32'h0000_0000;
  localparam logic [31:0] CPU_MTVEC_INIT    = 32'h0000_0000;
  localparam int unsigned CPU_EXTENSION_A   = 0;
  localparam int unsigned CPU_EXTENSION_C   = 0;
  localparam int unsigned CPU_EXTENSION_M   = 0;
  localparam int unsigned CPU_CSR_COUNTER   = 0;
  localparam int unsigned CPU_DEBUG_SUPPORT = 0;

endpackage
/* verilator lint_on UNUSEDPARAM */
