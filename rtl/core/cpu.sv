module cpu
  import riscv_pkg::*;
  import core_types_pkg::*;
(
    input logic clk_i,
    input logic rst_n_i,

    output logic      imem_req_valid_o,
    input  logic      imem_req_ready_i,
    output imem_req_t imem_req_o,

    input  logic      imem_rsp_valid_i,
    output logic      imem_rsp_ready_o,
    input  imem_rsp_t imem_rsp_i,

    output logic      dmem_req_valid_o,
    input  logic      dmem_req_ready_i,
    output dmem_req_t dmem_req_o,

    input  logic      dmem_rsp_valid_i,
    output logic      dmem_rsp_ready_o,
    input  dmem_rsp_t dmem_rsp_i,

    output logic         retire_valid_o,
    output retire_lane_t retire_lane_o
);

  handshake_if #(.payload_t(if_id_payload_t)) if_id_input ();
  handshake_if #(.payload_t(if_id_payload_t)) if_id_output ();
  handshake_if #(.payload_t(id_issue_payload_t)) id_issue_input ();
  handshake_if #(.payload_t(id_issue_payload_t)) id_issue_output ();
  handshake_if #(.payload_t(issue_ex_payload_t)) issue_ex_input ();
  handshake_if #(.payload_t(issue_ex_payload_t)) issue_ex_output ();
  handshake_if #(.payload_t(ex_mem_payload_t)) ex_mem_input ();
  handshake_if #(.payload_t(ex_mem_payload_t)) ex_mem_output ();
  handshake_if #(.payload_t(mem_wb_payload_t)) mem_wb_input ();
  handshake_if #(.payload_t(mem_wb_payload_t)) mem_wb_output ();

  typedef enum logic [1:0] {
    FETCH_RESET   = 2'b00,
    FETCH_READY   = 2'b01,
    FETCH_WAIT    = 2'b10,
    FETCH_DISCARD = 2'b11
  } fetch_state_e;

  addr_t        fetch_pc_r;
  addr_t        fetch_request_pc_r;
  fetch_state_e fetch_state_r;
  fetch_state_e next_fetch_state;
  logic         fetch_request_fire;
  logic         fetch_response_fire;

  logic         redirect_valid;
  addr_t        redirect_pc;

  reg_addr_t    decode_rs1;
  reg_addr_t    decode_rs2;
  reg_addr_t    decode_rd;
  decode_ctrl_t decode_ctrl;
  word_t        decode_immediate;

  word_t        rs1_data;
  word_t        rs2_data;

  logic         issue_hazard;
  logic         issue_serialize;

  word_t        execute_operand_a;
  word_t        execute_operand_b;
  word_t        execute_result;
  logic         execute_redirect;

  word_t        memory_write_data;
  byte_enable_t memory_write_strb;
  word_t        memory_load_data;
  logic         memory_misaligned;
  logic         memory_access;
  logic         memory_request;
  logic         memory_request_sent_r;
  logic         memory_request_fire;
  logic         memory_response_fire;
  word_t        memory_result;

  logic         regfile_write;

  function automatic logic depends_on(input logic read_enable, input reg_addr_t source,
                                      input logic producer_valid, input logic producer_write,
                                      input reg_addr_t destination);
    return read_enable && producer_valid && producer_write &&
        (source != '0) && (source == destination);
  endfunction

  pipe_stage #(
      .payload_t(if_id_payload_t)
  ) u_if_id (
      .clk_i,
      .rst_n_i,
      .flush_i(redirect_valid),
      .upstream(if_id_input),
      .downstream(if_id_output)
  );

  pipe_stage #(
      .payload_t(id_issue_payload_t)
  ) u_id_issue (
      .clk_i,
      .rst_n_i,
      .flush_i(redirect_valid),
      .upstream(id_issue_input),
      .downstream(id_issue_output)
  );

  pipe_stage #(
      .payload_t(issue_ex_payload_t)
  ) u_issue_ex (
      .clk_i,
      .rst_n_i,
      .flush_i(1'b0),
      .upstream(issue_ex_input),
      .downstream(issue_ex_output)
  );

  pipe_stage #(
      .payload_t(ex_mem_payload_t)
  ) u_ex_mem (
      .clk_i,
      .rst_n_i,
      .flush_i(1'b0),
      .upstream(ex_mem_input),
      .downstream(ex_mem_output)
  );

  pipe_stage #(
      .payload_t(mem_wb_payload_t)
  ) u_mem_wb (
      .clk_i,
      .rst_n_i,
      .flush_i(1'b0),
      .upstream(mem_wb_input),
      .downstream(mem_wb_output)
  );

  always_comb begin
    imem_req_valid_o = (fetch_state_r == FETCH_READY) && !redirect_valid;
    imem_req_o = '{addr: fetch_pc_r};

    if_id_input.valid = (fetch_state_r == FETCH_WAIT) && imem_rsp_valid_i;
    if_id_input.payload = '{
        pc: fetch_request_pc_r,
        instr: imem_rsp_i.data,
        error: imem_rsp_i.error
    };

    imem_rsp_ready_o = (fetch_state_r == FETCH_DISCARD) ||
        ((fetch_state_r == FETCH_WAIT) && if_id_input.ready);

    fetch_request_fire = imem_req_valid_o && imem_req_ready_i;
    fetch_response_fire = imem_rsp_valid_i && imem_rsp_ready_o;
  end

  always_comb begin
    unique case (fetch_state_r)
      FETCH_RESET: next_fetch_state = FETCH_READY;

      FETCH_READY: begin
        if (fetch_request_fire) begin
          next_fetch_state = FETCH_WAIT;
        end else begin
          next_fetch_state = FETCH_READY;
        end
      end

      FETCH_WAIT: begin
        if (redirect_valid) begin
          next_fetch_state = FETCH_DISCARD;
        end else if (fetch_response_fire) begin
          next_fetch_state = FETCH_READY;
        end else begin
          next_fetch_state = FETCH_WAIT;
        end
      end

      FETCH_DISCARD: begin
        if (fetch_response_fire) begin
          next_fetch_state = FETCH_READY;
        end else begin
          next_fetch_state = FETCH_DISCARD;
        end
      end

      default: next_fetch_state = FETCH_RESET;
    endcase
  end

  always_ff @(posedge clk_i or negedge rst_n_i) begin
    if (!rst_n_i) begin
      fetch_pc_r <= addr_t'(cfg_pkg::RESET_VECTOR);
      fetch_request_pc_r <= '0;
      fetch_state_r <= FETCH_RESET;
    end else begin
      fetch_state_r <= next_fetch_state;

      unique case (fetch_state_r)
        FETCH_READY: begin
          if (redirect_valid) begin
            fetch_pc_r <= redirect_pc;
          end else if (fetch_request_fire) begin
            fetch_pc_r <= fetch_pc_r + addr_t'(ILEN / 8);
            fetch_request_pc_r <= fetch_pc_r;
          end
        end

        FETCH_WAIT: begin
          if (redirect_valid) begin
            fetch_pc_r <= redirect_pc;
          end
        end

        FETCH_DISCARD: begin
          if (redirect_valid) begin
            fetch_pc_r <= redirect_pc;
          end

        end

        default: begin
          fetch_pc_r <= addr_t'(cfg_pkg::RESET_VECTOR);
          fetch_request_pc_r <= '0;
        end
      endcase
    end
  end

  decoder u_decoder (
      .instr_i(if_id_output.payload.instr),
      .rs1_o(decode_rs1),
      .rs2_o(decode_rs2),
      .rd_o(decode_rd),
      .ctrl_o(decode_ctrl)
  );

  immediate_gen u_immediate_gen (
      .instr_i(if_id_output.payload.instr[ILEN-1:7]),
      .sel_i(decode_ctrl.immediate),
      .immediate_o(decode_immediate)
  );

  always_comb begin
    id_issue_input.valid = if_id_output.valid;
    id_issue_input.payload = '{
        pc: if_id_output.payload.pc,
        rs1: decode_rs1,
        rs2: decode_rs2,
        rd: decode_rd,
        immediate: decode_immediate,
        ctrl: if_id_output.payload.error ? make_decode_ctrl(.illegal(1'b1)) : decode_ctrl
    };
    if_id_output.ready = id_issue_input.ready;
  end

  regfile u_regfile (
      .clk_i,
      .rs1_addr_i(id_issue_output.payload.rs1),
      .rs2_addr_i(id_issue_output.payload.rs2),
      .rs1_data_o(rs1_data),
      .rs2_data_o(rs2_data),
      .rd_write_i(regfile_write),
      .rd_addr_i (mem_wb_output.payload.rd),
      .rd_data_i (mem_wb_output.payload.result)
  );

  always_comb begin
    issue_hazard = depends_on(
      id_issue_output.payload.ctrl.rs1_read,
      id_issue_output.payload.rs1,
      issue_ex_output.valid,
      issue_ex_output.payload.ctrl.reg_write,
      issue_ex_output.payload.rd
    ) || depends_on(
      id_issue_output.payload.ctrl.rs2_read,
      id_issue_output.payload.rs2,
      issue_ex_output.valid,
      issue_ex_output.payload.ctrl.reg_write,
      issue_ex_output.payload.rd
    ) || depends_on(
      id_issue_output.payload.ctrl.rs1_read,
      id_issue_output.payload.rs1,
      ex_mem_output.valid,
      ex_mem_output.payload.reg_write,
      ex_mem_output.payload.rd
    ) || depends_on(
      id_issue_output.payload.ctrl.rs2_read,
      id_issue_output.payload.rs2,
      ex_mem_output.valid,
      ex_mem_output.payload.reg_write,
      ex_mem_output.payload.rd
    ) || depends_on(
      id_issue_output.payload.ctrl.rs1_read,
      id_issue_output.payload.rs1,
      mem_wb_output.valid,
      mem_wb_output.payload.reg_write,
      mem_wb_output.payload.rd
    ) || depends_on(
      id_issue_output.payload.ctrl.rs2_read,
      id_issue_output.payload.rs2,
      mem_wb_output.valid,
      mem_wb_output.payload.reg_write,
      mem_wb_output.payload.rd
    );

    issue_serialize = id_issue_output.payload.ctrl.serialize &&
        (issue_ex_output.valid || ex_mem_output.valid || mem_wb_output.valid);

    issue_ex_input.valid = id_issue_output.valid && !issue_hazard && !issue_serialize;
    issue_ex_input.payload = '{
        pc: id_issue_output.payload.pc,
        rd: id_issue_output.payload.rd,
        rs1_data: id_issue_output.payload.ctrl.rs1_read ? rs1_data : '0,
        rs2_data: id_issue_output.payload.ctrl.rs2_read ? rs2_data : '0,
        immediate: id_issue_output.payload.immediate,
        ctrl: id_issue_output.payload.ctrl
    };
    id_issue_output.ready = issue_ex_input.ready && !issue_hazard && !issue_serialize;
  end

  always_comb begin
    unique case (issue_ex_output.payload.ctrl.operand_a)
      OPERAND_A_RS1: execute_operand_a = issue_ex_output.payload.rs1_data;
      OPERAND_A_PC:  execute_operand_a = issue_ex_output.payload.pc;
      default:       execute_operand_a = '0;
    endcase

    unique case (issue_ex_output.payload.ctrl.operand_b)
      OPERAND_B_RS2: execute_operand_b = issue_ex_output.payload.rs2_data;
      OPERAND_B_IMM: execute_operand_b = issue_ex_output.payload.immediate;
      default:       execute_operand_b = '0;
    endcase
  end

  alu u_alu (
      .lhs_i(execute_operand_a),
      .rhs_i(execute_operand_b),
      .op_i(issue_ex_output.payload.ctrl.alu_op),
      .result_o(execute_result)
  );

  bru u_bru (
      .lhs_i(issue_ex_output.payload.rs1_data),
      .rhs_i(issue_ex_output.payload.rs2_data),
      .branch_op_i(issue_ex_output.payload.ctrl.branch_op),
      .jump_i(issue_ex_output.payload.ctrl.jump),
      .indirect_i(
          issue_ex_output.payload.ctrl.jump &&
          (issue_ex_output.payload.ctrl.operand_a == OPERAND_A_RS1)
      ),
      .target_i(execute_result),
      .taken_o(execute_redirect),
      .target_o(redirect_pc)
  );

  always_comb begin
    redirect_valid = issue_ex_output.valid && ex_mem_input.ready &&
        execute_redirect && !issue_ex_output.payload.ctrl.illegal;

    ex_mem_input.valid = issue_ex_output.valid;
    ex_mem_input.payload = '{
        pc: issue_ex_output.payload.pc,
        rd: issue_ex_output.payload.rd,
        result: execute_result,
        store_data: issue_ex_output.payload.rs2_data,
        memory_size: issue_ex_output.payload.ctrl.memory_size,
        result_source: issue_ex_output.payload.ctrl.result_source,
        reg_write: issue_ex_output.payload.ctrl.reg_write,
        memory_read: issue_ex_output.payload.ctrl.memory_read,
        memory_write: issue_ex_output.payload.ctrl.memory_write,
        memory_unsigned: issue_ex_output.payload.ctrl.memory_unsigned,
        illegal: issue_ex_output.payload.ctrl.illegal
    };
    issue_ex_output.ready = ex_mem_input.ready;
  end

  lsu u_lsu (
      .byte_offset_i(ex_mem_output.payload.result[1:0]),
      .store_data_i(ex_mem_output.payload.store_data),
      .read_data_i(dmem_rsp_i.data),
      .size_i(ex_mem_output.payload.memory_size),
      .unsigned_i(ex_mem_output.payload.memory_unsigned),
      .write_data_o(memory_write_data),
      .write_strb_o(memory_write_strb),
      .load_data_o(memory_load_data),
      .misaligned_o(memory_misaligned)
  );

  always_comb begin
    memory_access = ex_mem_output.payload.memory_read || ex_mem_output.payload.memory_write;
    memory_request = memory_access && !ex_mem_output.payload.illegal && !memory_misaligned;

    dmem_req_valid_o = ex_mem_output.valid && memory_request && !memory_request_sent_r;
    dmem_req_o = '{
        addr: ex_mem_output.payload.result,
        write: ex_mem_output.payload.memory_write,
        data: memory_write_data,
        strb: memory_write_strb
    };

    dmem_rsp_ready_o = 1'b0;
    ex_mem_output.ready = 1'b0;
    mem_wb_input.valid = 1'b0;

    unique case (ex_mem_output.payload.result_source)
      RESULT_ALU: memory_result = ex_mem_output.payload.result;
      RESULT_MEM: memory_result = memory_load_data;
      RESULT_PC_STEP: memory_result = ex_mem_output.payload.pc + word_t'(ILEN / 8);
      default: memory_result = '0;
    endcase

    mem_wb_input.payload = '{
        pc: ex_mem_output.payload.pc,
        rd: ex_mem_output.payload.rd,
        result: memory_result,
        reg_write: ex_mem_output.payload.reg_write,
        illegal:
        ex_mem_output.payload.illegal
        || (
        memory_access && memory_misaligned
        ) || (
        memory_request_sent_r && dmem_rsp_valid_i && dmem_rsp_i.error
        )
    };

    if (ex_mem_output.valid) begin
      if (!memory_request) begin
        mem_wb_input.valid  = 1'b1;
        ex_mem_output.ready = mem_wb_input.ready;
      end else if (memory_request_sent_r) begin
        mem_wb_input.valid = dmem_rsp_valid_i;
        dmem_rsp_ready_o = mem_wb_input.ready;
        ex_mem_output.ready = dmem_rsp_valid_i && mem_wb_input.ready;
      end
    end

    memory_request_fire  = dmem_req_valid_o && dmem_req_ready_i;
    memory_response_fire = dmem_rsp_valid_i && dmem_rsp_ready_o;
  end

  always_ff @(posedge clk_i or negedge rst_n_i) begin
    if (!rst_n_i) begin
      memory_request_sent_r <= 1'b0;
    end else if (memory_response_fire) begin
      memory_request_sent_r <= 1'b0;
    end else if (memory_request_fire) begin
      memory_request_sent_r <= 1'b1;
    end
  end

  always_comb begin
    mem_wb_output.ready = 1'b1;

    regfile_write = mem_wb_output.valid &&
        mem_wb_output.payload.reg_write &&
        !mem_wb_output.payload.illegal;

    retire_valid_o = mem_wb_output.valid;
    retire_lane_o = '{
        pc: mem_wb_output.payload.pc,
        rd: mem_wb_output.payload.rd,
        data: mem_wb_output.payload.result,
        write: regfile_write,
        illegal: mem_wb_output.payload.illegal
    };
  end

endmodule
