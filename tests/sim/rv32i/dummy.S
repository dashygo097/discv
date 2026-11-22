// REQUIRES: rv32i
// RUN: %cc -T %linker_script %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

.section .text.start, "ax", @progbits
.globl _start
.type _start, @function

_start:
  li t0, HOST_EXIT
  sw zero, 0(t0)

.Lhalt:
  j .Lhalt
