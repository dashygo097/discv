// REQUIRES: rv32i
// RUN: %cc -T %linker_script %start %s -o %t.elf
// RUN: %objcopy %t.elf %t.bin
// RUN: %simtest %t.bin

int main(void) { return 0; }
