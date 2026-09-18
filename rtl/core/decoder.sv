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

  localparam decode_ctrl_t CTRL_ILLEGAL = '{
      alu_op: ALU_ADD,
      operand_a: OPERAND_A_ZERO,
      operand_b: OPERAND_B_ZERO,
      immediate: IMM_NONE,
      branch_op: BR_NONE,
      memory_size: MEM_BYTE,
      result_source: RESULT_ALU,
      illegal: 1'b1,
      default: '0
  };

  localparam decode_ctrl_t CTRL_FENCE = '{
      alu_op: ALU_ADD,
      operand_a: OPERAND_A_ZERO,
      operand_b: OPERAND_B_ZERO,
      immediate: IMM_NONE,
      branch_op: BR_NONE,
      memory_size: MEM_BYTE,
      result_source: RESULT_ALU,
      serialize: 1'b1,
      default: '0
  };

  decode_ctrl_t decoded_ctrl;

  function automatic decode_ctrl_t alu_ctrl(input alu_op_e alu_op, input operand_a_sel_e operand_a,
                                            input operand_b_sel_e operand_b,
                                            input immediate_sel_e immediate);
    return
    '{
        alu_op: alu_op,
        operand_a: operand_a,
        operand_b: operand_b,
        immediate: immediate,
        branch_op: BR_NONE,
        memory_size: MEM_BYTE,
        result_source: RESULT_ALU,
        rs1_read: operand_a == OPERAND_A_RS1,
        rs2_read: operand_b == OPERAND_B_RS2,
        reg_write: 1'b1,
        default: '0
    }
    ;
  endfunction

  function automatic decode_ctrl_t load_ctrl(input memory_size_e memory_size,
                                             input logic memory_unsigned);
    return
    '{
        alu_op: ALU_ADD,
        operand_a: OPERAND_A_RS1,
        operand_b: OPERAND_B_IMM,
        immediate: IMM_I,
        branch_op: BR_NONE,
        memory_size: memory_size,
        result_source: RESULT_MEM,
        rs1_read: 1'b1,
        reg_write: 1'b1,
        memory_read: 1'b1,
        memory_unsigned: memory_unsigned,
        default: '0
    }
    ;
  endfunction

  function automatic decode_ctrl_t store_ctrl(input memory_size_e memory_size);
    return
    '{
        alu_op: ALU_ADD,
        operand_a: OPERAND_A_RS1,
        operand_b: OPERAND_B_IMM,
        immediate: IMM_S,
        branch_op: BR_NONE,
        memory_size: memory_size,
        result_source: RESULT_ALU,
        rs1_read: 1'b1,
        rs2_read: 1'b1,
        memory_write: 1'b1,
        default: '0
    }
    ;
  endfunction

  function automatic decode_ctrl_t branch_ctrl(input branch_op_e branch_op);
    return
    '{
        alu_op: ALU_ADD,
        operand_a: OPERAND_A_PC,
        operand_b: OPERAND_B_IMM,
        immediate: IMM_B,
        branch_op: branch_op,
        memory_size: MEM_BYTE,
        result_source: RESULT_ALU,
        rs1_read: 1'b1,
        rs2_read: 1'b1,
        default: '0
    }
    ;
  endfunction

  function automatic decode_ctrl_t jump_ctrl(input operand_a_sel_e operand_a,
                                             input immediate_sel_e immediate);
    return
    '{
        alu_op: ALU_ADD,
        operand_a: operand_a,
        operand_b: OPERAND_B_IMM,
        immediate: immediate,
        branch_op: BR_NONE,
        memory_size: MEM_BYTE,
        result_source: RESULT_PC_STEP,
        rs1_read: operand_a == OPERAND_A_RS1,
        reg_write: 1'b1,
        jump: 1'b1,
        default: '0
    }
    ;
  endfunction

  function automatic decode_ctrl_t architectural_ctrl(
      input decode_ctrl_t ctrl, input reg_addr_t rs1, input reg_addr_t rs2, input reg_addr_t rd);
    return
    '{
        alu_op: ctrl.alu_op,
        operand_a: ctrl.operand_a,
        operand_b: ctrl.operand_b,
        immediate: ctrl.immediate,
        branch_op: ctrl.branch_op,
        memory_size: ctrl.memory_size,
        result_source: ctrl.result_source,
        rs1_read: ctrl.rs1_read && (rs1 != '0),
        rs2_read: ctrl.rs2_read && (rs2 != '0),
        reg_write: ctrl.reg_write && (rd != '0),
        memory_read: ctrl.memory_read,
        memory_write: ctrl.memory_write,
        memory_unsigned: ctrl.memory_unsigned,
        jump: ctrl.jump,
        serialize: ctrl.serialize,
        illegal: ctrl.illegal
    }
    ;
  endfunction

  assign rs1_o = instr_i[19:15];
  assign rs2_o = instr_i[24:20];
  assign rd_o  = instr_i[11:7];

  always_comb begin
    unique casez (instr_i)
      // RV32I register-register arithmetic.
      32'b0000000_?????_?????_000_?????_0110011:
      decoded_ctrl = alu_ctrl(ALU_ADD, OPERAND_A_RS1, OPERAND_B_RS2, IMM_NONE);
      32'b0100000_?????_?????_000_?????_0110011:
      decoded_ctrl = alu_ctrl(ALU_SUB, OPERAND_A_RS1, OPERAND_B_RS2, IMM_NONE);
      32'b0000000_?????_?????_001_?????_0110011:
      decoded_ctrl = alu_ctrl(ALU_SLL, OPERAND_A_RS1, OPERAND_B_RS2, IMM_NONE);
      32'b0000000_?????_?????_010_?????_0110011:
      decoded_ctrl = alu_ctrl(ALU_SLT, OPERAND_A_RS1, OPERAND_B_RS2, IMM_NONE);
      32'b0000000_?????_?????_011_?????_0110011:
      decoded_ctrl = alu_ctrl(ALU_SLTU, OPERAND_A_RS1, OPERAND_B_RS2, IMM_NONE);
      32'b0000000_?????_?????_100_?????_0110011:
      decoded_ctrl = alu_ctrl(ALU_XOR, OPERAND_A_RS1, OPERAND_B_RS2, IMM_NONE);
      32'b0000000_?????_?????_101_?????_0110011:
      decoded_ctrl = alu_ctrl(ALU_SRL, OPERAND_A_RS1, OPERAND_B_RS2, IMM_NONE);
      32'b0100000_?????_?????_101_?????_0110011:
      decoded_ctrl = alu_ctrl(ALU_SRA, OPERAND_A_RS1, OPERAND_B_RS2, IMM_NONE);
      32'b0000000_?????_?????_110_?????_0110011:
      decoded_ctrl = alu_ctrl(ALU_OR, OPERAND_A_RS1, OPERAND_B_RS2, IMM_NONE);
      32'b0000000_?????_?????_111_?????_0110011:
      decoded_ctrl = alu_ctrl(ALU_AND, OPERAND_A_RS1, OPERAND_B_RS2, IMM_NONE);

      // RV32I immediate arithmetic. Shift-immediate patterns constrain funct7.
      32'b???????_?????_?????_000_?????_0010011:
      decoded_ctrl = alu_ctrl(ALU_ADD, OPERAND_A_RS1, OPERAND_B_IMM, IMM_I);
      32'b0000000_?????_?????_001_?????_0010011:
      decoded_ctrl = alu_ctrl(ALU_SLL, OPERAND_A_RS1, OPERAND_B_IMM, IMM_I);
      32'b???????_?????_?????_010_?????_0010011:
      decoded_ctrl = alu_ctrl(ALU_SLT, OPERAND_A_RS1, OPERAND_B_IMM, IMM_I);
      32'b???????_?????_?????_011_?????_0010011:
      decoded_ctrl = alu_ctrl(ALU_SLTU, OPERAND_A_RS1, OPERAND_B_IMM, IMM_I);
      32'b???????_?????_?????_100_?????_0010011:
      decoded_ctrl = alu_ctrl(ALU_XOR, OPERAND_A_RS1, OPERAND_B_IMM, IMM_I);
      32'b0000000_?????_?????_101_?????_0010011:
      decoded_ctrl = alu_ctrl(ALU_SRL, OPERAND_A_RS1, OPERAND_B_IMM, IMM_I);
      32'b0100000_?????_?????_101_?????_0010011:
      decoded_ctrl = alu_ctrl(ALU_SRA, OPERAND_A_RS1, OPERAND_B_IMM, IMM_I);
      32'b???????_?????_?????_110_?????_0010011:
      decoded_ctrl = alu_ctrl(ALU_OR, OPERAND_A_RS1, OPERAND_B_IMM, IMM_I);
      32'b???????_?????_?????_111_?????_0010011:
      decoded_ctrl = alu_ctrl(ALU_AND, OPERAND_A_RS1, OPERAND_B_IMM, IMM_I);

      // Loads and stores.
      32'b???????_?????_?????_000_?????_0000011: decoded_ctrl = load_ctrl(MEM_BYTE, 1'b0);
      32'b???????_?????_?????_001_?????_0000011: decoded_ctrl = load_ctrl(MEM_HALF, 1'b0);
      32'b???????_?????_?????_010_?????_0000011: decoded_ctrl = load_ctrl(MEM_WORD, 1'b0);
      32'b???????_?????_?????_100_?????_0000011: decoded_ctrl = load_ctrl(MEM_BYTE, 1'b1);
      32'b???????_?????_?????_101_?????_0000011: decoded_ctrl = load_ctrl(MEM_HALF, 1'b1);
      32'b???????_?????_?????_000_?????_0100011: decoded_ctrl = store_ctrl(MEM_BYTE);
      32'b???????_?????_?????_001_?????_0100011: decoded_ctrl = store_ctrl(MEM_HALF);
      32'b???????_?????_?????_010_?????_0100011: decoded_ctrl = store_ctrl(MEM_WORD);

      // Conditional branches.
      32'b???????_?????_?????_000_?????_1100011: decoded_ctrl = branch_ctrl(BR_EQ);
      32'b???????_?????_?????_001_?????_1100011: decoded_ctrl = branch_ctrl(BR_NE);
      32'b???????_?????_?????_100_?????_1100011: decoded_ctrl = branch_ctrl(BR_LT);
      32'b???????_?????_?????_101_?????_1100011: decoded_ctrl = branch_ctrl(BR_GE);
      32'b???????_?????_?????_110_?????_1100011: decoded_ctrl = branch_ctrl(BR_LTU);
      32'b???????_?????_?????_111_?????_1100011: decoded_ctrl = branch_ctrl(BR_GEU);

      // Upper-immediate and control-transfer instructions.
      32'b???????_?????_?????_???_?????_0110111:
      decoded_ctrl = alu_ctrl(ALU_ADD, OPERAND_A_ZERO, OPERAND_B_IMM, IMM_U);
      32'b???????_?????_?????_???_?????_0010111:
      decoded_ctrl = alu_ctrl(ALU_ADD, OPERAND_A_PC, OPERAND_B_IMM, IMM_U);
      32'b???????_?????_?????_???_?????_1101111: decoded_ctrl = jump_ctrl(OPERAND_A_PC, IMM_J);
      32'b???????_?????_?????_000_?????_1100111: decoded_ctrl = jump_ctrl(OPERAND_A_RS1, IMM_I);

      // FENCE is legal and requests pipeline serialization.
      32'b???????_?????_?????_000_?????_0001111: decoded_ctrl = CTRL_FENCE;

      default: decoded_ctrl = CTRL_ILLEGAL;
    endcase
  end

  always_comb begin
    ctrl_o = architectural_ctrl(decoded_ctrl, rs1_o, rs2_o, rd_o);
  end

endmodule
