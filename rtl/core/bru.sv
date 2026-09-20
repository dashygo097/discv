module bru
  import riscv_pkg::*;
  import core_types_pkg::*;
(
    input word_t      lhs_i,
    input word_t      rhs_i,
    input branch_op_e branch_op_i,
    input logic       jump_i,
    input logic       indirect_i,
    input addr_t      target_i,

    output logic  taken_o,
    output addr_t target_o
);

  logic branch_condition;

  always_comb begin
    unique case (branch_op_i)
      BR_EQ:   branch_condition = lhs_i == rhs_i;
      BR_NE:   branch_condition = lhs_i != rhs_i;
      BR_LT:   branch_condition = $signed(lhs_i) < $signed(rhs_i);
      BR_GE:   branch_condition = $signed(lhs_i) >= $signed(rhs_i);
      BR_LTU:  branch_condition = lhs_i < rhs_i;
      BR_GEU:  branch_condition = lhs_i >= rhs_i;
      default: branch_condition = 1'b0;
    endcase

    taken_o = jump_i || branch_condition;

    if (indirect_i) begin
      target_o = {target_i[$bits(addr_t)-1:1], 1'b0};
    end else begin
      target_o = target_i;
    end
  end

endmodule
