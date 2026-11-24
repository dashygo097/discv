// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  lla t0, .Lscratch
  li t1, 0x12345678
  sw t1, 0(t0)
  fence rw, rw
  lw t2, 0(t0)
  CHECK_EQ t2, t1, 1
TEST_END

.section .bss, "aw", @nobits
.p2align 2
.Lscratch:
  .zero 4
