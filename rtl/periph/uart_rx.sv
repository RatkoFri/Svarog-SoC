///////////////////////////////////////////////////////////////////////
// uart_rx
//
// Purpose: UART receiver, 8N1. Waits for a start bit, checks it is
//          still low half a bit later, then samples the eight data
//          bits (LSB first) and the stop bit in the middle of each
//          bit, Div clock cycles apart. Valid pulses for one clock
//          when a frame with a correct stop bit has been received;
//          Data holds the byte until the next frame completes.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module uart_rx (
  input  logic        clk, reset,
  input  logic [15:0] Div,      // clock cycles per bit
  input  logic        Rx,
  output logic [7:0]  Data,
  output logic        Valid);

  typedef enum logic [1:0] {IDLE, START, DATA, STOP} statetype;

  statetype    State;
  logic        RxMeta, RxSync;
  logic [15:0] BaudCount;
  logic [2:0]  BitCount;
  logic        HalfBit, FullBit;

  // CDC: Rx is asynchronous to clk, so it passes through a 2-FF
  // synchroniser. The reset value is the idle level of the line.
  always_ff @(posedge clk)
    if (reset) begin
      RxMeta <= 1'b1;
      RxSync <= 1'b1;
    end else begin
      RxMeta <= Rx;
      RxSync <= RxMeta;
    end

  assign HalfBit = (BaudCount == {1'b0, Div[15:1]});
  assign FullBit = (BaudCount == Div - 16'd1);

  always_ff @(posedge clk)
    if (reset) begin
      State     <= IDLE;
      BaudCount <= 16'd0;
      BitCount  <= 3'd0;
      Data      <= 8'd0;
      Valid     <= 1'b0;
    end else begin
      Valid     <= 1'b0;
      BaudCount <= BaudCount + 16'd1;
      case (State)
        IDLE: begin
          BaudCount <= 16'd0;
          if (~RxSync) State <= START;
        end
        START:                      // middle of the start bit
          if (HalfBit) begin
            BaudCount <= 16'd0;
            BitCount  <= 3'd0;
            State     <= RxSync ? IDLE : DATA;    // a glitch is dropped
          end
        DATA:                       // middle of each data bit
          if (FullBit) begin
            BaudCount <= 16'd0;
            Data      <= {RxSync, Data[7:1]};
            BitCount  <= BitCount + 3'd1;
            if (BitCount == 3'd7) State <= STOP;
          end
        default:                    // STOP: middle of the stop bit
          if (FullBit) begin
            Valid <= RxSync;        // framing error: frame is dropped
            State <= IDLE;
          end
      endcase
    end

endmodule
