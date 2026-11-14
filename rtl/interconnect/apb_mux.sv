///////////////////////////////////////////////////////////////////////
// apb_mux
//
// Purpose: Return path of the Svarog APB bus: selects the read data,
//          ready and error of the addressed slave with the one-hot
//          PSEL from apb_decoder.
//          The slave side uses flattened packed vectors (the coding
//          standard does not allow arrays of signals as ports): slave
//          s occupies bit s / [s*32 +: 32].
//          A transfer that addresses no slave (DecErr) is completed
//          here with ApbReady and ApbSlvErr both high, so the CPU
//          takes an access fault instead of waiting forever.
//          Purely combinational.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module apb_mux
  import svarog_soc_pkg::*;
  (input  logic [NUM_SLAVES-1:0]    SlaveSel,
   input  logic                     DecErr,
   input  logic [NUM_SLAVES*32-1:0] SlaveRdata,
   input  logic [NUM_SLAVES-1:0]    SlaveReady, SlaveSlvErr,
   output logic [31:0]              ApbRdata,
   output logic                     ApbReady, ApbSlvErr);

  always_comb begin
    ApbRdata  = 32'b0;
    ApbReady  = DecErr;
    ApbSlvErr = DecErr;
    for (int unsigned i = 0; i < NUM_SLAVES; i++)
      if (SlaveSel[i]) begin
        ApbRdata  = SlaveRdata[i*32 +: 32];
        ApbReady  = SlaveReady[i];
        ApbSlvErr = SlaveSlvErr[i];
      end
  end

endmodule
