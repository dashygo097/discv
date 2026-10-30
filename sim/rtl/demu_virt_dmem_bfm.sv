module demu_virt_dmem_bfm
  import core_types_pkg::*;
  import demu_dpi_pkg::*;
#(
    parameter int unsigned PORT
) (
    input logic clk_i,
    input logic rst_n_i,

    handshake_if.sink   request,
    handshake_if.source response
);

  typedef enum logic [1:0] {
    IDLE,
    WAIT_DEVICE,
    HOLD_RESPONSE
  } state_e;

  chandle dpi_handle;
  state_e state_r;
  longint unsigned transaction_r;
  dmem_rsp_t response_r;

  function automatic int start_transaction(input dmem_req_t payload,
                                           output longint unsigned transaction,
                                           output dmem_rsp_t transaction_response);
    int unsigned data;
    bit error;

    data = '0;
    error = '0;
    transaction_response = '0;

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
      transaction_response = '{data: data, error: error};
    end
  endfunction

  initial begin
    dpi_handle = demu_context();
    if (dpi_handle == null) begin
      $fatal(1, "DEMU DPI context is not bound");
    end
  end

  always_comb begin
    request.ready = state_r == IDLE || (state_r == HOLD_RESPONSE && response.ready);

    response.valid = state_r == HOLD_RESPONSE;
    response.payload = response_r;
  end

  always_ff @(posedge clk_i or negedge rst_n_i) begin
    if (!rst_n_i) begin
      state_r       <= IDLE;
      transaction_r <= '0;
      response_r    <= '0;
    end else begin
      if (request.valid && request.ready) begin
        longint unsigned transaction;
        dmem_rsp_t transaction_response;

        if (state_r == HOLD_RESPONSE) begin
          if (demu_complete(dpi_handle, transaction_r) != 0) begin
            $fatal(1, "Failed to complete data transaction");
          end
        end

        case (start_transaction(
            request.payload, transaction, transaction_response
        ))
          -1: $fatal(1, "Failed to start data transaction");
          0:  state_r <= WAIT_DEVICE;
          1: begin
            response_r <= transaction_response;
            state_r    <= HOLD_RESPONSE;
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
              0:  ;
              1: begin
                response_r <= '{data: data, error: error};
                state_r    <= HOLD_RESPONSE;
              end
              default: $fatal(1, "Invalid data transaction poll status");
            endcase
          end

          HOLD_RESPONSE: begin
            if (response.valid && response.ready) begin
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
