// REQUIRES: rv32i, m
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  li t0, -7
  li t1, 3
  rem t2, t0, t1
  li t3, -1
  CHECK_EQ t2, t3, 1

  li t0, 7
  li t1, -3
  rem t2, t0, t1
  li t3, 1
  CHECK_EQ t2, t3, 2

  li t0, -1
  li t1, 16
  remu t2, t0, t1
  li t3, 15
  CHECK_EQ t2, t3, 3

  lui t0, 0x80000
  li t1, -1
  rem t2, t0, t1
  CHECK_EQ t2, zero, 4

  rem t2, t0, zero
  CHECK_EQ t2, t0, 5

  remu t2, t0, zero
  CHECK_EQ t2, t0, 6
TEST_END
