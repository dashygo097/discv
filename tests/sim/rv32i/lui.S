// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
  lla t1, .Lexpected
  lw t2, 0(t1)
  lui t0, 0x12345
  CHECK_EQ t0, t2, 1

  lw t2, 4(t1)
  lui t0, 0xfffff
  CHECK_EQ t0, t2, 2

  lui t0, 0
  CHECK_EQ t0, zero, 3
TEST_END

.section .rodata, "a", @progbits
.p2align 2
.Lexpected:
  .word 0x12345000
  .word 0xfffff000
