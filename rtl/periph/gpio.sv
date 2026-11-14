///////////////////////////////////////////////////////////////////////
// gpio
//
// Purpose: Reference GPIO of the Svarog SoC: WIDTH output pins and
//          WIDTH input pins. APB slave, zero wait states, no error
//          reporting. Registers are whole words (ApbStrb is not used).
//          Register map (byte offsets):
//            0x00 OUT  RW  reset 0  drives GpioOut, reads back
//            0x04 IN   RO           GpioIn after a 2-FF synchroniser
//          Unmapped offsets read as zero and ignore writes.
//          No interrupt output.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module gpio #(parameter WIDTH = 16) (
  input  logic             clk, reset,
  // APB slave port
  input  logic             ApbSel, ApbEnable, ApbWrite,
  // only the register offset and the low WIDTH data bits are used
  /* verilator lint_off UNUSEDSIGNAL */
  input  logic [31:0]      ApbAddr,
  input  logic [31:0]      ApbWdata,
  /* verilator lint_on UNUSEDSIGNAL */
  output logic [31:0]      ApbRdata,
  output logic             ApbReady, ApbSlvErr,
  // pins
  input  logic [WIDTH-1:0] GpioIn,
  output logic [WIDTH-1:0] GpioOut);

  localparam logic [9:0] OUT_OFFSET = 10'd0;   // 0x00
  localparam logic [9:0] IN_OFFSET  = 10'd1;   // 0x04

  logic [WIDTH-1:0] InMeta, InSync;
  logic             WriteEn;

  // registers are written in the access phase
  assign WriteEn = ApbSel & ApbEnable & ApbWrite;

  always_ff @(posedge clk)
    if (reset) GpioOut <= '0;
    else if (WriteEn & (ApbAddr[11:2] == OUT_OFFSET)) GpioOut <= ApbWdata[WIDTH-1:0];

  // CDC: the pins are asynchronous to clk (switches, buttons), so they
  // pass through a 2-FF synchroniser before software can read them
  always_ff @(posedge clk) begin
    InMeta <= GpioIn;
    InSync <= InMeta;
  end

  // read mux
  always_comb begin
    ApbRdata = 32'b0;
    case (ApbAddr[11:2])
      OUT_OFFSET: ApbRdata[WIDTH-1:0] = GpioOut;
      IN_OFFSET:  ApbRdata[WIDTH-1:0] = InSync;
      default:    ApbRdata = 32'b0;
    endcase
  end

  assign ApbReady  = 1'b1;
  assign ApbSlvErr = 1'b0;

endmodule
