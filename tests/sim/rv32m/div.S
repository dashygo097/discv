// REQUIRES: rv32i, m
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  li t0, -7
  li t1, 3
  div t2, t0, t1
  li t3, -2
  CHECK_EQ t2, t3, 1

  divu t2, t0, t1
  li t3, 0x55555553
  CHECK_EQ t2, t3, 2

  lui t0, 0x80000
  li t1, -1
  div t2, t0, t1
  CHECK_EQ t2, t0, 3

  div t2, t0, zero
  CHECK_EQ t2, t1, 4

  divu t2, t0, zero
  CHECK_EQ t2, t1, 5
TEST_END
