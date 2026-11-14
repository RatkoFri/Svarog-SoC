# SoC address map for testbenches. Mirrors config/svarog_soc_pkg.sv.
#
# Keep in step with the package: the decoder test checks the extents of
# every region listed here.

SLAVE = {
    "RAM": 0,
    "UART": 1,
    "TIMER": 2,
    "GPIO": 3,
}

NUM_SLAVES = len(SLAVE)

# name -> (base, size)
REGIONS = {
    "RAM": (0x0000_0000, 0x0001_0000),
    "UART": (0x2000_0000, 0x0000_1000),
    "TIMER": (0x2000_1000, 0x0000_1000),
    "GPIO": (0x2000_2000, 0x0000_1000),
}

# addresses that belong to no region (used by the decoder and
# interconnect tests; move one if a new slave takes its address)
HOLES = [
    0x0001_0000,   # just past the RAM
    0x1000_0000,
    0x1FFF_FFFC,   # just below the peripherals
    0x2000_3000,   # just past the last peripheral
    0xFFFF_FFFC,   # top of the address space
]

# external interrupt lines (index into the CPU's irq vector)
IRQ = {
    "UART": 0,
}
NUM_IRQS = len(IRQ)


def base(name):
    return REGIONS[name][0]
