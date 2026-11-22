// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

.section .text.start, "ax", @progbits
.globl _start
.type _start, @function

_start:
  addi x1, x0, 10
  addi x2, x0, 20
  add x3, x1, x2
  li x4, 1
  li x5, 30
  bne x3, x5, .Lexit
  li x4, 0

.Lexit:
  li x6, HOST_EXIT
  sw x4, 0(x6)

.Lhalt:
  j .Lhalt
