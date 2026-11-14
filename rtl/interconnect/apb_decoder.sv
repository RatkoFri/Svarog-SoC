///////////////////////////////////////////////////////////////////////
// apb_decoder
//
// Purpose: Address decoder for the Svarog APB bus. Turns the bridge's
//          single select (a transfer is in progress) and the address
//          into a one-hot PSEL, one bit per slave, using the address
//          map in svarog_soc_pkg. DecErr is asserted when a transfer
//          addresses no mapped region; apb_mux then completes the
//          transfer with an error instead of hanging the bus.
//          Purely combinational.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

// The package import sits in the header so the port width can follow
// NUM_SLAVES: adding a slave to svarog_soc_pkg resizes SlaveSel here.
module apb_decoder
  import svarog_soc_pkg::*;
  (input  logic [31:0]           ApbAddr,
   input  logic                  ApbSel,
   output logic [NUM_SLAVES-1:0] SlaveSel,
   output logic                  DecErr);

  logic [NUM_SLAVES-1:0] Match;

  // A region is matched by comparing the address bits above the region
  // size, which is why regions must be power-of-two sized and aligned.
  function automatic logic in_region(input logic [31:0] A,
                                     input logic [31:0] Base,
                                     input logic [31:0] Size);
    return (A & ~(Size - 32'd1)) == Base;
  endfunction

  always_comb begin
    Match = '0;
    Match[SLAVE_RAM]   = in_region(ApbAddr, RAM_BASE, RAM_SIZE);
    Match[SLAVE_UART]  = in_region(ApbAddr, UART_BASE, UART_SIZE);
    Match[SLAVE_TIMER] = in_region(ApbAddr, TIMER_BASE, TIMER_SIZE);
    Match[SLAVE_GPIO]  = in_region(ApbAddr, GPIO_BASE, GPIO_SIZE);
  end

  assign SlaveSel = ApbSel ? Match : '0;
  assign DecErr   = ApbSel & ~|Match;

endmodule
