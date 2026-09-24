module async_fifo #(
    parameter type payload_t = logic,
    parameter int unsigned DEPTH
) (
    input logic wclk_i,
    input logic wrst_n_i,

    handshake_if.sink in,

    input logic rclk_i,
    input logic rrst_n_i,

    handshake_if.source out,

    output logic empty_o,
    output logic full_o
);
  initial begin
    assert (DEPTH >= 2)
    else $fatal(1, "DEPTH must be at least 2");

    assert ((DEPTH & (DEPTH - 1)) == 0)
    else $fatal(1, "DEPTH must be a power of two");
  end

  localparam int unsigned ADDR_WIDTH = $clog2(DEPTH);
  localparam int unsigned PTR_WIDTH  = ADDR_WIDTH + 1;

  payload_t storage[DEPTH];

  // write
  logic [PTR_WIDTH - 1:0] wptr_r;
  logic [PTR_WIDTH - 1:0] wptr_gray_r;

  always_ff @(posedge wclk_i or negedge wrst_n_i) begin
    if (!wrst_n_i) begin
      wptr_r <= '0;
    end else begin
      if (in.valid && in.ready) begin
        wptr_r <= wptr_r + '1;
        storage[wptr_r[ADDR_WIDTH-1:0]] <= in.payload;
      end
    end
  end

  // read
  logic [PTR_WIDTH - 1:0] rptr_r;
  logic [PTR_WIDTH - 1:0] rptr_gray_r;

  always_ff @(posedge rclk_i or negedge rrst_n_i) begin
    if (!rrst_n_i) begin
      rptr_r <= '0;
    end else begin
      if (out.valid && out.ready) begin
        rptr_r <= rptr_r + '1;
      end
    end
  end

  // synchronization
  logic [PTR_WIDTH - 1:0] rptr_gray_meta_r;
  logic [PTR_WIDTH - 1:0] rptr_gray_sync_r;

  always_ff @(posedge wclk_i or negedge wrst_n_i) begin
    if (!wrst_n_i) begin
      rptr_gray_meta_r <= '0;
      rptr_gray_sync_r <= '0;
    end else begin
      rptr_gray_meta_r <= rptr_gray_r;
      rptr_gray_sync_r <= rptr_gray_meta_r;
    end
  end

  logic [PTR_WIDTH - 1:0] wptr_gray_meta_r;
  logic [PTR_WIDTH - 1:0] wptr_gray_sync_r;

  always_ff @(posedge rclk_i or negedge rrst_n_i) begin
    if (!rrst_n_i) begin
      wptr_gray_meta_r <= '0;
      wptr_gray_sync_r <= '0;
    end else begin
      wptr_gray_meta_r <= wptr_gray_r;
      wptr_gray_sync_r <= wptr_gray_meta_r;
    end
  end

  // comb
  always_comb begin
    wptr_gray_r = wptr_r ^ (wptr_r >> 1);
    rptr_gray_r = rptr_r ^ (rptr_r >> 1);

    full_o = (wptr_gray_r == (rptr_gray_sync_r ^ (PTR_WIDTH'(3) << (PTR_WIDTH - 2))));
    in.ready = !full_o;

    empty_o = rptr_gray_r == wptr_gray_sync_r;

    out.valid = !empty_o;
    out.payload = storage[rptr_r[ADDR_WIDTH-1:0]];
  end

endmodule
