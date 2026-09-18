module alu
  import core_types_pkg::*;
#(
    parameter int unsigned XLEN = cfg_pkg::XLEN
) (
    input  logic    [XLEN-1:0] lhs_i,
    input  logic    [XLEN-1:0] rhs_i,
    input  alu_op_e            op_i,
    output logic    [XLEN-1:0] result_o
);

  localparam int unsigned SHAMT_WIDTH = $clog2(XLEN);

  always_comb begin
    result_o = '0;

    unique case (op_i)
      ALU_ADD:  result_o = lhs_i + rhs_i;
      ALU_SUB:  result_o = lhs_i - rhs_i;
      ALU_AND:  result_o = lhs_i & rhs_i;
      ALU_OR:   result_o = lhs_i | rhs_i;
      ALU_XOR:  result_o = lhs_i ^ rhs_i;
      ALU_SLL:  result_o = lhs_i << rhs_i[SHAMT_WIDTH-1:0];
      ALU_SRL:  result_o = lhs_i >> rhs_i[SHAMT_WIDTH-1:0];
      ALU_SRA:  result_o = $unsigned($signed(lhs_i) >>> rhs_i[SHAMT_WIDTH-1:0]);
      ALU_SLT:  result_o[0] = $signed(lhs_i) < $signed(rhs_i);
      ALU_SLTU: result_o[0] = lhs_i < rhs_i;
      default:  result_o = '0;
    endcase
  end
endmodule
