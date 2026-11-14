/*
 * crt0.S — Svarog startup code and trap entry.
 *
 * _start runs from the reset vector at address 0: it points mtvec at
 * trap_entry, sets up gp and sp, zeroes .bss and calls main.
 *
 * There is no .data copy loop: the whole image, initialised data
 * included, is baked into the RAM at synthesis time, so .data is
 * already in place (see sw/link.ld).
 *
 * trap_entry is where the CPU goes for every interrupt and exception
 * (mtvec, direct mode). It saves the registers a C function may
 * clobber, calls trap_handler(mcause, mepc, mtval) in bsp.c, restores
 * them and returns with mret.
 */

    .section .text.init, "ax"
    .global _start
    .type _start, @function

_start:
    /* all traps go to trap_entry; interrupts stay off until the
     * program calls irq_enable() */
    la      t0, trap_entry
    csrw    mtvec, t0
    csrw    mie, zero

    /* set up the stack and global pointer */
    .option push
    .option norelax
    la      gp, __global_pointer$
    .option pop
    la      sp, __stack_top

    /* zero .bss */
    la      t0, __bss_start
    la      t1, __bss_end
1:  bgeu    t0, t1, 2f
    sw      zero, 0(t0)
    addi    t0, t0, 4
    j       1b
2:

    /* argc = 0, argv = NULL */
    li      a0, 0
    li      a1, 0
    call    main

    /* main returned: park in a spin loop with the return code in a0 */
    .global _exit
_exit:
3:  j       3b

    .size _start, . - _start

/* ------------------------------------------------------------------ */
/* trap entry: mtvec must be 4-byte aligned                            */
/* ------------------------------------------------------------------ */
    .section .text.trap, "ax"
    .balign 4
    .global trap_entry
    .type trap_entry, @function

trap_entry:
    /* save the caller-saved registers (the C handler preserves the
     * callee-saved ones itself) */
    addi    sp, sp, -64
    sw      ra,  0(sp)
    sw      t0,  4(sp)
    sw      t1,  8(sp)
    sw      t2, 12(sp)
    sw      a0, 16(sp)
    sw      a1, 20(sp)
    sw      a2, 24(sp)
    sw      a3, 28(sp)
    sw      a4, 32(sp)
    sw      a5, 36(sp)
    sw      a6, 40(sp)
    sw      a7, 44(sp)
    sw      t3, 48(sp)
    sw      t4, 52(sp)
    sw      t5, 56(sp)
    sw      t6, 60(sp)

    csrr    a0, mcause
    csrr    a1, mepc
    csrr    a2, mtval
    call    trap_handler

    lw      ra,  0(sp)
    lw      t0,  4(sp)
    lw      t1,  8(sp)
    lw      t2, 12(sp)
    lw      a0, 16(sp)
    lw      a1, 20(sp)
    lw      a2, 24(sp)
    lw      a3, 28(sp)
    lw      a4, 32(sp)
    lw      a5, 36(sp)
    lw      a6, 40(sp)
    lw      a7, 44(sp)
    lw      t3, 48(sp)
    lw      t4, 52(sp)
    lw      t5, 56(sp)
    lw      t6, 60(sp)
    addi    sp, sp, 64
    mret

    .size trap_entry, . - trap_entry
