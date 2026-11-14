///////////////////////////////////////////////////////////////////////
// svarog_soc
//
// Purpose: Svarog SoC top level. The Hazard3 core's AHB-Lite master
//          goes through the AHB-to-APB bridge onto one APB bus, where
//          the decoder selects one of the slaves: the RAM, the UART,
//          the timer and the GPIO. Everything, the RAM included, is an
//          APB slave.
//
//          The slave side of the bus uses flattened packed vectors
//          (the coding standard does not allow arrays of signals as
//          ports): slave s occupies bit s / [s*32 +: 32].
//          svarog_soc_pkg supplies the indices and the address map.
//
//          Interrupts: peripheral Irq lines go to the core's external
//          interrupt vector at the index given in svarog_soc_pkg; the
//          timer drives the machine timer interrupt.
//
//          ApbStrb (byte lanes of a write) is connected to the RAM
//          only; peripherals take whole 32-bit registers.
// Author:  Ratko Pilipovic
// Date:    14 November 2026
///////////////////////////////////////////////////////////////////////

module svarog_soc
  import svarog_soc_pkg::*;
  #(parameter RAM_ADDR_WIDTH = 14,       // words: 2^14 = 64 KiB
    parameter INIT_FILE      = "",       // $readmemh image, synthesis-time
    parameter GPIO_WIDTH     = 16)
  (input  logic                  clk, reset,
   // UART pins
   output logic                  Tx,
   input  logic                  Rx,
   // GPIO pins
   input  logic [GPIO_WIDTH-1:0] GpioIn,
   output logic [GPIO_WIDTH-1:0] GpioOut);

  // CPU AHB-Lite master
  logic [31:0] AhbAddr, AhbWdata, AhbRdata;
  logic [1:0]  AhbTrans;
  logic [2:0]  AhbSize;
  logic        AhbWrite, AhbReady, AhbResp;

  // APB, master side
  logic        ApbSel, ApbEnable, ApbWrite, ApbReady, ApbSlvErr;
  logic [31:0] ApbAddr, ApbWdata, ApbRdata;
  logic [3:0]  ApbStrb;
  logic        DecErr;

  // APB, slave side (flattened)
  logic [NUM_SLAVES-1:0]    SlaveSel, SlaveReady, SlaveSlvErr;
  logic [NUM_SLAVES*32-1:0] SlaveRdata;

  // interrupts
  logic [NUM_IRQS-1:0] Irq;
  logic                TimerIrq;

  // ---------------------------------------------------------------
  // CPU
  // ---------------------------------------------------------------
  cpu cpu(.clk(clk), .reset(reset),
          .AhbAddr(AhbAddr), .AhbWrite(AhbWrite), .AhbTrans(AhbTrans),
          .AhbSize(AhbSize), .AhbWdata(AhbWdata), .AhbRdata(AhbRdata),
          .AhbReady(AhbReady), .AhbResp(AhbResp),
          .Irq(Irq), .TimerIrq(TimerIrq));

  // ---------------------------------------------------------------
  // interconnect: bridge (the APB master), decoder, return mux
  // ---------------------------------------------------------------
  ahb_to_apb bridge(.clk(clk), .reset(reset),
                    .AhbAddr(AhbAddr), .AhbWrite(AhbWrite), .AhbTrans(AhbTrans),
                    .AhbSize(AhbSize), .AhbWdata(AhbWdata), .AhbRdata(AhbRdata),
                    .AhbReady(AhbReady), .AhbResp(AhbResp),
                    .ApbSel(ApbSel), .ApbEnable(ApbEnable), .ApbWrite(ApbWrite),
                    .ApbAddr(ApbAddr), .ApbWdata(ApbWdata), .ApbStrb(ApbStrb),
                    .ApbRdata(ApbRdata), .ApbReady(ApbReady),
                    .ApbSlvErr(ApbSlvErr));

  apb_decoder decoder(.ApbAddr(ApbAddr), .ApbSel(ApbSel),
                      .SlaveSel(SlaveSel), .DecErr(DecErr));

  apb_mux mux(.SlaveSel(SlaveSel), .DecErr(DecErr),
              .SlaveRdata(SlaveRdata), .SlaveReady(SlaveReady),
              .SlaveSlvErr(SlaveSlvErr),
              .ApbRdata(ApbRdata), .ApbReady(ApbReady), .ApbSlvErr(ApbSlvErr));

  // ---------------------------------------------------------------
  // memory
  // ---------------------------------------------------------------
  apb_ram #(.ADDR_WIDTH(RAM_ADDR_WIDTH), .INIT_FILE(INIT_FILE)) ram(
    .clk(clk),
    .ApbSel(SlaveSel[SLAVE_RAM]), .ApbEnable(ApbEnable), .ApbWrite(ApbWrite),
    .ApbAddr(ApbAddr), .ApbWdata(ApbWdata), .ApbStrb(ApbStrb),
    .ApbRdata(SlaveRdata[SLAVE_RAM*32 +: 32]),
    .ApbReady(SlaveReady[SLAVE_RAM]), .ApbSlvErr(SlaveSlvErr[SLAVE_RAM]));

  // ---------------------------------------------------------------
  // peripherals
  // ---------------------------------------------------------------
  uart uart(.clk(clk), .reset(reset),
            .ApbSel(SlaveSel[SLAVE_UART]), .ApbEnable(ApbEnable),
            .ApbWrite(ApbWrite), .ApbAddr(ApbAddr), .ApbWdata(ApbWdata),
            .ApbRdata(SlaveRdata[SLAVE_UART*32 +: 32]),
            .ApbReady(SlaveReady[SLAVE_UART]),
            .ApbSlvErr(SlaveSlvErr[SLAVE_UART]),
            .Tx(Tx), .Rx(Rx), .Irq(Irq[IRQ_UART]));

  timer timer(.clk(clk), .reset(reset),
              .ApbSel(SlaveSel[SLAVE_TIMER]), .ApbEnable(ApbEnable),
              .ApbWrite(ApbWrite), .ApbAddr(ApbAddr), .ApbWdata(ApbWdata),
              .ApbRdata(SlaveRdata[SLAVE_TIMER*32 +: 32]),
              .ApbReady(SlaveReady[SLAVE_TIMER]),
              .ApbSlvErr(SlaveSlvErr[SLAVE_TIMER]),
              .Irq(TimerIrq));

  gpio #(.WIDTH(GPIO_WIDTH)) gpio(
    .clk(clk), .reset(reset),
    .ApbSel(SlaveSel[SLAVE_GPIO]), .ApbEnable(ApbEnable),
    .ApbWrite(ApbWrite), .ApbAddr(ApbAddr), .ApbWdata(ApbWdata),
    .ApbRdata(SlaveRdata[SLAVE_GPIO*32 +: 32]),
    .ApbReady(SlaveReady[SLAVE_GPIO]), .ApbSlvErr(SlaveSlvErr[SLAVE_GPIO]),
    .GpioIn(GpioIn), .GpioOut(GpioOut));

endmodule
