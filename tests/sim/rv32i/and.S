// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  li t0, 0xf0f00ff0
  li t1, 0x0ff033cc
  and t2, t0, t1
  li t3, 0x00f003c0
  CHECK_EQ t2, t3, 1

  and t2, t0, zero
  CHECK_EQ t2, zero, 2

  li t0, 0x89abcdef
  andi t2, t0, -16
  li t3, 0x89abcde0
  CHECK_EQ t2, t3, 3

  andi t2, t0, 0x7ff
  li t3, 0x5ef
  CHECK_EQ t2, t3, 4
TEST_END
