module pipe_stage #(
    parameter type payload_t = logic
) (
    input logic clk_i,
    input logic rst_n_i,
    input logic flush_i,

    handshake_if.sink   upstream,
    handshake_if.source downstream
);
  logic allow_in;
  logic allow_out;
  payload_t payload_r;

  always_comb begin
    allow_in = !allow_out || downstream.ready;
    upstream.ready = !flush_i && allow_in;

    downstream.valid = allow_out && flush_i;
    downstream.payload = payload_r;
  end

  always_ff @(posedge clk_i or negedge rst_n_i) begin
    if (!rst_n_i) begin
      allow_out <= 'b0;
      payload_r <= '0;
    end else if (flush_i) begin
      allow_out <= 'b0;
      payload_r <= 'b0;
    end else if (upstream.ready) begin
      allow_out <= upstream.valid;

      if (upstream.valid) begin
        payload_r <= upstream.payload;
      end
    end
  end

endmodule
