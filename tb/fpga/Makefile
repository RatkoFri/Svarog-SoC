TOPLEVEL_DIR := $(abspath ../..)

# The board wrapper runs the same C program as the SoC testbench
# (sw/tests/soctest), with the same fast simulation baud rate.
SW_DIR    := $(TOPLEVEL_DIR)/sw/tests/soctest
SW_BUILD  := build/sim
CPU_HZ    ?= 50000000
UART_DIV  ?= 16
INIT_FILE ?= $(SW_DIR)/$(SW_BUILD)/soctest.hex

TOPLEVEL = top
MODULE   = test_fpga_top

VERILOG_SOURCES = $(SOC_SOURCES) $(TOPLEVEL_DIR)/fpga/anvil/top.sv

COMPILE_ARGS += -GRAM_ADDR_WIDTH=14 -GINIT_FILE=\"$(INIT_FILE)\"

export UART_DIV

include $(TOPLEVEL_DIR)/tb/common/Makefile.include

EXTRA_ARGS += $(CPU_ARGS)

# rules after the include so cocotb's `all` stays the default goal
.PHONY: firmware
firmware:
	$(MAKE) -C $(SW_DIR) BUILD=$(SW_BUILD) CPU_HZ=$(CPU_HZ) \
	    BAUD=$$(( $(CPU_HZ) / $(UART_DIV) ))

$(SW_DIR)/$(SW_BUILD)/soctest.hex: firmware ;

$(SIM_BUILD)/Vtop.mk: $(INIT_FILE)
