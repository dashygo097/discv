`include "cc/registers.svh"

module cpu_5stage_inorder_virt
  import riscv_pkg::*;
  import core_pkg::*;
(
    input logic clk_i,
    input logic rst_n_i,

    output logic  imem_req_valid_o,
    input  logic  imem_req_ready_i,
    output addr_t imem_req_addr_o,

    input  logic   imem_resp_valid_i,
    output logic   imem_resp_ready_o,
    input  instr_t imem_resp_data_i,
    input  logic   imem_resp_error_i,

    output logic         dmem_req_valid_o,
    input  logic         dmem_req_ready_i,
    output addr_t        dmem_req_addr_o,
    output logic         dmem_req_write_o,
    output word_t        dmem_req_data_o,
    output byte_enable_t dmem_req_strb_o,

    input  logic  dmem_resp_valid_i,
    output logic  dmem_resp_ready_o,
    input  word_t dmem_resp_data_i,
    input  logic  dmem_resp_error_i,

    output logic      retire_valid_o,
    output addr_t     retire_pc_o,
    output instr_t    retire_instr_o,
    output reg_addr_t retire_rd_o,
    output word_t     retire_data_o,
    output logic      retire_write_o,
    output logic      retire_illegal_o
);

  handshake_if #(.payload_t(imem_req_t)) imem_req ();
  handshake_if #(.payload_t(imem_resp_t)) imem_resp ();
  handshake_if #(.payload_t(dmem_req_t)) dmem_req ();
  handshake_if #(.payload_t(dmem_resp_t)) dmem_resp ();
  valid_if #(.payload_t(retire_lane_t)) retire ();

  handshake_if #(.payload_t(if_id_payload_t)) if_id_out ();
  handshake_if #(.payload_t(id_issue_payload_t)) id_issue_in ();
  handshake_if #(.payload_t(id_issue_payload_t)) id_issue_out ();
  handshake_if #(.payload_t(issue_ex_payload_t)) issue_ex_in ();
  handshake_if #(.payload_t(issue_ex_payload_t)) issue_ex_out ();
  handshake_if #(.payload_t(ex_mem_payload_t)) ex_mem_in ();
  handshake_if #(.payload_t(ex_mem_payload_t)) ex_mem_out ();
  handshake_if #(.payload_t(mem_wb_payload_t)) mem_wb_in ();
  valid_if #(.payload_t(mem_wb_payload_t)) mem_wb_out ();

  localparam addr_t InstrBytes = addr_t'(ILEN / 8);

  logic            redirect_valid;
  addr_t           redirect_pc;

  reg_addr_t       decode_rs1;
  reg_addr_t       decode_rs2;
  reg_addr_t       decode_rd;
  decode_ctrl_t    decode_ctrl;
  decode_ctrl_t    decode_effective_ctrl;
  word_t           decode_immediate;

  word_t           rs1_data;
  word_t           rs2_data;

  logic            issue_hazard;
  logic            issue_ex_hazard;
  logic            ex_mem_hazard;
  logic            mem_wb_hazard;
  logic            issue_serialize;

  word_t           execute_operand_a;
  word_t           execute_operand_b;
  word_t           execute_result;
  logic            execute_redirect;

  word_t           memory_write_data;
  byte_enable_t    memory_write_strb;
  word_t           memory_load_data;
  logic            memory_misaligned;
  logic            memory_access;
  logic            memory_req;
  logic            memory_illegal;
  logic            memory_req_sent_r;
  logic            memory_req_fire;
  logic            memory_resp_fire;
  word_t           memory_result;

  logic            regfile_write;
  logic            writeback_valid_r;
  mem_wb_payload_t writeback_payload_r;

  function automatic logic depends_on(input id_issue_payload_t consumer, input logic producer_valid,
                                      input logic producer_write, input reg_addr_t destination);
    return producer_valid && producer_write &&
        ((consumer.ctrl.rs1_read && consumer.rs1 != '0 && consumer.rs1 == destination) ||
         (consumer.ctrl.rs2_read && consumer.rs2 != '0 && consumer.rs2 == destination));
  endfunction

  always_comb begin
    imem_resp.valid   = imem_resp_valid_i;
    imem_resp.payload = '{data: imem_resp_data_i, error: imem_resp_error_i};

    dmem_resp.valid   = dmem_resp_valid_i;
    dmem_resp.payload = '{data: dmem_resp_data_i, error: dmem_resp_error_i};

    imem_req.ready    = imem_req_ready_i;
    imem_req_valid_o  = imem_req.valid;
    imem_req_addr_o   = imem_req.payload.addr;
    imem_resp_ready_o = imem_resp.ready;

    dmem_req.ready    = dmem_req_ready_i;
    dmem_req_valid_o  = dmem_req.valid;
    dmem_req_addr_o   = dmem_req.payload.addr;
    dmem_req_write_o  = dmem_req.payload.write;
    dmem_req_data_o   = dmem_req.payload.data;
    dmem_req_strb_o   = dmem_req.payload.strb;
    dmem_resp_ready_o = dmem_resp.ready;

    retire_valid_o    = retire.valid;
    retire_pc_o       = retire.payload.pc;
    retire_instr_o    = retire.payload.instr;
    retire_rd_o       = retire.payload.rd;
    retire_data_o     = retire.payload.data;
    retire_write_o    = retire.payload.write;
    retire_illegal_o  = retire.payload.illegal;
  end

  ifu u_ifu (
      .clk_i           (clk_i),
      .rst_n_i         (rst_n_i),
      .redirect_valid_i(redirect_valid),
      .redirect_pc_i   (redirect_pc),
      .imem_req        (imem_req),
      .imem_resp       (imem_resp),
      .if_id           (if_id_out)
  );

  // Decode
  flushable_pipe #(
      .payload_t(id_issue_payload_t)
  ) u_id_issue (
      .clk_i  (clk_i),
      .rst_n_i(rst_n_i),
      .flush_i(redirect_valid),
      .in     (id_issue_in),
      .out    (id_issue_out)
  );

  decoder u_decoder (
      .instr_i(if_id_out.payload.instr),
      .rs1_o  (decode_rs1),
      .rs2_o  (decode_rs2),
      .rd_o   (decode_rd),
      .ctrl_o (decode_ctrl)
  );

  immediate_gen u_immediate_gen (
      .instr_i    (if_id_out.payload.instr[ILEN-1:7]),
      .sel_i      (decode_ctrl.immediate),
      .immediate_o(decode_immediate)
  );

  always_comb begin
    decode_effective_ctrl = if_id_out.payload.error ? make_decode_ctrl(
      .alu_op(ALU_NONE),
      .illegal(1'b1)
    ) : decode_ctrl;

    id_issue_in.valid = if_id_out.valid;
    id_issue_in.payload = '{
        pc: if_id_out.payload.pc,
        instr: if_id_out.payload.instr,
        rs1: decode_rs1,
        rs2: decode_rs2,
        rd: decode_rd,
        immediate: decode_immediate,
        ctrl: decode_effective_ctrl
    };
    if_id_out.ready = id_issue_in.ready;
  end

  // Issue
  pipe #(
      .payload_t(issue_ex_payload_t)
  ) u_issue_ex (
      .clk_i  (clk_i),
      .rst_n_i(rst_n_i),
      .in     (issue_ex_in),
      .out    (issue_ex_out)
  );

  regfile u_regfile (
      .clk_i     (clk_i),
      .rs1_addr_i(id_issue_out.payload.rs1),
      .rs2_addr_i(id_issue_out.payload.rs2),
      .rs1_data_o(rs1_data),
      .rs2_data_o(rs2_data),
      .rd_write_i(regfile_write),
      .rd_addr_i (mem_wb_out.payload.rd),
      .rd_data_i (mem_wb_out.payload.result)
  );

  always_comb begin
    issue_ex_hazard = depends_on(
      id_issue_out.payload,
      issue_ex_out.valid,
      issue_ex_out.payload.ctrl.reg_write,
      issue_ex_out.payload.rd
    );
    ex_mem_hazard = depends_on(id_issue_out.payload, ex_mem_out.valid, ex_mem_out.payload.reg_write,
                               ex_mem_out.payload.rd);
    mem_wb_hazard = depends_on(id_issue_out.payload, mem_wb_out.valid, mem_wb_out.payload.reg_write,
                               mem_wb_out.payload.rd);
    issue_hazard = issue_ex_hazard || ex_mem_hazard || mem_wb_hazard;

    issue_serialize = id_issue_out.payload.ctrl.serialize &&
        (issue_ex_out.valid || ex_mem_out.valid || mem_wb_out.valid);

    issue_ex_in.valid = id_issue_out.valid && !issue_hazard && !issue_serialize;
    issue_ex_in.payload = '{
        pc: id_issue_out.payload.pc,
        instr: id_issue_out.payload.instr,
        rd: id_issue_out.payload.rd,
        rs1_data: id_issue_out.payload.ctrl.rs1_read ? rs1_data : '0,
        rs2_data: id_issue_out.payload.ctrl.rs2_read ? rs2_data : '0,
        immediate: id_issue_out.payload.immediate,
        ctrl: id_issue_out.payload.ctrl
    };
    id_issue_out.ready = issue_ex_in.ready && !issue_hazard && !issue_serialize;
  end

  // Execute
  pipe #(
      .payload_t(ex_mem_payload_t)
  ) u_ex_mem (
      .clk_i  (clk_i),
      .rst_n_i(rst_n_i),
      .in     (ex_mem_in),
      .out    (ex_mem_out)
  );

  always_comb begin
    unique case (issue_ex_out.payload.ctrl.operand_a)
      OPERAND_A_RS1: execute_operand_a = issue_ex_out.payload.rs1_data;
      OPERAND_A_PC:  execute_operand_a = issue_ex_out.payload.pc;
      default:       execute_operand_a = '0;
    endcase

    unique case (issue_ex_out.payload.ctrl.operand_b)
      OPERAND_B_RS2: execute_operand_b = issue_ex_out.payload.rs2_data;
      OPERAND_B_IMM: execute_operand_b = issue_ex_out.payload.immediate;
      default:       execute_operand_b = '0;
    endcase
  end

  alu u_alu (
      .lhs_i   (execute_operand_a),
      .rhs_i   (execute_operand_b),
      .op_i    (issue_ex_out.payload.ctrl.alu_op),
      .result_o(execute_result)
  );

  bru u_bru (
      .lhs_i(issue_ex_out.payload.rs1_data),
      .rhs_i(issue_ex_out.payload.rs2_data),
      .branch_op_i(issue_ex_out.payload.ctrl.branch_op),
      .jump_i(issue_ex_out.payload.ctrl.jump),
      .indirect_i(issue_ex_out.payload.ctrl.jump &&
        (issue_ex_out.payload.ctrl.operand_a == OPERAND_A_RS1)
      ),
      .target_i(execute_result),
      .taken_o(execute_redirect),
      .target_o(redirect_pc)
  );

  always_comb begin
    redirect_valid = issue_ex_out.valid && ex_mem_in.ready &&
        execute_redirect && !issue_ex_out.payload.ctrl.illegal;

    ex_mem_in.valid = issue_ex_out.valid;
    ex_mem_in.payload = '{
        pc: issue_ex_out.payload.pc,
        instr: issue_ex_out.payload.instr,
        rd: issue_ex_out.payload.rd,
        result: execute_result,
        store_data: issue_ex_out.payload.rs2_data,
        memory_size: issue_ex_out.payload.ctrl.memory_size,
        result_source: issue_ex_out.payload.ctrl.result_source,
        reg_write: issue_ex_out.payload.ctrl.reg_write,
        memory_read: issue_ex_out.payload.ctrl.memory_read,
        memory_write: issue_ex_out.payload.ctrl.memory_write,
        memory_unsigned: issue_ex_out.payload.ctrl.memory_unsigned,
        illegal: issue_ex_out.payload.ctrl.illegal
    };
    issue_ex_out.ready = ex_mem_in.ready;
  end

  // Memory
  lsu u_lsu (
      .byte_offset_i(ex_mem_out.payload.result[1:0]),
      .store_data_i (ex_mem_out.payload.store_data),
      .read_data_i  (dmem_resp.payload.data),
      .size_i       (ex_mem_out.payload.memory_size),
      .unsigned_i   (ex_mem_out.payload.memory_unsigned),
      .write_data_o (memory_write_data),
      .write_strb_o (memory_write_strb),
      .load_data_o  (memory_load_data),
      .misaligned_o (memory_misaligned)
  );

  always_comb begin
    memory_access = ex_mem_out.payload.memory_read || ex_mem_out.payload.memory_write;
    memory_req = memory_access && !ex_mem_out.payload.illegal && !memory_misaligned;

    dmem_req.valid = ex_mem_out.valid && memory_req && !memory_req_sent_r;
    dmem_req.payload = '{
        addr: ex_mem_out.payload.result,
        write: ex_mem_out.payload.memory_write,
        data: memory_write_data,
        strb: memory_write_strb
    };

    dmem_resp.ready = 1'b0;
    ex_mem_out.ready = 1'b0;
    mem_wb_in.valid = 1'b0;

    unique case (ex_mem_out.payload.result_source)
      RESULT_ALU: memory_result = ex_mem_out.payload.result;
      RESULT_MEM: memory_result = memory_load_data;
      RESULT_PC_STEP: memory_result = ex_mem_out.payload.pc + InstrBytes;
      default: memory_result = '0;
    endcase

    memory_illegal = ex_mem_out.payload.illegal ||
        (memory_access && memory_misaligned) ||
        (memory_req_sent_r && dmem_resp.valid && dmem_resp.payload.error);

    mem_wb_in.payload = '{
        pc: ex_mem_out.payload.pc,
        instr: ex_mem_out.payload.instr,
        rd: ex_mem_out.payload.rd,
        result: memory_result,
        reg_write: ex_mem_out.payload.reg_write,
        illegal: memory_illegal
    };

    if (ex_mem_out.valid) begin
      if (!memory_req) begin
        mem_wb_in.valid  = 1'b1;
        ex_mem_out.ready = mem_wb_in.ready;
      end else if (memory_req_sent_r) begin
        mem_wb_in.valid  = dmem_resp.valid;
        dmem_resp.ready  = mem_wb_in.ready;
        ex_mem_out.ready = dmem_resp.valid && mem_wb_in.ready;
      end
    end

    memory_req_fire  = dmem_req.valid && dmem_req.ready;
    memory_resp_fire = dmem_resp.valid && dmem_resp.ready;
  end

  `REG_CE_CLR_ARSTN(memory_req_sent_r, 1'b1, memory_req_fire, memory_resp_fire, 1'b0)

  `REG_ARSTN(writeback_valid_r, mem_wb_in.valid, 1'b0)
  `REG_CE(writeback_payload_r, mem_wb_in.payload, mem_wb_in.valid)

  always_comb begin
    mem_wb_in.ready = 1'b1;
    mem_wb_out.valid = writeback_valid_r;
    mem_wb_out.payload = writeback_payload_r;

    regfile_write = mem_wb_out.valid && mem_wb_out.payload.reg_write && !mem_wb_out.payload.illegal;

    retire.valid = mem_wb_out.valid;
    retire.payload = '{
        pc: mem_wb_out.payload.pc,
        instr: mem_wb_out.payload.instr,
        rd: mem_wb_out.payload.rd,
        data: mem_wb_out.payload.result,
        write: regfile_write,
        illegal: mem_wb_out.payload.illegal
    };
  end

endmodule
