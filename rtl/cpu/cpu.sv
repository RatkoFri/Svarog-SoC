///////////////////////////////////////////////////////////////////////
// cpu
//
// Purpose: SoC adapter for the Hazard3 RISC-V core
//          (rtl/cpu/hazard3, git submodule, github.com/Wren6991/Hazard3).
//          Interface changes only, the core is instantiated as-is:
//            - project port naming and active-high reset
//            - the single AHB-Lite master port, without the AHB5
//              signals the SoC does not use (burst, prot, lock,
//              master id, exclusive access)
//            - power-control handshakes tied back, debug and
//              system-bus-access ports tied off
//          The core is configured from svarog_soc_pkg: RV32I + Zicsr,
//          M-mode only, no PMP, no debug.
//          Reset: Hazard3 resets asynchronously on rst_n. It is driven
//          here from the SoC's synchronous reset, so assertion and
//          release are both aligned to clk.
//          Interrupts: Irq is OR-ed into mip.meip (mcause 11),
//          TimerIrq drives mip.mtip (mcause 7). Both are level
//          sensitive and active high.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module cpu
  import svarog_soc_pkg::*;
  (input  logic                clk, reset,
   // AHB-Lite master port
   output logic [31:0]         AhbAddr,
   output logic                AhbWrite,
   output logic [1:0]          AhbTrans,
   output logic [2:0]          AhbSize,
   output logic [31:0]         AhbWdata,
   input  logic [31:0]         AhbRdata,
   input  logic                AhbReady,
   input  logic                AhbResp,
   // interrupts
   input  logic [NUM_IRQS-1:0] Irq,
   input  logic                TimerIrq);

  // power-control handshakes, tied straight back
  logic PwrupReq, Unblock;

  // core outputs the SoC does not use
  /* verilator lint_off UNUSEDSIGNAL */
  logic        UnusedClkEn, UnusedLock, UnusedExcl;
  logic [2:0]  UnusedBurst;
  logic [3:0]  UnusedProt;
  logic [7:0]  UnusedMaster;
  logic        UnusedFenceI, UnusedFenceD;
  logic        UnusedHalted, UnusedRunning, UnusedData0Wen;
  logic [31:0] UnusedData0Wdata, UnusedSbusRdata;
  logic        UnusedInstrRdy, UnusedCaughtExc, UnusedCaughtEbreak;
  logic        UnusedSbusRdy, UnusedSbusErr;
  /* verilator lint_on UNUSEDSIGNAL */

  hazard3_cpu_1port #(
    .RESET_VECTOR(CPU_RESET_VECTOR),
    .MTVEC_INIT(CPU_MTVEC_INIT),
    .EXTENSION_A(CPU_EXTENSION_A),
    .EXTENSION_C(CPU_EXTENSION_C),
    .EXTENSION_M(CPU_EXTENSION_M),
    .CSR_M_MANDATORY(1),
    .CSR_M_TRAP(1),
    .CSR_COUNTER(CPU_CSR_COUNTER),
    .U_MODE(0),
    .PMP_REGIONS(0),
    .DEBUG_SUPPORT(CPU_DEBUG_SUPPORT),
    .NUM_IRQS(NUM_IRQS)) core(
    .clk(clk),
    .clk_always_on(clk),
    .rst_n(~reset),
    // power control
    .pwrup_req(PwrupReq),
    .pwrup_ack(PwrupReq),
    .clk_en(UnusedClkEn),
    .unblock_out(Unblock),
    .unblock_in(Unblock),
    // AHB master
    .haddr(AhbAddr),
    .hwrite(AhbWrite),
    .htrans(AhbTrans),
    .hsize(AhbSize),
    .hburst(UnusedBurst),
    .hprot(UnusedProt),
    .hmastlock(UnusedLock),
    .hmaster(UnusedMaster),
    .hexcl(UnusedExcl),
    .hready(AhbReady),
    .hresp(AhbResp),
    .hexokay(1'b1),
    .hwdata(AhbWdata),
    .hrdata(AhbRdata),
    // memory ordering
    .fence_i_vld(UnusedFenceI),
    .fence_d_vld(UnusedFenceD),
    .fence_rdy(1'b1),
    // debug (not used)
    .dbg_req_halt(1'b0),
    .dbg_req_halt_on_reset(1'b0),
    .dbg_req_resume(1'b0),
    .dbg_halted(UnusedHalted),
    .dbg_running(UnusedRunning),
    .dbg_data0_rdata(32'b0),
    .dbg_data0_wdata(UnusedData0Wdata),
    .dbg_data0_wen(UnusedData0Wen),
    .dbg_instr_data(32'b0),
    .dbg_instr_data_vld(1'b0),
    .dbg_instr_data_rdy(UnusedInstrRdy),
    .dbg_instr_caught_exception(UnusedCaughtExc),
    .dbg_instr_caught_ebreak(UnusedCaughtEbreak),
    .dbg_sbus_addr(32'b0),
    .dbg_sbus_write(1'b0),
    .dbg_sbus_size(2'b0),
    .dbg_sbus_vld(1'b0),
    .dbg_sbus_rdy(UnusedSbusRdy),
    .dbg_sbus_err(UnusedSbusErr),
    .dbg_sbus_wdata(32'b0),
    .dbg_sbus_rdata(UnusedSbusRdata),
    // identification
    .mhartid_val(32'b0),
    .eco_version(4'b0),
    // interrupts
    .irq(Irq),
    .soft_irq(1'b0),
    .timer_irq(TimerIrq));

endmodule
