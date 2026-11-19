module demu_sim_top
  import core_pkg::*;
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

  `DEMU_RTL_TOP u_dut (
      .clk_i,
      .rst_n_i,
      .imem_req_valid_o(imem_req.valid),
      .imem_req_ready_i(imem_req.ready),
      .imem_req_addr_o (imem_req.payload.addr),
      .imem_rsp_valid_i(imem_rsp.valid),
      .imem_rsp_ready_o(imem_rsp.ready),
      .imem_rsp_data_i (imem_rsp.payload.data),
      .imem_rsp_error_i(imem_rsp.payload.error),
      .dmem_req_valid_o(dmem_req.valid),
      .dmem_req_ready_i(dmem_req.ready),
      .dmem_req_addr_o (dmem_req.payload.addr),
      .dmem_req_write_o(dmem_req.payload.write),
      .dmem_req_data_o (dmem_req.payload.data),
      .dmem_req_strb_o (dmem_req.payload.strb),
      .dmem_rsp_valid_i(dmem_rsp.valid),
      .dmem_rsp_ready_o(dmem_rsp.ready),
      .dmem_rsp_data_i (dmem_rsp.payload.data),
      .dmem_rsp_error_i(dmem_rsp.payload.error),
      .retire_valid_o  (retire.valid),
      .retire_pc_o     (retire.payload.pc),
      .retire_instr_o  (retire.payload.instr),
      .retire_rd_o     (retire.payload.rd),
      .retire_data_o   (retire.payload.data),
      .retire_write_o  (retire.payload.write),
      .retire_illegal_o(retire.payload.illegal)
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
