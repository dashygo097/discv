`ifdef DEMU_SIM_TOP_demu_sim_top
module demu_sim_top
  import core_pkg::*;
  import riscv_pkg::*;
  import demu_dpi_pkg::*;
  import demu_platform_pkg::*;
(
    input logic clk_i,
    input logic rst_n_i
);
  handshake_if #(.payload_t(mem_req_t)) imem_req ();
  handshake_if #(.payload_t(mem_resp_t)) imem_resp ();
  handshake_if #(.payload_t(mem_req_t)) dmem_req ();
  handshake_if #(.payload_t(mem_resp_t)) dmem_resp ();
  valid_if #(.payload_t(retire_lane_t)) retire ();

  addr_t imem_addr;

  always_comb begin
    imem_req.payload = '{addr: imem_addr, write: 1'b0, data: '0, strb: '0};
  end

  `DEMU_RTL_TOP u_dut (
      .clk_i            (clk_i),
      .rst_n_i          (rst_n_i),
      .imem_req_valid_o (imem_req.valid),
      .imem_req_ready_i (imem_req.ready),
      .imem_req_addr_o  (imem_addr),
      .imem_resp_valid_i(imem_resp.valid),
      .imem_resp_ready_o(imem_resp.ready),
      .imem_resp_data_i (imem_resp.payload.data),
      .imem_resp_error_i(imem_resp.payload.status != MEM_OKAY),
      .dmem_req_valid_o (dmem_req.valid),
      .dmem_req_ready_i (dmem_req.ready),
      .dmem_req_addr_o  (dmem_req.payload.addr),
      .dmem_req_write_o (dmem_req.payload.write),
      .dmem_req_data_o  (dmem_req.payload.data),
      .dmem_req_strb_o  (dmem_req.payload.strb),
      .dmem_resp_valid_i(dmem_resp.valid),
      .dmem_resp_ready_o(dmem_resp.ready),
      .dmem_resp_data_i (dmem_resp.payload.data),
      .dmem_resp_error_i(dmem_resp.payload.status != MEM_OKAY),
      .retire_valid_o   (retire.valid),
      .retire_pc_o      (retire.payload.pc),
      .retire_instr_o   (retire.payload.instr),
      .retire_rd_o      (retire.payload.rd),
      .retire_data_o    (retire.payload.data),
      .retire_write_o   (retire.payload.write),
      .retire_illegal_o (retire.payload.illegal)
  );

  demu_virt_bfm #(
      .PORT(IMEM_PORT)
  ) u_imem (
      .clk_i  (clk_i),
      .rst_n_i(rst_n_i),
      .req    (imem_req),
      .resp   (imem_resp)
  );

  demu_virt_bfm #(
      .PORT(DMEM_PORT)
  ) u_dmem (
      .clk_i  (clk_i),
      .rst_n_i(rst_n_i),
      .req    (dmem_req),
      .resp   (dmem_resp)
  );

  demu_retire_monitor u_retire (
      .clk_i  (clk_i),
      .rst_n_i(rst_n_i),
      .retire (retire)
  );

endmodule

`endif
