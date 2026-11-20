module demu_virt_dmem_bfm
  import core_pkg::*;
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
  dmem_resp_t resp_r;

  function automatic int start_transaction(input dmem_req_t payload,
                                           output longint unsigned transaction,
                                           output dmem_resp_t transaction_resp);
    int unsigned data;
    bit error;

    data = '0;
    error = '0;
    transaction_resp = '0;

    if (demu_submit(
            dpi_handle,
            PORT,
            payload.write,
            payload.addr,
            payload.data,
            32'(payload.strb),
            32'(4),
            transaction
        ) != 0) begin
      start_transaction = -1;
    end else begin
      start_transaction = demu_poll(dpi_handle, transaction, data, error);
      transaction_resp  = '{data: data, error: error};
    end
  endfunction

  initial begin
    dpi_handle = demu_context();
    if (dpi_handle == null) begin
      $fatal(1, "DEMU DPI context is not bound");
    end
  end

  always_comb begin
    req.ready = state_r == IDLE || (state_r == HOLD_RESP && resp.ready);

    resp.valid = state_r == HOLD_RESP;
    resp.payload = resp_r;
  end

  always_ff @(posedge clk_i or negedge rst_n_i) begin
    if (!rst_n_i) begin
      state_r       <= IDLE;
      transaction_r <= '0;
      resp_r        <= '0;
    end else begin
      if (req.valid && req.ready) begin
        longint unsigned transaction;
        dmem_resp_t transaction_resp;

        if (state_r == HOLD_RESP) begin
          if (demu_complete(dpi_handle, transaction_r) != 0) begin
            $fatal(1, "Failed to complete data transaction");
          end
        end

        case (start_transaction(
            req.payload, transaction, transaction_resp
        ))
          -1: $fatal(1, "Failed to start data transaction");
          0: state_r <= WAIT_DEVICE;
          1: begin
            resp_r  <= transaction_resp;
            state_r <= HOLD_RESP;
          end
          default: $fatal(1, "Invalid data transaction poll status");
        endcase
        transaction_r <= transaction;
      end else begin
        unique case (state_r)
          WAIT_DEVICE: begin
            int unsigned data;
            bit error;

            case (demu_poll(
                dpi_handle, transaction_r, data, error
            ))
              -1: $fatal(1, "Failed to poll data transaction");
              0: ;
              1: begin
                resp_r  <= '{data: data, error: error};
                state_r <= HOLD_RESP;
              end
              default: $fatal(1, "Invalid data transaction poll status");
            endcase
          end

          HOLD_RESP: begin
            if (resp.valid && resp.ready) begin
              if (demu_complete(dpi_handle, transaction_r) != 0) begin
                $fatal(1, "Failed to complete data transaction");
              end
              state_r <= IDLE;
            end
          end

          default: state_r <= IDLE;
        endcase
      end
    end
  end

endmodule
