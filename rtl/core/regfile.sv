`include "cc/registers.svh"

module regfile
  import riscv_pkg::*;
(
    input logic clk_i,

    input  reg_addr_t rs1_addr_i,
    input  reg_addr_t rs2_addr_i,
    output word_t     rs1_data_o,
    output word_t     rs2_data_o,

    input logic      rd_write_i,
    input reg_addr_t rd_addr_i,
    input word_t     rd_data_i
);
  localparam int unsigned NumRegs = 1 << $bits(reg_addr_t);

  word_t regs_r[NumRegs];

  always_comb begin
    regs_r[0]  = '0;
    rs1_data_o = regs_r[rs1_addr_i];
    rs2_data_o = regs_r[rs2_addr_i];
  end

  for (genvar i = 1; i < NumRegs; i++) begin : gen_register
    logic write_enable;
    assign write_enable = rd_write_i && (rd_addr_i == reg_addr_t'(i));
    `REG_CE(regs_r[i], rd_data_i, write_enable)
  end

endmodule
