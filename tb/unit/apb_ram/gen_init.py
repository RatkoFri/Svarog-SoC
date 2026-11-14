#!/usr/bin/env python3
"""Memory image for the apb_ram testbench: word i holds pattern(i)."""

import sys

WORDS = 256


def pattern(i):
    return (0xC0DE0000 | i) ^ (i << 20) & 0xFFFFFFFF


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "mem_init.hex"
    with open(path, "w") as f:
        for i in range(WORDS):
            f.write(f"{pattern(i) & 0xFFFFFFFF:08x}\n")


if __name__ == "__main__":
    main()
