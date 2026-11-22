module demu_axi5_lite_sim_top
  import core_pkg::*;
  import riscv_pkg::*;
  import demu_platform_pkg::*;
(
    input logic clk_i,
    input logic rst_n_i
);
  axi5_lite_if #(
      .ADDR_WIDTH($bits(addr_t)),
      .DATA_WIDTH($bits(word_t))
  ) imem (
      .ACLK   (clk_i),
      .ARESETn(rst_n_i)
  );

  axi5_lite_if #(
      .ADDR_WIDTH($bits(addr_t)),
      .DATA_WIDTH($bits(word_t))
  ) dmem (
      .ACLK   (clk_i),
      .ARESETn(rst_n_i)
  );

  valid_if #(.payload_t(retire_lane_t)) retire ();

  `DEMU_RTL_TOP u_dut (
      .imem  (imem),
      .dmem  (dmem),
      .retire(retire)
  );

  demu_axi5_lite_slv_bfm #(.PORT(IMEM_PORT)) u_imem (.axi(imem));

  demu_axi5_lite_slv_bfm #(.PORT(DMEM_PORT)) u_dmem (.axi(dmem));

  demu_retire_monitor u_retire (
      .clk_i  (clk_i),
      .rst_n_i(rst_n_i),
      .retire (retire)
  );
endmodule
