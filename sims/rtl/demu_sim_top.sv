module demu_sim_top
  import core_types_pkg::*;
  import demu_platform_pkg::*;
(
    input logic clk_i,
    input logic rst_n_i
);

  handshake_if #(.payload_t(imem_req_t)) imem_req ();
  handshake_if #(.payload_t(imem_rsp_t)) imem_rsp ();
  handshake_if #(.payload_t(dmem_req_t)) dmem_req ();
  handshake_if #(.payload_t(dmem_rsp_t)) dmem_rsp ();
  valid_if #(.payload_t(retire_lane_t)) retire ();

  cpu u_cpu (
      .clk_i,
      .rst_n_i,
      .imem_req,
      .imem_rsp,
      .dmem_req,
      .dmem_rsp,
      .retire
  );

  demu_virt_imem_bfm #(
      .PORT(IMEM_PORT)
  ) u_imem (
      .clk_i,
      .rst_n_i,
      .request (imem_req),
      .response(imem_rsp)
  );

  demu_virt_dmem_bfm #(
      .PORT(DMEM_PORT)
  ) u_dmem (
      .clk_i,
      .rst_n_i,
      .request (dmem_req),
      .response(dmem_rsp)
  );

  demu_retire_monitor u_retire (
      .clk_i,
      .rst_n_i,
      .retire
  );

endmodule
