#ifndef TEST_CASE_OP
#define TEST_CASE_OP addi
#endif

.macro TEST_BEGIN
  .section .text.start, "ax", @progbits
  .option norvc
  .globl _start
  .type _start, @function
_start:
.endm

.macro TEST_CASE case_id
  TEST_CASE_OP t6, zero, \case_id
.endm

.macro CHECK_EQ actual, expected, case_id
  TEST_CASE \case_id
  bne \actual, \expected, .Lfail
.endm

.macro TEST_END
  li t5, HOST_EXIT
  sw zero, 0(t5)
.Lpass_halt:
  j .Lpass_halt

.Lfail:
  li t5, HOST_EXIT
  sw t6, 0(t5)
.Lfail_halt:
  j .Lfail_halt
  .size _start, . - _start
.endm
