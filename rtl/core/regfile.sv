module regfile
  import riscv_pkg::*;
(
    input logic clk_i,

    input reg_addr_t rs1_addr_i,
    input reg_addr_t rs2_addr_i,
    output word_t    rs1_data_o,
    output word_t    rs2_data_o,

    input logic      rd_write_i,
    input reg_addr_t rd_addr_i,
    input word_t     rd_data_i
);

  localparam int unsigned NUM_REGS = 1 << $bits(reg_addr_t);

  word_t regs_r[NUM_REGS];

  always_comb begin
    if (rs1_addr_i == '0) begin
      rs1_data_o = '0;
    end else begin
      rs1_data_o = regs_r[rs1_addr_i];
    end

    if (rs2_addr_i == '0) begin
      rs2_data_o = '0;
    end else begin
      rs2_data_o = regs_r[rs2_addr_i];
    end
  end

  always_ff @(posedge clk_i) begin
    if (rd_write_i && (rd_addr_i != '0)) begin
      regs_r[rd_addr_i] <= rd_data_i;
    end
  end

endmodule
