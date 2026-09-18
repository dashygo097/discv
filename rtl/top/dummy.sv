module dummy
  import riscv_pkg::*;
  import core_types_pkg::*;
(
    input  instr_t       instr_i,
    input  addr_t        pc_i,
    input  word_t        rs1_data_i,
    input  word_t        rs2_data_i,
    output reg_addr_t    rs1_o,
    output reg_addr_t    rs2_o,
    output reg_addr_t    rd_o,
    output word_t        immediate_o,
    output word_t        result_o,
    output decode_ctrl_t ctrl_o
);

  cpu u_cpu (
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
