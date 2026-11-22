`include "cc/assertions.svh"

module demu_dpi_bfm
  import demu_dpi_pkg::*;
#(
    parameter int unsigned PORT
) (
    input logic clk_i,
    input logic rst_n_i,

    handshake_if.sink   req,
    handshake_if.source resp
);
  typedef enum logic [1:0] {
    IDLE,
    WAIT_DEVICE,
    HOLD_RESP
  } state_e;

  chandle dpi_handle;
  state_e state_r;
  longint unsigned transaction_r;
  mem_resp_t resp_r;
  logic req_fire, resp_fire;

  initial begin
    dpi_handle = demu_context();
    if (dpi_handle == null) $fatal(1, "DEMU DPI context is not bound");
  end

  always_comb begin
    resp.valid   = state_r == HOLD_RESP;
    resp.payload = resp_r;
  end

  always_comb begin
    resp_fire = resp.valid && resp.ready;
    req.ready = rst_n_i && ((state_r == IDLE) || resp_fire);
  end

  always_comb begin
    req_fire = req.valid && req.ready;
  end

  always_ff @(posedge clk_i or negedge rst_n_i) begin
    if (!rst_n_i) begin
      state_r       <= IDLE;
      transaction_r <= '0;
      resp_r        <= '0;
    end else begin
      if (resp_fire) begin
        if (demu_complete(dpi_handle, transaction_r) != 0) begin
          $fatal(1, "DEMU port %0d failed to complete transaction %0d", PORT, transaction_r);
        end
        state_r <= IDLE;
      end

      if (req_fire || (state_r == WAIT_DEVICE)) begin
        longint unsigned transaction;
        int unsigned data;
        byte unsigned status;

        transaction = transaction_r;
        if (req_fire) begin
          if (demu_submit(
                  dpi_handle,
                  PORT,
                  req.payload.write,
                  req.payload.addr,
                  req.payload.data,
                  32'(req.payload.strb),
                  WordBytes,
                  transaction
              ) != 0) begin
            $fatal(1, "DEMU port %0d failed to submit address %h", PORT, req.payload.addr);
          end
          transaction_r <= transaction;
        end

        case (demu_poll(
            dpi_handle, transaction, data, status
        ))
          0: state_r <= WAIT_DEVICE;
          1: begin
            resp_r  <= '{data: data, status: mem_status_e'(status)};
            state_r <= HOLD_RESP;
          end
          default: $fatal(1, "DEMU port %0d failed to poll transaction %0d", PORT, transaction);
        endcase
      end
    end
  end

  `ASSERT(RespStable, resp.valid && !resp.ready |=> resp.valid && $stable(resp.payload))
endmodule
