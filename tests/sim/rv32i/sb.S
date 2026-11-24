// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  lla t0, .Lscratch
  li t1, 0x11223344
  sw t1, 0(t0)
  li t1, 0xdeadbea5

  sb t1, 0(t0)
  lw t2, 0(t0)
  li t3, 0x112233a5
  CHECK_EQ t2, t3, 1

  sb t1, 1(t0)
  lw t2, 0(t0)
  li t3, 0x1122a5a5
  CHECK_EQ t2, t3, 2

  sb t1, 2(t0)
  lw t2, 0(t0)
  li t3, 0x11a5a5a5
  CHECK_EQ t2, t3, 3

  sb t1, 3(t0)
  lw t2, 0(t0)
  li t3, 0xa5a5a5a5
  CHECK_EQ t2, t3, 4
TEST_END

.section .bss, "aw", @nobits
.p2align 2
.Lscratch:
  .zero 4
