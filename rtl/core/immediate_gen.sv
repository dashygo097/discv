module immediate_gen
  import riscv_pkg::*;
  import core_types_pkg::*;
#(
    parameter int unsigned XLEN = cfg_pkg::XLEN
) (
    input  logic         [ILEN-1:7]   instr_i,
    input  immediate_sel_e            sel_i,
    output logic           [XLEN-1:0] immediate_o
);

  always_comb begin
    immediate_o = '0;

    unique case (sel_i)
      IMM_I: immediate_o = {{(XLEN - 12) {instr_i[31]}}, instr_i[31:20]};
      IMM_S: immediate_o = {{(XLEN - 12) {instr_i[31]}}, instr_i[31:25], instr_i[11:7]};
      IMM_B:
      immediate_o = {
        {(XLEN - 13) {instr_i[31]}}, instr_i[31], instr_i[7], instr_i[30:25], instr_i[11:8], 1'b0
      };
      IMM_U: immediate_o = {{(XLEN - 32) {instr_i[31]}}, instr_i[31:12], 12'b0};
      IMM_J:
      immediate_o = {
        {(XLEN - 21) {instr_i[31]}}, instr_i[31], instr_i[19:12], instr_i[20], instr_i[30:21], 1'b0
      };
      IMM_CSR: immediate_o = {{(XLEN - 5) {1'b0}}, instr_i[19:15]};
      default: immediate_o = '0;
    endcase
  end

endmodule
