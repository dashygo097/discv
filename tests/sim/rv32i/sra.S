// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  li t0, 0x80000001
  li t1, 63
  sra t2, t0, t1
  li t3, -1
  CHECK_EQ t2, t3, 1

  li t1, 33
  sra t2, t0, t1
  lui t3, 0xc0000
  CHECK_EQ t2, t3, 2

  li t1, 32
  sra t2, t0, t1
  CHECK_EQ t2, t0, 3

  li t0, 0x80000001
  srai t2, t0, 31
  li t3, -1
  CHECK_EQ t2, t3, 4

  srai t2, t0, 1
  lui t3, 0xc0000
  CHECK_EQ t2, t3, 5

  lui t0, 0x40000
  srai t2, t0, 1
  lui t3, 0x20000
  CHECK_EQ t2, t3, 6
TEST_END
