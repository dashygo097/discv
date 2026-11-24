// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  lla t0, .Ldata
  addi t0, t0, 2

  lh t1, -2(t0)
  lhu t2, -2(t0)
  li t3, 32767
  CHECK_EQ t1, t3, 1
  CHECK_EQ t2, t3, 2

  lh t1, 0(t0)
  lhu t2, 0(t0)
  li t3, -32767
  li t4, 32769
  CHECK_EQ t1, t3, 3
  CHECK_EQ t2, t4, 4
TEST_END

.section .rodata, "a", @progbits
.p2align 2
.Ldata:
  .word 0x80017fff
