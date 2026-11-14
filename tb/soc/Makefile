TOPLEVEL_DIR := $(abspath ../..)

# The SoC runs a real C program, built from sw/tests/soctest and applied
# at elaboration through INIT_FILE — the same synthesis-time
# initialization the FPGA flow uses. The simulated image uses a fast
# baud rate (UART_DIV clocks per bit) so a run stays short.
SW_DIR    := $(TOPLEVEL_DIR)/sw/tests/soctest
SW_BUILD  := build/sim
CPU_HZ    ?= 50000000
UART_DIV  ?= 16
INIT_FILE ?= $(SW_DIR)/$(SW_BUILD)/soctest.hex

TOPLEVEL = svarog_soc
# MODULE is overridable so `make -C tb/soc MODULE=test_sw INIT_FILE=...`
# can run an arbitrary image built from sw/ (that is what `make run` in
# an example does).
MODULE  ?= test_svarog_soc

VERILOG_SOURCES = $(SOC_SOURCES)

# C programs need the full 64 KiB (RAM_ADDR_WIDTH=14)
RAM_ADDR_WIDTH ?= 14
COMPILE_ARGS += -GRAM_ADDR_WIDTH=$(RAM_ADDR_WIDTH) -GINIT_FILE=\"$(INIT_FILE)\"

# passed through to the Python tests
export UART_DIV
export RUN_CYCLES
export EXPECT
export EXPECT_FILE

include $(TOPLEVEL_DIR)/tb/common/Makefile.include

EXTRA_ARGS += $(CPU_ARGS)

# rules after the include so cocotb's `all` stays the default goal.
# The built-in image is rebuilt by its own Makefile whenever its sources
# change; an image passed in through INIT_FILE is used as it is.
.PHONY: firmware
firmware:
	$(MAKE) -C $(SW_DIR) BUILD=$(SW_BUILD) CPU_HZ=$(CPU_HZ) \
	    BAUD=$$(( $(CPU_HZ) / $(UART_DIV) ))

$(SW_DIR)/$(SW_BUILD)/soctest.hex: firmware ;

$(SIM_BUILD)/Vtop.mk: $(INIT_FILE)
