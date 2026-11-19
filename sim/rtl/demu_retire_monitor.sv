module demu_retire_monitor
  import core_pkg::*;
  import demu_dpi_pkg::*;
(
    input logic clk_i,
    input logic rst_n_i,

    valid_if.monitor retire
);

  chandle dpi_handle;

  initial begin
    dpi_handle = demu_context();
    if (dpi_handle == null) begin
      $fatal(1, "DEMU DPI context is not bound");
    end
  end

  always_ff @(posedge clk_i or negedge rst_n_i) begin
    if (rst_n_i) begin
      if (retire.valid) begin
        demu_retire(dpi_handle, retire.payload.pc, retire.payload.instr, {3'b000, retire.payload.rd
                    }, retire.payload.data, retire.payload.write, retire.payload.illegal);
      end
    end
  end

endmodule
