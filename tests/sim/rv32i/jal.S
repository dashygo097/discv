// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  TEST_CASE 1
  jal t0, .Ljal_forward
.Ljal_forward_link:
  bne t6, zero, .Lfail

.Ljal_backward:
  lla t1, .Ljal_backward_link
  CHECK_EQ t0, t1, 2

  addi t2, zero, 0
  TEST_CASE 3
  jal zero, .Ljal_discard
  bne t6, zero, .Lfail

.Ljal_forward:
  lla t1, .Ljal_forward_link
  CHECK_EQ t0, t1, 4

  TEST_CASE 5
  jal t0, .Ljal_backward
.Ljal_backward_link:
  bne t6, zero, .Lfail

.Ljal_discard:
  CHECK_EQ zero, t2, 6

  lla t0, .Ljalr_forward
  addi t0, t0, -3
  TEST_CASE 7
  jalr t1, 4(t0)
.Ljalr_forward_link:
  j .Lfail

.Ljalr_backward:
  lla t1, .Ljalr_backward_link
  CHECK_EQ t0, t1, 8
  j .Ljalr_done

.Ljalr_forward:
  lla t2, .Ljalr_forward_link
  CHECK_EQ t1, t2, 9

  lla t0, .Ljalr_backward
  addi t0, t0, 4
  TEST_CASE 10
  jalr t0, -4(t0)
.Ljalr_backward_link:
  j .Lfail

.Ljalr_done:
TEST_END
