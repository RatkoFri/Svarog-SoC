///////////////////////////////////////////////////////////////////////
// top
//
// Purpose: FPGA wrapper for the Svarog SoC on the Digilent Nexys
//          A7-100T, built with Anvil (F4PGA). Board plumbing only — no
//          design logic lives here:
//            - the board clock drives the SoC directly (see the clock
//              constraint in the XDC; software uses CPU_HZ)
//            - converts the active-low CPU_RESETN button to the SoC's
//              synchronous active-high reset, through a synchroniser,
//              plus a power-on reset so the SoC starts without the
//              button being pressed
//            - maps GPIO to the 16 LEDs and 16 slide switches
//            - maps the UART to the USB-serial bridge
//
//          Deliberately free of package imports and type parameters:
//          Anvil converts project sources with sv2v, and this file is
//          kept simple enough to survive any conversion path.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module top #(parameter RAM_ADDR_WIDTH = 14,          // 2^14 words = 64 KiB
             parameter INIT_FILE      = "firmware.hex")
           (input  logic        clk,          // SoC clock (see XDC)
            input  logic        cpu_resetn,   // active-low push button
            output logic        uart_tx,      // to the USB-serial RXD
            input  logic        uart_rx,      // from the USB-serial TXD
            input  logic [15:0] sw,           // slide switches -> GPIO in
            output logic [15:0] led);         // LEDs <- GPIO out

  // ---------------------------------------------------------------
  // reset: active-low button -> synchronous active-high reset
  //
  // CDC: the button is asynchronous to clk; two flops synchronise it.
  // The SoC resets synchronously, so the clock must be running while
  // reset is asserted — always true here, the board clock free-runs.
  //
  // PorCount additionally holds reset for the first 15 clocks after
  // configuration, so the SoC starts cleanly even if the button is
  // never pressed. SocReset is registered: the Hazard3 core uses it as
  // an asynchronous reset, so it must be glitch free.
  // ---------------------------------------------------------------
  logic       ResetSyncQ, ResetSync;
  logic [3:0] PorCount;
  logic       PorReset;
  logic       SocReset;

  initial begin
    PorCount   = 4'd0;
    ResetSyncQ = 1'b1;
    ResetSync  = 1'b1;
    SocReset   = 1'b1;
  end

  always_ff @(posedge clk) begin
    ResetSyncQ <= ~cpu_resetn;   // button pressed = reset requested
    ResetSync  <= ResetSyncQ;
  end

  always_ff @(posedge clk)
    if (PorCount != 4'hF) PorCount <= PorCount + 4'd1;

  assign PorReset = (PorCount != 4'hF);

  always_ff @(posedge clk)
    SocReset <= ResetSync | PorReset;

  // ---------------------------------------------------------------
  // the SoC
  //
  // INIT_FILE is resolved by the synthesiser relative to the directory
  // the build runs in, so firmware.hex sits in the project root. Build
  // it from sw/ — see docs/FPGA.md.
  // ---------------------------------------------------------------
  svarog_soc #(.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),
               .INIT_FILE(INIT_FILE),
               .GPIO_WIDTH(16))
    soc(.clk(clk), .reset(SocReset),
        .Tx(uart_tx), .Rx(uart_rx),
        .GpioIn(sw), .GpioOut(led));

endmodule
