module cpu_sim_top
  import riscv_pkg::*;
  import core_types_pkg::*;
(
    input logic clk_i,
    input logic rst_n_i,

    output logic  imem_req_valid_o,
    input  logic  imem_req_ready_i,
    output addr_t imem_req_addr_o,

    input  logic   imem_rsp_valid_i,
    output logic   imem_rsp_ready_o,
    input  instr_t imem_rsp_data_i,
    input  logic   imem_rsp_error_i,

    output logic         dmem_req_valid_o,
    input  logic         dmem_req_ready_i,
    output addr_t        dmem_req_addr_o,
    output logic         dmem_req_write_o,
    output word_t        dmem_req_data_o,
    output byte_enable_t dmem_req_strb_o,

    input  logic  dmem_rsp_valid_i,
    output logic  dmem_rsp_ready_o,
    input  word_t dmem_rsp_data_i,
    input  logic  dmem_rsp_error_i,

    output logic      retire_valid_o,
    output addr_t     retire_pc_o,
    output instr_t    retire_instr_o,
    output reg_addr_t retire_rd_o,
    output word_t     retire_data_o,
    output logic      retire_write_o,
    output logic      retire_illegal_o
);

  handshake_if #(.payload_t(imem_req_t)) imem_req ();
  handshake_if #(.payload_t(imem_rsp_t)) imem_rsp ();
  handshake_if #(.payload_t(dmem_req_t)) dmem_req ();
  handshake_if #(.payload_t(dmem_rsp_t)) dmem_rsp ();
  handshake_if #(.payload_t(retire_lane_t)) retire ();

  always_comb begin
    imem_rsp.valid   = imem_rsp_valid_i;
    imem_rsp.payload = '{data: imem_rsp_data_i, error: imem_rsp_error_i};

    dmem_rsp.valid   = dmem_rsp_valid_i;
    dmem_rsp.payload = '{data: dmem_rsp_data_i, error: dmem_rsp_error_i};

    imem_req.ready   = imem_req_ready_i;
    imem_req_valid_o = imem_req.valid;
    imem_req_addr_o  = imem_req.payload.addr;
    imem_rsp_ready_o = imem_rsp.ready;

    dmem_req.ready   = dmem_req_ready_i;
    dmem_req_valid_o = dmem_req.valid;
    dmem_req_addr_o  = dmem_req.payload.addr;
    dmem_req_write_o = dmem_req.payload.write;
    dmem_req_data_o  = dmem_req.payload.data;
    dmem_req_strb_o  = dmem_req.payload.strb;
    dmem_rsp_ready_o = dmem_rsp.ready;

    retire.ready     = 1'b1;
    retire_valid_o   = retire.valid;
    retire_pc_o      = retire.payload.pc;
    retire_instr_o   = retire.payload.instr;
    retire_rd_o      = retire.payload.rd;
    retire_data_o    = retire.payload.data;
    retire_write_o   = retire.payload.write;
    retire_illegal_o = retire.payload.illegal;
  end

  cpu u_cpu (
      .clk_i,
      .rst_n_i,
      .imem_req,
      .imem_rsp,
      .dmem_req,
      .dmem_rsp,
      .retire
  );

endmodule
