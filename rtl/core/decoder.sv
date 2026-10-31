module decoder
  import riscv_pkg::*;
  import core_types_pkg::*;
(
    input  instr_t       instr_i,
    output reg_addr_t    rs1_o,
    output reg_addr_t    rs2_o,
    output reg_addr_t    rd_o,
    output decode_ctrl_t ctrl_o
);

  assign rs1_o = instr_i[19:15];
  assign rs2_o = instr_i[24:20];
  assign rd_o  = instr_i[11:7];

  always_comb begin
    unique casez (instr_i)
      // Register-register arithmetic
      INSTR_ADD:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_RS2),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_SUB:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_SUB),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_RS2),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_SLL:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_SLL),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_RS2),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_SLT:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_SLT),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_RS2),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_SLTU:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_SLTU),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_RS2),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_XOR:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_XOR),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_RS2),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_SRL:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_SRL),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_RS2),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_SRA:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_SRA),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_RS2),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_OR:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_OR),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_RS2),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_AND:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_AND),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_RS2),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .reg_write(1'b1)
      );

      // Immediate arithmetic
      INSTR_ADDI:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .rs1_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_SLLI:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_SLL),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .rs1_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_SLTI:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_SLT),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .rs1_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_SLTIU:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_SLTU),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .rs1_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_XORI:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_XOR),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .rs1_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_SRLI:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_SRL),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .rs1_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_SRAI:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_SRA),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .rs1_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_ORI:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_OR),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .rs1_read(1'b1),
        .reg_write(1'b1)
      );
      INSTR_ANDI:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_AND),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .rs1_read(1'b1),
        .reg_write(1'b1)
      );

      // Loads
      INSTR_LB:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .memory_size(MEM_BYTE),
        .result_source(RESULT_MEM),
        .rs1_read(1'b1),
        .reg_write(1'b1),
        .memory_read(1'b1)
      );
      INSTR_LH:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .memory_size(MEM_HALF),
        .result_source(RESULT_MEM),
        .rs1_read(1'b1),
        .reg_write(1'b1),
        .memory_read(1'b1)
      );
      INSTR_LW:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .result_source(RESULT_MEM),
        .rs1_read(1'b1),
        .reg_write(1'b1),
        .memory_read(1'b1)
      );
      INSTR_LBU:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .memory_size(MEM_BYTE),
        .result_source(RESULT_MEM),
        .rs1_read(1'b1),
        .reg_write(1'b1),
        .memory_read(1'b1),
        .memory_unsigned(1'b1)
      );
      INSTR_LHU:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .memory_size(MEM_HALF),
        .result_source(RESULT_MEM),
        .rs1_read(1'b1),
        .reg_write(1'b1),
        .memory_read(1'b1),
        .memory_unsigned(1'b1)
      );

      // Stores
      INSTR_SB:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_S),
        .memory_size(MEM_BYTE),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .memory_write(1'b1)
      );
      INSTR_SH:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_S),
        .memory_size(MEM_HALF),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .memory_write(1'b1)
      );
      INSTR_SW:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_S),
        .rs1_read(1'b1),
        .rs2_read(1'b1),
        .memory_write(1'b1)
      );

      // Conditional branches
      INSTR_BEQ:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_PC),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_B),
        .branch_op(BR_EQ),
        .rs1_read(1'b1),
        .rs2_read(1'b1)
      );
      INSTR_BNE:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_PC),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_B),
        .branch_op(BR_NE),
        .rs1_read(1'b1),
        .rs2_read(1'b1)
      );
      INSTR_BLT:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_PC),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_B),
        .branch_op(BR_LT),
        .rs1_read(1'b1),
        .rs2_read(1'b1)
      );
      INSTR_BGE:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_PC),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_B),
        .branch_op(BR_GE),
        .rs1_read(1'b1),
        .rs2_read(1'b1)
      );
      INSTR_BLTU:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_PC),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_B),
        .branch_op(BR_LTU),
        .rs1_read(1'b1),
        .rs2_read(1'b1)
      );
      INSTR_BGEU:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_PC),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_B),
        .branch_op(BR_GEU),
        .rs1_read(1'b1),
        .rs2_read(1'b1)
      );

      // Upper-immediate and control-flow instructions
      INSTR_LUI:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_U),
        .reg_write(1'b1)
      );
      INSTR_AUIPC:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_PC),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_U),
        .reg_write(1'b1)
      );
      INSTR_JAL:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_PC),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_J),
        .result_source(RESULT_PC_STEP),
        .reg_write(1'b1),
        .jump(1'b1)
      );
      INSTR_JALR:
      ctrl_o = make_decode_ctrl(
        .alu_op(ALU_ADD),
        .operand_a(OPERAND_A_RS1),
        .operand_b(OPERAND_B_IMM),
        .immediate(IMM_I),
        .result_source(RESULT_PC_STEP),
        .rs1_read(1'b1),
        .reg_write(1'b1),
        .jump(1'b1)
      );

      // Memory ordering
      INSTR_FENCE: ctrl_o = make_decode_ctrl(.alu_op(ALU_NONE), .serialize(1'b1));

      default: ctrl_o = make_decode_ctrl(.alu_op(ALU_NONE), .illegal(1'b1));
    endcase
  end

endmodule
