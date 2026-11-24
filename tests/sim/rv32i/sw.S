// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  lla t0, .Lscratch
  addi t0, t0, 4
  sh zero, 0(t0)
  sh zero, 2(t0)

  li t1, 0x89abcdef
  sw t1, -4(t0)
  lw t2, -4(t0)
  CHECK_EQ t2, t1, 1

  li t1, 0x76543210
  sw t1, 4(t0)
  lw t2, 4(t0)
  CHECK_EQ t2, t1, 2

  lw t2, 0(t0)
  CHECK_EQ t2, zero, 3
TEST_END

.section .bss, "aw", @nobits
.p2align 2
.Lscratch:
  .zero 12
