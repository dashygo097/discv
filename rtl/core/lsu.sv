module lsu
  import riscv_pkg::*;
  import core_types_pkg::*;
(
    input logic         [1:0] byte_offset_i,
    input word_t              store_data_i,
    input word_t              read_data_i,
    input memory_size_e       size_i,
    input logic               unsigned_i,

    output word_t        write_data_o,
    output byte_enable_t write_strb_o,
    output word_t        load_data_o,
    output logic         misaligned_o
);

  logic [ 7:0] selected_byte;
  logic [15:0] selected_half;

  always_comb begin
    unique case (byte_offset_i)
      2'b00: selected_byte = read_data_i[7:0];
      2'b01: selected_byte = read_data_i[15:8];
      2'b10: selected_byte = read_data_i[23:16];
      2'b11: selected_byte = read_data_i[31:24];
    endcase

    if (byte_offset_i[1]) begin
      selected_half = read_data_i[31:16];
    end else begin
      selected_half = read_data_i[15:0];
    end

    write_data_o = store_data_i << (8 * byte_offset_i);
    write_strb_o = '0;
    load_data_o  = '0;
    misaligned_o = 1'b0;

    unique case (size_i)
      MEM_BYTE: begin
        write_strb_o = byte_enable_t'(1) << byte_offset_i;

        if (unsigned_i) begin
          load_data_o = {{($bits(word_t) - 8) {1'b0}}, selected_byte};
        end else begin
          load_data_o = {{($bits(word_t) - 8) {selected_byte[7]}}, selected_byte};
        end
      end

      MEM_HALF: begin
        write_strb_o = byte_enable_t'(3) << byte_offset_i;
        misaligned_o = byte_offset_i[0];

        if (unsigned_i) begin
          load_data_o = {{($bits(word_t) - 16) {1'b0}}, selected_half};
        end else begin
          load_data_o = {{($bits(word_t) - 16) {selected_half[15]}}, selected_half};
        end
      end

      MEM_WORD: begin
        write_strb_o = '1;
        load_data_o  = read_data_i;
        misaligned_o = |byte_offset_i;
      end

      default: begin
        write_strb_o = '0;
        load_data_o  = '0;
        misaligned_o = 1'b1;
      end
    endcase
  end

endmodule
