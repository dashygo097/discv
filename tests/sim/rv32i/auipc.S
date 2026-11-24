// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

#include "../macros.inc"

TEST_BEGIN
.Lzero:
  auipc t0, 0
  lui t1, %hi(.Lzero)
  addi t1, t1, %lo(.Lzero)
  CHECK_EQ t0, t1, 1

.Lpositive:
  auipc t0, 0x12345
  lui t1, %hi(.Lpositive)
  addi t1, t1, %lo(.Lpositive)
  lui t2, 0x12345
  add t1, t1, t2
  CHECK_EQ t0, t1, 2

.Lnegative:
  auipc t0, 0xfffff
  lui t1, %hi(.Lnegative)
  addi t1, t1, %lo(.Lnegative)
  lui t2, 0xfffff
  add t1, t1, t2
  CHECK_EQ t0, t1, 3
TEST_END
