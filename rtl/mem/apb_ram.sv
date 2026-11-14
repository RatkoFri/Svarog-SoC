///////////////////////////////////////////////////////////////////////
// apb_ram
//
// Purpose: The SoC memory: one single-port synchronous RAM behind an
//          APB slave port. Code, data and stack all live here.
//          ADDR_WIDTH is the depth in 32-bit words (default 2^14 =
//          64 KiB). INIT_FILE is a $readmemh image of 32-bit words
//          applied at elaboration — synthesis-time initialization,
//          folded into the FPGA bitstream (built with scripts/mkmem.py).
//          Timing, zero wait states (ApbReady tied high):
//            SETUP  : the RAM reads the addressed word
//            ACCESS : read  — the word is on ApbRdata
//                     write — the bytes selected by ApbStrb are merged
//                             into the word just read and written back
//          The read-modify-write gives byte and halfword stores
//          without byte write enables in the RAM primitive.
//          This is the only slave that uses ApbStrb.
//          Addresses beyond the RAM depth wrap (only the low address
//          bits are used).
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module apb_ram #(parameter ADDR_WIDTH = 14,      // words: 2^14 = 64 KiB
                 parameter INIT_FILE  = "") (
  input  logic        clk,
  // APB slave port
  input  logic        ApbSel, ApbEnable, ApbWrite,
  // only the word-index bits are used; the bits above the RAM depth
  // and the byte offset are legitimately ignored
  /* verilator lint_off UNUSEDSIGNAL */
  input  logic [31:0] ApbAddr,
  /* verilator lint_on UNUSEDSIGNAL */
  input  logic [31:0] ApbWdata,
  input  logic [3:0]  ApbStrb,
  output logic [31:0] ApbRdata,
  output logic        ApbReady, ApbSlvErr);

  logic [31:0] RamRdata, RamWdata, StrbMask;
  logic        RamWe;

  assign StrbMask = {{8{ApbStrb[3]}}, {8{ApbStrb[2]}}, {8{ApbStrb[1]}}, {8{ApbStrb[0]}}};

  // write in the access phase, merging into the word read in setup
  assign RamWe    = ApbSel & ApbEnable & ApbWrite;
  assign RamWdata = (RamRdata & ~StrbMask) | (ApbWdata & StrbMask);

  sync_single_port_RAM #(.DATA_WIDTH(32), .ADDR_WIDTH(ADDR_WIDTH),
                         .INIT_FILE(INIT_FILE)) ram(
    .clock(clk),
    .addr_a(ApbAddr[ADDR_WIDTH+1:2]), .datain_a(RamWdata), .we_a(RamWe),
    .dataout_a(RamRdata));

  assign ApbRdata  = RamRdata;
  assign ApbReady  = 1'b1;
  assign ApbSlvErr = 1'b0;

endmodule
