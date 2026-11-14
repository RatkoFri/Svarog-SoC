///////////////////////////////////////////////////////////////////////
// uart
//
// Purpose: Reference UART of the Svarog SoC: 8N1, programmable baud
//          divider, one-byte transmit and receive buffers (no FIFO),
//          level interrupt. APB slave, zero wait states, no error
//          reporting. Registers are whole words (ApbStrb is not used).
//          Register map (byte offsets):
//            0x00 CTRL    RW  reset 0
//                   bit0 RX_IRQ_EN  interrupt while RX_AVAIL
//                   bit1 TX_IRQ_EN  interrupt while TX_EMPTY
//            0x04 DIV     RW  reset 0   clock cycles per bit, 16 bits
//            0x08 TX      WO            write sends the low byte;
//                                       ignored while a frame is on
//                                       the line; reads 0
//            0x0C RX      RO            last received byte; the read
//                                       clears RX_AVAIL and RX_OVERRUN
//            0x10 STATUS  RO
//                   bit0 TX_EMPTY    transmitter idle (reset 1)
//                   bit1 RX_AVAIL    a byte is waiting in RX
//                   bit2 RX_OVERRUN  a byte arrived while RX_AVAIL;
//                                    the older byte was overwritten
//          Unmapped offsets read as zero and ignore writes.
//          Irq is a level: (RX_IRQ_EN & RX_AVAIL) |
//          (TX_IRQ_EN & TX_EMPTY). The receive interrupt is cleared by
//          reading RX, the transmit interrupt by writing TX or by
//          dropping TX_IRQ_EN.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module uart (
  input  logic        clk, reset,
  // APB slave port
  input  logic        ApbSel, ApbEnable, ApbWrite,
  // only the register offset and the low data bits are used
  /* verilator lint_off UNUSEDSIGNAL */
  input  logic [31:0] ApbAddr,
  input  logic [31:0] ApbWdata,
  /* verilator lint_on UNUSEDSIGNAL */
  output logic [31:0] ApbRdata,
  output logic        ApbReady, ApbSlvErr,
  // serial pins
  output logic        Tx,
  input  logic        Rx,
  // interrupt (level)
  output logic        Irq);

  localparam logic [9:0] CTRL_OFFSET   = 10'd0;   // 0x00
  localparam logic [9:0] DIV_OFFSET    = 10'd1;   // 0x04
  localparam logic [9:0] TX_OFFSET     = 10'd2;   // 0x08
  localparam logic [9:0] RX_OFFSET     = 10'd3;   // 0x0C
  localparam logic [9:0] STATUS_OFFSET = 10'd4;   // 0x10

  logic        RxIrqEn, TxIrqEn;
  logic [15:0] Div;
  logic [7:0]  RxData, RxByte;
  logic        RxValid, RxAvail, RxOverrun;
  logic        TxBusy, TxStart;
  logic        WriteEn, ReadEn, RxRead;

  // registers are accessed in the access phase; ApbReady is tied high,
  // so the access phase lasts exactly one clock
  assign WriteEn = ApbSel & ApbEnable & ApbWrite;
  assign ReadEn  = ApbSel & ApbEnable & ~ApbWrite;
  assign TxStart = WriteEn & (ApbAddr[11:2] == TX_OFFSET);
  assign RxRead  = ReadEn & (ApbAddr[11:2] == RX_OFFSET);

  // control and divider registers
  always_ff @(posedge clk)
    if (reset) begin
      RxIrqEn <= 1'b0;
      TxIrqEn <= 1'b0;
      Div     <= 16'd0;
    end else if (WriteEn)
      case (ApbAddr[11:2])
        CTRL_OFFSET: begin
          RxIrqEn <= ApbWdata[0];
          TxIrqEn <= ApbWdata[1];
        end
        DIV_OFFSET: Div <= ApbWdata[15:0];
        default: ;
      endcase

  uart_tx tx(.clk(clk), .reset(reset), .Div(Div), .Start(TxStart),
             .Data(ApbWdata[7:0]), .Tx(Tx), .Busy(TxBusy));

  uart_rx rx(.clk(clk), .reset(reset), .Div(Div), .Rx(Rx),
             .Data(RxByte), .Valid(RxValid));

  // one-byte receive buffer with its flags; a new byte wins over a
  // read in the same clock
  always_ff @(posedge clk)
    if (reset) begin
      RxData    <= 8'd0;
      RxAvail   <= 1'b0;
      RxOverrun <= 1'b0;
    end else if (RxValid) begin
      RxData    <= RxByte;
      RxAvail   <= 1'b1;
      RxOverrun <= RxAvail & ~RxRead;
    end else if (RxRead) begin
      RxAvail   <= 1'b0;
      RxOverrun <= 1'b0;
    end

  // read mux
  always_comb
    case (ApbAddr[11:2])
      CTRL_OFFSET:   ApbRdata = {30'b0, TxIrqEn, RxIrqEn};
      DIV_OFFSET:    ApbRdata = {16'b0, Div};
      RX_OFFSET:     ApbRdata = {24'b0, RxData};
      STATUS_OFFSET: ApbRdata = {29'b0, RxOverrun, RxAvail, ~TxBusy};
      default:       ApbRdata = 32'b0;
    endcase

  assign ApbReady  = 1'b1;
  assign ApbSlvErr = 1'b0;

  assign Irq = (RxIrqEn & RxAvail) | (TxIrqEn & ~TxBusy);

endmodule
