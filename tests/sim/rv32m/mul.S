// REQUIRES: rv32i, m
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  li t0, -7
  li t1, 6
  mul t2, t0, t1
  li t3, -42
  CHECK_EQ t2, t3, 1

  li t0, 0x12345678
  li t1, 16
  mul t2, t0, t1
  li t3, 0x23456780
  CHECK_EQ t2, t3, 2

  li t0, -2
  li t1, -1

  mulh t2, t0, t1
  CHECK_EQ t2, zero, 3

  mulhsu t2, t0, t1
  CHECK_EQ t2, t0, 4

  mulhu t2, t0, t1
  li t3, -3
  CHECK_EQ t2, t3, 5

  lui t0, 0x80000
  li t1, 3
  mulh t2, t0, t1
  li t3, -2
  CHECK_EQ t2, t3, 6
TEST_END
