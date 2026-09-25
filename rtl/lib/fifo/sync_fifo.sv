module sync_fifo #(
    parameter type payload_t = logic,
    parameter int unsigned DEPTH
) (
    input logic clk_i,
    input logic rst_n_i,

    handshake_if.sink   in,
    handshake_if.source out,

    output logic empty_o,
    output logic full_o
);
  localparam int unsigned PTR_WIDTH = DEPTH > 1 ? $clog2(DEPTH) : 1;
  localparam int unsigned CNT_WIDTH = DEPTH > 1 ? $clog2(DEPTH + 1) : 1;

  payload_t storage[DEPTH];

  logic [CNT_WIDTH - 1:0] counter_r;
  logic [PTR_WIDTH - 1:0] w_ptr_r;
  logic [PTR_WIDTH - 1:0] r_ptr_r;

  logic push;
  logic pop;

  always_comb begin
    empty_o = (counter_r == '0);
    full_o = (counter_r == CNT_WIDTH'(DEPTH));

    out.valid = !empty_o;
    out.payload = storage[r_ptr_r];

    pop = out.valid && out.ready;

    in.ready = !full_o || pop;
    push = in.valid && in.ready;
  end

  always_ff @(posedge clk_i or negedge rst_n_i) begin
    if (!rst_n_i) begin
      counter_r <= '0;
      w_ptr_r   <= '0;
      r_ptr_r   <= '0;
    end else begin
      if (push) begin
        storage[w_ptr_r] <= in.payload;

        if (w_ptr_r == PTR_WIDTH'(DEPTH - 1)) begin
          w_ptr_r <= '0;
        end else begin
          w_ptr_r <= w_ptr_r + '1;
        end
      end

      if (pop) begin
        if (r_ptr_r == PTR_WIDTH'(DEPTH - 1)) begin
          r_ptr_r <= '0;
        end else begin
          r_ptr_r <= r_ptr_r + '1;
        end
      end

      case ({
        push, pop
      })
        2'b10:   counter_r <= counter_r + 1'b1;
        2'b01:   counter_r <= counter_r - 1'b1;
        default: counter_r <= counter_r;
      endcase
    end
  end
endmodule
