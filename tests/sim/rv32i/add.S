// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#define TEST_CASE_OP ori
#include "../macros.inc"

TEST_BEGIN
  li t0, 10
  li t1, 20
  add t2, t0, t1
  ori t3, zero, 30
  CHECK_EQ t2, t3, 1

  lui t0, 0x80000
  ori t1, zero, 1
  sub t3, t0, t1
  add t2, t3, t1
  CHECK_EQ t2, t0, 2

  ori t0, zero, 1
  addi t2, t0, 2047
  lui t3, 1
  srli t3, t3, 1
  CHECK_EQ t2, t3, 3

  addi t2, zero, -2048
  ori t3, zero, -2048
  CHECK_EQ t2, t3, 4

  lui t0, 0x80000
  ori t1, zero, 1
  sub t3, t0, t1
  addi t2, t3, 1
  CHECK_EQ t2, t0, 5
TEST_END
