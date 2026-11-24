// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  lla t0, .Ldata
  addi t0, t0, 4

  lw t1, -4(t0)
  li t2, 0x80000001
  CHECK_EQ t1, t2, 1

  lw t1, 4(t0)
  li t2, 0x01234567
  CHECK_EQ t1, t2, 2
TEST_END

.section .rodata, "a", @progbits
.p2align 2
.Ldata:
  .word 0x80000001
  .word 0xdeadbeef
  .word 0x01234567
