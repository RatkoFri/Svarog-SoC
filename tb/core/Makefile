TOPLEVEL_DIR := $(abspath ../..)

# The CPU subsystem runs a real C program, built from sw/tests/coretest.
SW_DIR    := $(TOPLEVEL_DIR)/sw/tests/coretest
INIT_FILE ?= $(SW_DIR)/build/coretest.hex

TOPLEVEL = core_tb
MODULE   = test_core

VERILOG_SOURCES = $(PKG_SOURCES) $(CPU_SOURCES) \
                  $(RTL_DIR)/interconnect/ahb_to_apb.sv $(MEM_SOURCES) \
                  $(PWD)/core_tb.sv

# the full 64 KiB: the program's stack and result block sit at the top
RAM_ADDR_WIDTH ?= 14
COMPILE_ARGS += -GRAM_ADDR_WIDTH=$(RAM_ADDR_WIDTH) -GINIT_FILE=\"$(INIT_FILE)\"

include $(TOPLEVEL_DIR)/tb/common/Makefile.include

EXTRA_ARGS += $(CPU_ARGS)

# rules after the include so cocotb's `all` stays the default goal.
# The image is rebuilt by its own Makefile whenever its sources change.
.PHONY: firmware
firmware:
	$(MAKE) -C $(SW_DIR)

$(INIT_FILE): firmware ;

$(SIM_BUILD)/Vtop.mk: $(INIT_FILE)
