///////////////////////////////////////////////////////////////////////
// core_tb
//
// Purpose: Testbench-only wrapper for the CPU subsystem: the Hazard3
//          adapter, the AHB-to-APB bridge and the APB RAM, with no
//          decoder and no peripherals. The RAM is the only slave, so
//          it is selected for every address. The two interrupt inputs
//          come out as ports for the testbench to drive.
//          Not synthesised.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module core_tb
  import svarog_soc_pkg::*;
  #(parameter RAM_ADDR_WIDTH = 14,
    parameter INIT_FILE      = "")
  (input  logic                clk, reset,
   input  logic [NUM_IRQS-1:0] Irq,
   input  logic                TimerIrq);

  logic [31:0] AhbAddr, AhbWdata, AhbRdata;
  logic [1:0]  AhbTrans;
  logic [2:0]  AhbSize;
  logic        AhbWrite, AhbReady, AhbResp;

  logic        ApbSel, ApbEnable, ApbWrite, ApbReady, ApbSlvErr;
  logic [31:0] ApbAddr, ApbWdata, ApbRdata;
  logic [3:0]  ApbStrb;

  cpu cpu(.clk(clk), .reset(reset),
          .AhbAddr(AhbAddr), .AhbWrite(AhbWrite), .AhbTrans(AhbTrans),
          .AhbSize(AhbSize), .AhbWdata(AhbWdata), .AhbRdata(AhbRdata),
          .AhbReady(AhbReady), .AhbResp(AhbResp),
          .Irq(Irq), .TimerIrq(TimerIrq));

  ahb_to_apb bridge(.clk(clk), .reset(reset),
                    .AhbAddr(AhbAddr), .AhbWrite(AhbWrite), .AhbTrans(AhbTrans),
                    .AhbSize(AhbSize), .AhbWdata(AhbWdata), .AhbRdata(AhbRdata),
                    .AhbReady(AhbReady), .AhbResp(AhbResp),
                    .ApbSel(ApbSel), .ApbEnable(ApbEnable), .ApbWrite(ApbWrite),
                    .ApbAddr(ApbAddr), .ApbWdata(ApbWdata), .ApbStrb(ApbStrb),
                    .ApbRdata(ApbRdata), .ApbReady(ApbReady),
                    .ApbSlvErr(ApbSlvErr));

  apb_ram #(.ADDR_WIDTH(RAM_ADDR_WIDTH), .INIT_FILE(INIT_FILE)) ram(
    .clk(clk),
    .ApbSel(ApbSel), .ApbEnable(ApbEnable), .ApbWrite(ApbWrite),
    .ApbAddr(ApbAddr), .ApbWdata(ApbWdata), .ApbStrb(ApbStrb),
    .ApbRdata(ApbRdata), .ApbReady(ApbReady), .ApbSlvErr(ApbSlvErr));

endmodule
