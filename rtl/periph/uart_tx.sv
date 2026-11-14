///////////////////////////////////////////////////////////////////////
// uart_tx
//
// Purpose: UART transmitter, 8N1. Start loads Data and sends one
//          frame: start bit, eight data bits LSB first, stop bit, each
//          Div clock cycles long. Busy is high while a frame is on the
//          line; Start is ignored while Busy.
//          The frame sits in a 10-bit shift register whose bit 0 is
//          the Tx pin, so Tx comes straight from a flip-flop.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module uart_tx (
  input  logic        clk, reset,
  input  logic [15:0] Div,      // clock cycles per bit
  input  logic        Start,
  input  logic [7:0]  Data,
  output logic        Tx,
  output logic        Busy);

  logic [9:0]  Shift;       // {stop, data[7:0], start}, shifted right
  logic [3:0]  BitCount;
  logic [15:0] BaudCount;
  logic        BitDone;

  assign BitDone = (BaudCount == Div - 16'd1);

  always_ff @(posedge clk)
    if (reset) begin
      Shift     <= '1;          // line idles high
      BitCount  <= 4'd0;
      BaudCount <= 16'd0;
      Busy      <= 1'b0;
    end else if (~Busy) begin
      if (Start) begin
        Shift     <= {1'b1, Data, 1'b0};
        BitCount  <= 4'd0;
        BaudCount <= 16'd0;
        Busy      <= 1'b1;
      end
    end else if (BitDone) begin
      BaudCount <= 16'd0;
      Shift     <= {1'b1, Shift[9:1]};
      BitCount  <= BitCount + 4'd1;
      if (BitCount == 4'd9) Busy <= 1'b0;
    end else
      BaudCount <= BaudCount + 16'd1;

  assign Tx = Shift[0];

endmodule
