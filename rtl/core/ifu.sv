`include "cc/assertions.svh"

module ifu
  import riscv_pkg::*;
  import core_pkg::*;
#(
    parameter addr_t RESET_VECTOR = addr_t'(arch_pkg::ARCH.reset_vector)
) (
    input logic  clk_i,
    input logic  rst_n_i,
    input logic  redirect_valid_i,
    input addr_t redirect_pc_i,

    handshake_if.source imem_req,
    handshake_if.sink   imem_resp,
    handshake_if.source if_id
);
  localparam addr_t InstrBytes = addr_t'(ILEN / 8);

  typedef enum logic [1:0] {
    IDLE,
    HOLD_REQ,
    WAIT_RESP
  } state_e;

  state_e state_r;
  addr_t  next_pc_r;
  addr_t  transaction_pc_r;
  logic   stale_r;
  logic req_fire, req_stale;
  logic resp_fire, resp_stale;

  handshake_if #(.payload_t(if_id_payload_t)) if_id_in ();

  flushable_pipe #(
      .payload_t(if_id_payload_t)
  ) u_if_id (
      .clk_i  (clk_i),
      .rst_n_i(rst_n_i),
      .flush_i(redirect_valid_i),
      .in     (if_id_in),
      .out    (if_id)
  );

  always_comb begin
    resp_stale = stale_r || redirect_valid_i;
    req_stale  = (state_r == HOLD_REQ) && resp_stale;
  end

  always_comb begin
    imem_resp.ready = (state_r == WAIT_RESP) && (resp_stale || if_id_in.ready);
  end

  always_comb begin
    if_id_in.valid = (state_r == WAIT_RESP) && imem_resp.valid && !resp_stale;
    if_id_in.payload = '{
        pc: transaction_pc_r,
        instr: imem_resp.payload.data,
        error: imem_resp.payload.error
    };
  end

  always_comb begin
    resp_fire = imem_resp.valid && imem_resp.ready;
    imem_req.valid = rst_n_i && ((state_r == HOLD_REQ) ||
        (!redirect_valid_i && ((state_r == IDLE) || resp_fire)));
    imem_req.payload = '{addr: (state_r == HOLD_REQ) ? transaction_pc_r : next_pc_r};
  end

  always_comb begin
    req_fire = imem_req.valid && imem_req.ready;
  end

  always_ff @(posedge clk_i or negedge rst_n_i) begin
    if (!rst_n_i) begin
      state_r          <= IDLE;
      next_pc_r        <= RESET_VECTOR;
      transaction_pc_r <= '0;
      stale_r          <= 1'b0;
    end else begin
      if (redirect_valid_i) begin
        next_pc_r <= redirect_pc_i;
      end else if (req_fire && !req_stale) begin
        next_pc_r <= imem_req.payload.addr + InstrBytes;
      end

      if (imem_req.valid) begin
        state_r          <= req_fire ? WAIT_RESP : HOLD_REQ;
        transaction_pc_r <= imem_req.payload.addr;
        stale_r          <= req_stale;
      end else if (resp_fire) begin
        state_r <= IDLE;
        stale_r <= 1'b0;
      end else if (redirect_valid_i && (state_r == WAIT_RESP)) begin
        stale_r <= 1'b1;
      end
    end
  end

  `ASSERT(ReqStable, imem_req.valid && !imem_req.ready |=> imem_req.valid && $stable
                     (imem_req.payload))
  `ASSERT(OneOutstanding, req_fire && (state_r == WAIT_RESP) |-> resp_fire)
endmodule
