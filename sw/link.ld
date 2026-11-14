/*
 * link.ld — Svarog SoC linker script.
 *
 * The SoC has one RAM at address 0, behind an APB slave like every
 * other device. Code, constants, data and the stack all live in it:
 *
 *   0x0000_0000   .text      _start first (the reset vector), code
 *                 .rodata    constants
 *                 .data      initialised variables
 *                 .bss       zeroed by crt0
 *                 ...        free
 *   RAM top       stack, growing down
 *
 * The whole image is baked into the RAM at synthesis time ($readmemh,
 * see docs/MEMORY.md), so .data is linked where it runs and needs no
 * startup copy — crt0 only zeroes .bss.
 *
 * The size matches the default SoC configuration (RAM_ADDR_WIDTH = 14,
 * so 64 KiB). Change LENGTH if the SoC is built with a different RAM
 * size.
 */

OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
    RAM (rwx) : ORIGIN = 0x00000000, LENGTH = 64K
}

/* room kept free for the stack; the link fails if the image grows into it */
__stack_size = 2K;

SECTIONS
{
    .text : ALIGN(4)
    {
        KEEP(*(.text.init))          /* _start must come first */
        KEEP(*(.text.trap))
        *(.text .text.*)
        . = ALIGN(4);
        __text_end = .;
    } > RAM

    .rodata : ALIGN(4)
    {
        *(.rodata .rodata.*)
        *(.srodata .srodata.*)
        . = ALIGN(4);
    } > RAM

    .data : ALIGN(4)
    {
        __data_start = .;
        *(.data .data.*)
        __sdata_start = .;
        *(.sdata .sdata.*)
        . = ALIGN(4);
        __data_end = .;
    } > RAM

    /* gp addresses the small-data area with signed 12-bit offsets */
    __global_pointer$ = __sdata_start + 0x800;

    .bss (NOLOAD) : ALIGN(4)
    {
        __bss_start = .;
        *(.sbss .sbss.*)
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(4);
        __bss_end = .;
    } > RAM

    /* stack grows down from the top of the RAM */
    __stack_top = ORIGIN(RAM) + LENGTH(RAM);
    __heap_start = __bss_end;

    /DISCARD/ : { *(.comment) *(.note.*) *(.eh_frame) }
}

ASSERT(__bss_end + __stack_size <= __stack_top,
       "program does not fit in the RAM (no room left for the stack)")
