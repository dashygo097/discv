`include "cc/assertions.svh"

module cpu_5stage_inorder_axi5_lite
  import core_pkg::*;
  import riscv_pkg::*;
(
    axi5_lite_if.source imem,
    axi5_lite_if.source dmem,
    valid_if.source     retire
);
  handshake_if #(.payload_t(dmem_req_t)) imem_req ();
  handshake_if #(.payload_t(dmem_resp_t)) imem_resp ();
  handshake_if #(.payload_t(dmem_req_t)) dmem_req ();
  handshake_if #(.payload_t(dmem_resp_t)) dmem_resp ();

  addr_t imem_addr;

  always_comb begin
    imem_req.payload = '{addr: imem_addr, write: 1'b0, data: '0, strb: '0};
  end

  cpu_5stage_inorder_virt u_cpu (
      .clk_i            (imem.ACLK),
      .rst_n_i          (imem.ARESETn),
      .imem_req_valid_o (imem_req.valid),
      .imem_req_ready_i (imem_req.ready),
      .imem_req_addr_o  (imem_addr),
      .imem_resp_valid_i(imem_resp.valid),
      .imem_resp_ready_o(imem_resp.ready),
      .imem_resp_data_i (instr_t'(imem_resp.payload.data)),
      .imem_resp_error_i(imem_resp.payload.error),
      .dmem_req_valid_o (dmem_req.valid),
      .dmem_req_ready_i (dmem_req.ready),
      .dmem_req_addr_o  (dmem_req.payload.addr),
      .dmem_req_write_o (dmem_req.payload.write),
      .dmem_req_data_o  (dmem_req.payload.data),
      .dmem_req_strb_o  (dmem_req.payload.strb),
      .dmem_resp_valid_i(dmem_resp.valid),
      .dmem_resp_ready_o(dmem_resp.ready),
      .dmem_resp_data_i (dmem_resp.payload.data),
      .dmem_resp_error_i(dmem_resp.payload.error),
      .retire_valid_o   (retire.valid),
      .retire_pc_o      (retire.payload.pc),
      .retire_instr_o   (retire.payload.instr),
      .retire_rd_o      (retire.payload.rd),
      .retire_data_o    (retire.payload.data),
      .retire_write_o   (retire.payload.write),
      .retire_illegal_o (retire.payload.illegal)
  );

  virt_to_axi5_lite u_imem (
      .req (imem_req),
      .resp(imem_resp),
      .axi (imem)
  );

  virt_to_axi5_lite u_dmem (
      .req (dmem_req),
      .resp(dmem_resp),
      .axi (dmem)
  );

  `ASSERT_INIT(InstructionBusWidth, $bits(instr_t) == $bits(word_t))
endmodule
