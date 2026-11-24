// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  lla t0, .Ldata
  addi t0, t0, 2

  lb t1, -2(t0)
  lbu t2, -2(t0)
  li t3, 1
  CHECK_EQ t1, t3, 1
  CHECK_EQ t2, t3, 2

  lb t1, -1(t0)
  lbu t2, -1(t0)
  li t3, -1
  li t4, 255
  CHECK_EQ t1, t3, 3
  CHECK_EQ t2, t4, 4

  lb t1, 0(t0)
  lbu t2, 0(t0)
  li t3, -128
  li t4, 128
  CHECK_EQ t1, t3, 5
  CHECK_EQ t2, t4, 6

  lb t1, 1(t0)
  lbu t2, 1(t0)
  li t3, 127
  CHECK_EQ t1, t3, 7
  CHECK_EQ t2, t3, 8
TEST_END

.section .rodata, "a", @progbits
.p2align 2
.Ldata:
  .word 0x7f80ff01
