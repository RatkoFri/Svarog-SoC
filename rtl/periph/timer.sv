///////////////////////////////////////////////////////////////////////
// timer
//
// Purpose: Reference timer of the Svarog SoC: a 64-bit up counter with
//          a 64-bit compare, the machine timer interrupt source. APB
//          slave, zero wait states, no error reporting. Registers are
//          whole words (ApbStrb is not used).
//          Register map (byte offsets):
//            0x00 CTRL      RW  reset 0
//                   bit0 ENABLE  count on every clock
//                   bit1 CLEAR   write 1 zeroes the counter; reads 0
//                   bit2 IRQ_EN  enable the interrupt output
//            0x04 COUNT_LO  RO  reset 0
//            0x08 COUNT_HI  RO  reset 0
//            0x0C CMP_LO    RW  reset 0xFFFF_FFFF
//            0x10 CMP_HI    RW  reset 0xFFFF_FFFF
//          Unmapped offsets read as zero and ignore writes.
//          Irq is a level: IRQ_EN & (COUNT >= CMP), registered, so it
//          follows a register write one clock later. It is cleared by
//          writing a compare value above the counter, by CLEAR, or by
//          dropping IRQ_EN — the same idea as mtime / mtimecmp.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module timer (
  input  logic        clk, reset,
  // APB slave port
  input  logic        ApbSel, ApbEnable, ApbWrite,
  // only the register offset is used
  /* verilator lint_off UNUSEDSIGNAL */
  input  logic [31:0] ApbAddr,
  /* verilator lint_on UNUSEDSIGNAL */
  input  logic [31:0] ApbWdata,
  output logic [31:0] ApbRdata,
  output logic        ApbReady, ApbSlvErr,
  // interrupt (level, to the CPU's timer_irq)
  output logic        Irq);

  localparam logic [9:0] CTRL_OFFSET     = 10'd0;   // 0x00
  localparam logic [9:0] COUNT_LO_OFFSET = 10'd1;   // 0x04
  localparam logic [9:0] COUNT_HI_OFFSET = 10'd2;   // 0x08
  localparam logic [9:0] CMP_LO_OFFSET   = 10'd3;   // 0x0C
  localparam logic [9:0] CMP_HI_OFFSET   = 10'd4;   // 0x10

  logic [63:0] Count, Cmp;
  logic        Enable, IrqEn;
  logic        WriteEn, CtrlWrite, Clear;

  // registers are written in the access phase
  assign WriteEn   = ApbSel & ApbEnable & ApbWrite;
  assign CtrlWrite = WriteEn & (ApbAddr[11:2] == CTRL_OFFSET);
  assign Clear     = CtrlWrite & ApbWdata[1];

  // control and compare registers
  always_ff @(posedge clk)
    if (reset) begin
      Enable <= 1'b0;
      IrqEn  <= 1'b0;
      Cmp    <= '1;
    end else if (WriteEn)
      case (ApbAddr[11:2])
        CTRL_OFFSET: begin
          Enable <= ApbWdata[0];
          IrqEn  <= ApbWdata[2];
        end
        CMP_LO_OFFSET: Cmp[31:0]  <= ApbWdata;
        CMP_HI_OFFSET: Cmp[63:32] <= ApbWdata;
        default: ;
      endcase

  // counter
  always_ff @(posedge clk)
    if (reset | Clear) Count <= 64'b0;
    else if (Enable) Count <= Count + 64'd1;

  // interrupt, registered to keep the 64-bit compare off the CPU path
  always_ff @(posedge clk)
    if (reset) Irq <= 1'b0;
    else Irq <= IrqEn & (Count >= Cmp);

  // read mux
  always_comb
    case (ApbAddr[11:2])
      CTRL_OFFSET:     ApbRdata = {29'b0, IrqEn, 1'b0, Enable};
      COUNT_LO_OFFSET: ApbRdata = Count[31:0];
      COUNT_HI_OFFSET: ApbRdata = Count[63:32];
      CMP_LO_OFFSET:   ApbRdata = Cmp[31:0];
      CMP_HI_OFFSET:   ApbRdata = Cmp[63:32];
      default:         ApbRdata = 32'b0;
    endcase

  assign ApbReady  = 1'b1;
  assign ApbSlvErr = 1'b0;

endmodule
