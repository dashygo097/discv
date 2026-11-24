// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  lui t0, 0x80000
  li t1, 1

  slt t2, t0, t1
  CHECK_EQ t2, t1, 1

  slt t2, t1, t0
  CHECK_EQ t2, zero, 2

  sltu t2, t1, t0
  CHECK_EQ t2, t1, 3

  sltu t2, t0, t1
  CHECK_EQ t2, zero, 4

  slt t2, t0, t0
  CHECK_EQ t2, zero, 5

  sltu t2, t0, t0
  CHECK_EQ t2, zero, 6

  li t0, -2049
  slti t2, t0, -2048
  CHECK_EQ t2, t1, 7

  li t0, -2048
  slti t2, t0, -2048
  CHECK_EQ t2, zero, 8

  slti t2, zero, -1
  CHECK_EQ t2, zero, 9

  lui t0, 0x80000
  sltiu t2, t0, -1
  CHECK_EQ t2, t1, 10

  li t0, -1
  sltiu t2, t0, -1
  CHECK_EQ t2, zero, 11

  sltiu t2, t0, 1
  CHECK_EQ t2, zero, 12
TEST_END
