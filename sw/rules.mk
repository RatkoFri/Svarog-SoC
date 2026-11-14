# Shared build rules for Svarog software.
#
# An example Makefile sets PROG and SRCS, then includes this file:
#
#   PROG = hello
#   SRCS = main.c
#   include ../../rules.mk
#
# Products (in build/):
#   $(PROG).elf   linked ELF, for objdump/gdb
#   $(PROG).bin   flat image (objcopy -O binary)
#   $(PROG).hex   $readmemh image for the SoC INIT_FILE parameter
#   $(PROG).lst   disassembly listing
#
# The toolchain prefix defaults to the Debian/Ubuntu package name. Set
# CROSS to use another (e.g. riscv32-unknown-elf-, riscv-none-elf-).

SW_DIR     := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SVAROG_DIR := $(abspath $(SW_DIR)/..)

CROSS  ?= riscv64-unknown-elf-
CC      = $(CROSS)gcc
OBJCOPY = $(CROSS)objcopy
OBJDUMP = $(CROSS)objdump
SIZE    = $(CROSS)size

# RAM depth in 32-bit words; must match the SoC's RAM_ADDR_WIDTH
# (default 14 -> 16384 words -> 64 KiB).
RAM_WORDS ?= 16384

# Core clock and UART baud rate. Both are compiled into the program, and
# the simulation needs the resulting divider to decode the serial stream.
# CPU_HZ must be the frequency of the clock that really reaches the SoC
# (see docs/FPGA.md and BUG-CLOCK in KnownBugs.md).
CPU_HZ ?= 50000000
BAUD   ?= 19200

# SoC RAM depth, as the log2 word count the RTL parameter takes
RAM_ADDR_WIDTH ?= 14

# RV32I plus the CSR instructions the trap code needs. The link step
# names plain rv32i: that is the multilib directory toolchains ship
# libgcc in, and not every GCC maps rv32i_zicsr onto it by itself.
ARCH      = -march=rv32i_zicsr -mabi=ilp32
LINK_ARCH = -march=rv32i -mabi=ilp32
WARN    = -Wall -Wextra -Werror
OPT    ?= -Os

# Extra flags passed to every compiler/assembler/link step. Use it to
# point gcc at a toolchain installed outside its configured prefix, e.g.
#   make TOOLFLAGS=-B/opt/riscv/bin/
TOOLFLAGS ?=

# Extra preprocessor definitions for one build, e.g.
#   make DEFS=-DDELAY_CYCLES=2000
DEFS ?=

CFLAGS  = $(ARCH) $(TOOLFLAGS) $(WARN) $(OPT) -std=c11 \
          -ffreestanding -fno-builtin -nostdlib \
          -ffunction-sections -fdata-sections \
          -DCPU_HZ=$(CPU_HZ) -DBAUD=$(BAUD) $(DEFS) -I$(SW_DIR)/bsp
ASFLAGS = $(ARCH) $(TOOLFLAGS)
LDFLAGS = $(LINK_ARCH) $(TOOLFLAGS) -nostdlib -nostartfiles -Wl,--gc-sections \
          -T$(SW_DIR)/link.ld -Wl,-Map=$(BUILD)/$(PROG).map

# RV32I has no multiply or divide instructions, so the compiler emits
# calls to libgcc helpers (__udivsi3, __umodsi3, __mulsi3 ...). libgcc is
# linked even though the C library is not — it is part of the compiler,
# not of libc.
LDLIBS = -lgcc

BUILD  ?= build
BSP_SRCS = $(SW_DIR)/bsp/crt0.S $(SW_DIR)/bsp/bsp.c
OBJS     = $(addprefix $(BUILD)/,$(notdir $(patsubst %.c,%.o,$(patsubst %.S,%.o,$(SRCS) $(BSP_SRCS)))))

VPATH = $(SW_DIR)/bsp

.PHONY: all clean size dump run
all: $(BUILD)/$(PROG).hex $(BUILD)/$(PROG).lst

$(BUILD):
	@mkdir -p $(BUILD)

$(BUILD)/%.o: %.c | $(BUILD)
	$(CC) $(CFLAGS) -c -o $@ $<

$(BUILD)/%.o: %.S | $(BUILD)
	$(CC) $(ASFLAGS) -c -o $@ $<

$(BUILD)/$(PROG).elf: $(OBJS) $(SW_DIR)/link.ld
	$(CC) $(LDFLAGS) -o $@ $(OBJS) $(LDLIBS)

$(BUILD)/$(PROG).bin: $(BUILD)/$(PROG).elf
	$(OBJCOPY) -O binary $< $@

# The flat binary starts at address 0, which is word 0 of the RAM.
$(BUILD)/$(PROG).hex: $(BUILD)/$(PROG).bin
	python3 $(SVAROG_DIR)/scripts/mkmem.py --bin $< -o $@ --words $(RAM_WORDS)

$(BUILD)/$(PROG).lst: $(BUILD)/$(PROG).elf
	$(OBJDUMP) -d -S $< > $@

size: $(BUILD)/$(PROG).elf
	@$(SIZE) $<

dump: $(BUILD)/$(PROG).lst
	@cat $<

# Run this program on the SoC testbench and print what it sends over the
# UART. The run is a simulation, so it uses its own build directory and
# a fast baud rate (16 clocks per bit) unless SIM_BAUD says otherwise;
# SIM_DEFS adds definitions for the simulated image only (an example
# sets it to shorten its delays).
#   RUN_CYCLES  how long to simulate at most
#   a golden file expected.txt next to the program turns `make run`
#   into a regression: the run stops as soon as the output matches or
#   differs
SIM_BAUD    ?= $(shell echo $$(( $(CPU_HZ) / 16 )))
SIM_DEFS    ?=
SIM_BUILD   := $(BUILD)/sim
# clock cycles per UART bit, as uart_init() computes it
SIM_UART_DIV := $(shell echo $$(( $(CPU_HZ) / $(SIM_BAUD) )))
RUN_CYCLES  ?= 300000
EXPECT_FILE ?= $(wildcard expected.txt)
run:
	$(MAKE) BUILD=$(SIM_BUILD) BAUD=$(SIM_BAUD) DEFS='$(DEFS) $(SIM_DEFS)' all
	$(MAKE) -C $(SVAROG_DIR)/tb/soc \
	    MODULE=test_sw \
	    INIT_FILE=$(abspath $(SIM_BUILD)/$(PROG).hex) \
	    RAM_ADDR_WIDTH=$(RAM_ADDR_WIDTH) \
	    SIM_BUILD=$(abspath $(SIM_BUILD))/verilator \
	    COCOTB_RESULTS_FILE=$(abspath $(SIM_BUILD))/results.xml \
	    UART_DIV=$(SIM_UART_DIV) RUN_CYCLES=$(RUN_CYCLES) \
	    EXPECT_FILE=$(abspath $(EXPECT_FILE))

clean:
	rm -rf $(BUILD)
