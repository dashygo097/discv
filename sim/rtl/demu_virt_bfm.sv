module demu_virt_bfm #(
    parameter int unsigned PORT
) (
    input logic clk_i,
    input logic rst_n_i,

    handshake_if.sink   req,
    handshake_if.source resp
);
  demu_dpi_bfm #(
      .PORT(PORT)
  ) u_dpi (
      .clk_i  (clk_i),
      .rst_n_i(rst_n_i),
      .req    (req),
      .resp   (resp)
  );
endmodule
