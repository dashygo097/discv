// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  li t0, -1
  li t1, -1
  TEST_CASE 1
  beq t0, t1, .Lbeq_taken
  j .Lfail

.Lbeq_backward:
  j .Lbeq_done

.Lbeq_taken:
  TEST_CASE 2
  beq t0, zero, .Lfail

  TEST_CASE 3
  beq t0, t1, .Lbeq_backward
  j .Lfail

.Lbeq_done:

  lui t0, 0x80000
  TEST_CASE 4
  bne t0, zero, .Lbne_taken
  j .Lfail

.Lbne_taken:
  lui t1, 0x80000
  TEST_CASE 5
  bne t0, t1, .Lfail
TEST_END
