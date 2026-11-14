///////////////////////////////////////////////////////////////////////
// interconnect_tb
//
// Purpose: Testbench-only wrapper that joins the three interconnect
//          modules exactly as svarog_soc does — bridge, decoder and
//          return mux — and leaves the slave side open, so the
//          testbench can stand in for every slave. Not synthesised.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module interconnect_tb
  import svarog_soc_pkg::*;
  (input  logic                     clk, reset,
   // AHB-Lite slave port (the testbench plays the CPU)
   input  logic [31:0]              AhbAddr,
   input  logic                     AhbWrite,
   input  logic [1:0]               AhbTrans,
   input  logic [2:0]               AhbSize,
   input  logic [31:0]              AhbWdata,
   output logic [31:0]              AhbRdata,
   output logic                     AhbReady,
   output logic                     AhbResp,
   // APB, shared signals to every slave
   output logic                     ApbEnable, ApbWrite,
   output logic [31:0]              ApbAddr, ApbWdata,
   output logic [3:0]               ApbStrb,
   // APB, per slave (flattened)
   output logic [NUM_SLAVES-1:0]    SlaveSel,
   input  logic [NUM_SLAVES*32-1:0] SlaveRdata,
   input  logic [NUM_SLAVES-1:0]    SlaveReady, SlaveSlvErr);

  logic        ApbSel, ApbReady, ApbSlvErr, DecErr;
  logic [31:0] ApbRdata;

  ahb_to_apb bridge(.clk(clk), .reset(reset),
                    .AhbAddr(AhbAddr), .AhbWrite(AhbWrite), .AhbTrans(AhbTrans),
                    .AhbSize(AhbSize), .AhbWdata(AhbWdata), .AhbRdata(AhbRdata),
                    .AhbReady(AhbReady), .AhbResp(AhbResp),
                    .ApbSel(ApbSel), .ApbEnable(ApbEnable), .ApbWrite(ApbWrite),
                    .ApbAddr(ApbAddr), .ApbWdata(ApbWdata), .ApbStrb(ApbStrb),
                    .ApbRdata(ApbRdata), .ApbReady(ApbReady),
                    .ApbSlvErr(ApbSlvErr));

  apb_decoder decoder(.ApbAddr(ApbAddr), .ApbSel(ApbSel),
                      .SlaveSel(SlaveSel), .DecErr(DecErr));

  apb_mux mux(.SlaveSel(SlaveSel), .DecErr(DecErr),
              .SlaveRdata(SlaveRdata), .SlaveReady(SlaveReady),
              .SlaveSlvErr(SlaveSlvErr),
              .ApbRdata(ApbRdata), .ApbReady(ApbReady), .ApbSlvErr(ApbSlvErr));

endmodule
