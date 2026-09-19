module alu
  import riscv_pkg::*;
  import core_types_pkg::*;
(
    input  word_t   lhs_i,
    input  word_t   rhs_i,
    input  alu_op_e op_i,
    output word_t   result_o
);

  localparam int unsigned SHAMT_WIDTH = $clog2($bits(word_t));

  always_comb begin
    unique case (op_i)
      ALU_ADD:  result_o = lhs_i + rhs_i;
      ALU_SUB:  result_o = lhs_i - rhs_i;
      ALU_AND:  result_o = lhs_i & rhs_i;
      ALU_OR:   result_o = lhs_i | rhs_i;
      ALU_XOR:  result_o = lhs_i ^ rhs_i;
      ALU_SLL:  result_o = lhs_i << rhs_i[SHAMT_WIDTH-1:0];
      ALU_SRL:  result_o = lhs_i >> rhs_i[SHAMT_WIDTH-1:0];
      ALU_SRA:  result_o = $unsigned($signed(lhs_i) >>> rhs_i[SHAMT_WIDTH-1:0]);
      ALU_SLT:  result_o = word_t'($signed(lhs_i) < $signed(rhs_i));
      ALU_SLTU: result_o = word_t'(lhs_i < rhs_i);
      ALU_NONE: result_o = '0;
      default:  result_o = '0;
    endcase
  end
endmodule
