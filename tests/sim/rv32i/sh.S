// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  lla t0, .Lscratch
  li t1, 0x89abcdef
  sw t1, 0(t0)
  li t1, 0x01234567

  sh t1, 0(t0)
  lw t2, 0(t0)
  li t3, 0x89ab4567
  CHECK_EQ t2, t3, 1

  sh t1, 2(t0)
  lw t2, 0(t0)
  li t3, 0x45674567
  CHECK_EQ t2, t3, 2
TEST_END

.section .bss, "aw", @nobits
.p2align 2
.Lscratch:
  .zero 4
