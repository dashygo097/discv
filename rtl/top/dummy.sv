module dummy
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

  cpu #(
      .XLEN(XLEN)
  ) u_cpu (
      .instr_i,
      .pc_i,
      .rs1_data_i,
      .rs2_data_i,
      .rs1_o,
      .rs2_o,
      .rd_o,
      .immediate_o,
      .result_o,
      .ctrl_o
  );

endmodule
