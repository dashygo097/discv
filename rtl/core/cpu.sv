module cpu
  import riscv_pkg::*;
  import core_types_pkg::*;
#(
    parameter int unsigned XLEN = cfg_pkg::XLEN
) (
    input  instr_t                  instr_i,
    input  logic         [XLEN-1:0] pc_i,
    input  logic         [XLEN-1:0] rs1_data_i,
    input  logic         [XLEN-1:0] rs2_data_i,
    output reg_addr_t               rs1_o,
    output reg_addr_t               rs2_o,
    output reg_addr_t               rd_o,
    output logic         [XLEN-1:0] immediate_o,
    output logic         [XLEN-1:0] result_o,
    output decode_ctrl_t            ctrl_o
);

  logic [XLEN-1:0] operand_a;
  logic [XLEN-1:0] operand_b;

  decoder u_decoder (
      .instr_i,
      .rs1_o,
      .rs2_o,
      .rd_o,
      .ctrl_o
  );

  immediate_gen #(
      .XLEN(XLEN)
  ) u_immediate_gen (
      .instr_i(instr_i[ILEN-1:7]),
      .sel_i  (ctrl_o.immediate),
      .immediate_o
  );

  always_comb begin
    unique case (ctrl_o.operand_a)
      OPERAND_A_RS1: operand_a = rs1_data_i;
      OPERAND_A_PC:  operand_a = pc_i;
      default:       operand_a = '0;
    endcase

    unique case (ctrl_o.operand_b)
      OPERAND_B_RS2: operand_b = rs2_data_i;
      OPERAND_B_IMM: operand_b = immediate_o;
      default:       operand_b = '0;
    endcase
  end

  alu #(
      .XLEN(XLEN)
  ) u_alu (
      .lhs_i(operand_a),
      .rhs_i(operand_b),
      .op_i (ctrl_o.alu_op),
      .result_o
  );

endmodule
