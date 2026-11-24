// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  lui t0, 0x80000
  li t1, 1

  TEST_CASE 1
  blt t0, t1, .Lblt_taken
  j .Lfail

.Lblt_taken:
  TEST_CASE 2
  blt t1, t0, .Lfail

  TEST_CASE 3
  blt t0, t0, .Lfail

  TEST_CASE 4
  bge t1, t0, .Lbge_greater
  j .Lfail

.Lbge_greater:
  TEST_CASE 5
  bge t0, t1, .Lfail

  TEST_CASE 6
  bge t0, t0, .Lbge_equal
  j .Lfail

.Lbge_equal:
  TEST_CASE 7
  bltu t1, t0, .Lbltu_taken
  j .Lfail

.Lbltu_taken:
  TEST_CASE 8
  bltu t0, t1, .Lfail

  TEST_CASE 9
  bltu t0, t0, .Lfail

  TEST_CASE 10
  bgeu t0, t1, .Lbgeu_greater
  j .Lfail

.Lbgeu_greater:
  TEST_CASE 11
  bgeu t1, t0, .Lfail

  TEST_CASE 12
  bgeu t0, t0, .Lbgeu_equal
  j .Lfail

.Lbgeu_equal:
TEST_END
