# Labs

Lab handouts and templates for NDN. Nothing is here yet.

| Lab | Topic |
|-----|-------|
| V1–V2 | GPIO |
| V3 | 7-segment display |
| V4 | UART with FIFO |
| V5 | interrupts |
| V6 | SPI master + ADXL362 |

Rules for this folder:

- A template must compile and pass a minimal testbench before it is handed out.
  The V1 template ships with the APB interface already written.
- Student peripherals are separate modules with their own file names; they do not
  replace the reference peripherals in `rtl/periph/`. File names must be unique
  across the design (`docs/ADDING_A_SLAVE.md`).
- **No solutions here.** Solutions live in `solutions/`, which is git-ignored and
  never committed to the public repository.
