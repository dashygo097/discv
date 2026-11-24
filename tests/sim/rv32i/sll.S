// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  li t0, 1
  li t1, 63
  sll t2, t0, t1
  lui t3, 0x80000
  CHECK_EQ t2, t3, 1

  li t0, 0x80000001
  li t1, 33
  sll t2, t0, t1
  li t3, 2
  CHECK_EQ t2, t3, 2

  li t1, 32
  sll t2, t0, t1
  CHECK_EQ t2, t0, 3

  li t0, 1
  slli t2, t0, 31
  lui t3, 0x80000
  CHECK_EQ t2, t3, 4

  li t0, 0x80000001
  slli t2, t0, 1
  li t3, 2
  CHECK_EQ t2, t3, 5

  slli t2, t0, 0
  CHECK_EQ t2, t0, 6
TEST_END
