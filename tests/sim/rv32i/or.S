// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  li t0, 0xf0f00ff0
  li t1, 0x0ff033cc
  or t2, t0, t1
  li t3, 0xfff03ffc
  CHECK_EQ t2, t3, 1

  or t2, zero, t1
  CHECK_EQ t2, t1, 2

  li t0, 0x12340020
  ori t2, t0, 0x105
  li t3, 0x12340125
  CHECK_EQ t2, t3, 3

  ori t2, t0, -2048
  li t3, 0xfffff820
  CHECK_EQ t2, t3, 4
TEST_END
