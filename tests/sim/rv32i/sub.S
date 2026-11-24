// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  li t0, 17
  li t1, 42
  sub t2, t0, t1
  li t3, -25
  CHECK_EQ t2, t3, 1

  lui t0, 0x80000
  li t1, 1
  sub t0, t0, t1
  li t3, 0x7fffffff
  CHECK_EQ t0, t3, 2

  sub t2, t1, t1
  CHECK_EQ t2, zero, 3
TEST_END
