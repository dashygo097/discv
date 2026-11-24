// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  li t0, 0xf0f00ff0
  li t1, 0x0ff033cc
  xor t2, t0, t1
  li t3, 0xff003c3c
  CHECK_EQ t2, t3, 1

  xor t2, t0, t0
  CHECK_EQ t2, zero, 2

  li t0, 0x01234567
  xori t2, t0, -1
  li t3, 0xfedcba98
  CHECK_EQ t2, t3, 3

  xori t2, t0, 0x155
  li t3, 0x01234432
  CHECK_EQ t2, t3, 4
TEST_END
