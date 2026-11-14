///////////////////////////////////////////////////////////////////////
// ahb_to_apb
//
// Purpose: Bridge from the CPU's AHB-Lite master port to the APB
//          peripheral bus. It is the only APB master in the SoC.
//          The APB side is the three-state machine from the lectures:
//            IDLE   : no transfer
//            SETUP  : ApbSel high, address/write/data valid (1 cycle)
//            ACCESS : ApbEnable high, held until ApbReady
//          An AHB address phase is captured when AhbReady is high and
//          AhbTrans[1] is set; the AHB data phase is then stretched
//          (AhbReady low) until the APB transfer completes. A new AHB
//          address phase can be accepted in the cycle a transfer
//          completes, so back-to-back transfers take two cycles each.
//          Errors: ApbSlvErr at the end of a transfer becomes the
//          two-cycle AHB error response (AhbResp high with AhbReady
//          low, then high) through the ERROR state.
//          ApbStrb carries the byte lanes of a write, derived from
//          AhbSize and the low address bits; it is zero for reads.
//          Only the RAM uses it — peripherals take whole 32-bit
//          registers. ApbAddr is word aligned.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module ahb_to_apb (
  input  logic        clk, reset,
  // AHB-Lite slave port (from the CPU)
  input  logic [31:0] AhbAddr,
  input  logic        AhbWrite,
  // AhbTrans[0] (SEQ) and AhbSize[2] never matter: single transfers
  // of at most 32 bits
  /* verilator lint_off UNUSEDSIGNAL */
  input  logic [1:0]  AhbTrans,
  input  logic [2:0]  AhbSize,
  /* verilator lint_on UNUSEDSIGNAL */
  input  logic [31:0] AhbWdata,
  output logic [31:0] AhbRdata,
  output logic        AhbReady,
  output logic        AhbResp,
  // APB master port
  output logic        ApbSel,
  output logic        ApbEnable,
  output logic        ApbWrite,
  output logic [31:0] ApbAddr,
  output logic [31:0] ApbWdata,
  output logic [3:0]  ApbStrb,
  input  logic [31:0] ApbRdata,
  input  logic        ApbReady,
  input  logic        ApbSlvErr);

  typedef enum logic [1:0] {IDLE, SETUP, ACCESS, ERROR} statetype;

  statetype    State, NextState;
  logic        Accept;      // AHB address phase accepted this cycle
  logic [29:0] AddrQ;       // captured word address
  logic        WriteQ;
  logic [3:0]  StrbQ, Strb;

  assign Accept = AhbReady & AhbTrans[1];

  // state register
  always_ff @(posedge clk)
    if (reset) State <= IDLE;
    else State <= NextState;

  // next state logic
  always_comb
    case (State)
      IDLE:    NextState = Accept ? SETUP : IDLE;
      SETUP:   NextState = ACCESS;
      ACCESS:  if (~ApbReady) NextState = ACCESS;
               else if (ApbSlvErr) NextState = ERROR;
               else NextState = Accept ? SETUP : IDLE;
      default: NextState = Accept ? SETUP : IDLE;   // ERROR
    endcase

  // byte lanes of the AHB transfer
  always_comb
    case (AhbSize[1:0])
      2'b00:   Strb = 4'b0001 << AhbAddr[1:0];
      2'b01:   Strb = AhbAddr[1] ? 4'b1100 : 4'b0011;
      default: Strb = 4'b1111;
    endcase

  // capture the AHB address phase
  always_ff @(posedge clk)
    if (Accept) begin
      AddrQ  <= AhbAddr[31:2];
      WriteQ <= AhbWrite;
      StrbQ  <= Strb;
    end

  // APB master outputs. AhbWdata is valid for the whole AHB data
  // phase, which spans SETUP and ACCESS, so it is passed straight on.
  assign ApbSel    = (State == SETUP) | (State == ACCESS);
  assign ApbEnable = (State == ACCESS);
  assign ApbWrite  = WriteQ;
  assign ApbAddr   = {AddrQ, 2'b00};
  assign ApbWdata  = AhbWdata;
  assign ApbStrb   = WriteQ ? StrbQ : 4'b0000;

  // AHB response
  assign AhbRdata = ApbRdata;
  assign AhbReady = (State == IDLE) | (State == ERROR) |
                    ((State == ACCESS) & ApbReady & ~ApbSlvErr);
  assign AhbResp  = (State == ERROR) |
                    ((State == ACCESS) & ApbReady & ApbSlvErr);

endmodule
