package core_types_pkg;
  import riscv_pkg::*;

  typedef struct packed {addr_t addr;} imem_req_t;

  typedef struct packed {
    instr_t data;
    logic   error;
  } imem_rsp_t;

  typedef struct packed {
    addr_t        addr;
    logic         write;
    word_t        data;
    byte_enable_t strb;
  } dmem_req_t;

  typedef struct packed {
    word_t data;
    logic  error;
  } dmem_rsp_t;

  typedef struct packed {
    addr_t     pc;
    instr_t    instr;
    reg_addr_t rd;
    word_t     data;
    logic      write;
    logic      illegal;
  } retire_lane_t;

  typedef enum logic [3:0] {
    ALU_ADD  = 4'b0000,
    ALU_SUB  = 4'b0001,
    ALU_AND  = 4'b0010,
    ALU_OR   = 4'b0011,
    ALU_XOR  = 4'b0100,
    ALU_SLL  = 4'b0101,
    ALU_SRL  = 4'b0110,
    ALU_SRA  = 4'b0111,
    ALU_SLT  = 4'b1000,
    ALU_SLTU = 4'b1001,
    ALU_NONE = 4'b1111
  } alu_op_e;

  typedef enum logic [1:0] {
    OPERAND_A_ZERO = 2'b00,
    OPERAND_A_RS1  = 2'b01,
    OPERAND_A_PC   = 2'b10
  } operand_a_sel_e;

  typedef enum logic [1:0] {
    OPERAND_B_ZERO = 2'b00,
    OPERAND_B_RS2  = 2'b01,
    OPERAND_B_IMM  = 2'b10
  } operand_b_sel_e;

  typedef enum logic [2:0] {
    IMM_NONE = 3'b000,
    IMM_I    = 3'b001,
    IMM_S    = 3'b010,
    IMM_B    = 3'b011,
    IMM_U    = 3'b100,
    IMM_J    = 3'b101,
    IMM_CSR  = 3'b110
  } immediate_sel_e;

  typedef enum logic [2:0] {
    BR_NONE = 3'b000,
    BR_EQ   = 3'b001,
    BR_NE   = 3'b010,
    BR_LT   = 3'b011,
    BR_GE   = 3'b100,
    BR_LTU  = 3'b101,
    BR_GEU  = 3'b110
  } branch_op_e;

  typedef enum logic [1:0] {
    MEM_BYTE = 2'b00,
    MEM_HALF = 2'b01,
    MEM_WORD = 2'b10
  } memory_size_e;

  typedef enum logic [1:0] {
    RESULT_ALU     = 2'b00,
    RESULT_MEM     = 2'b01,
    RESULT_PC_STEP = 2'b10,
    RESULT_CSR     = 2'b11
  } result_source_e;

  typedef struct packed {
    alu_op_e        alu_op;
    operand_a_sel_e operand_a;
    operand_b_sel_e operand_b;
    immediate_sel_e immediate;
    branch_op_e     branch_op;
    memory_size_e   memory_size;
    result_source_e result_source;
    logic           rs1_read;
    logic           rs2_read;
    logic           reg_write;
    logic           memory_read;
    logic           memory_write;
    logic           memory_unsigned;
    logic           jump;
    logic           serialize;
    logic           illegal;
  } decode_ctrl_t;

  function automatic decode_ctrl_t make_decode_ctrl(
      input alu_op_e alu_op = ALU_NONE, input operand_a_sel_e operand_a = OPERAND_A_ZERO,
      input operand_b_sel_e operand_b = OPERAND_B_ZERO, input immediate_sel_e immediate = IMM_NONE,
      input branch_op_e branch_op = BR_NONE, input memory_size_e memory_size = MEM_WORD,
      input result_source_e result_source = RESULT_ALU, input logic rs1_read = 1'b0,
      input logic rs2_read = 1'b0, input logic reg_write = 1'b0, input logic memory_read = 1'b0,
      input logic memory_write = 1'b0, input logic memory_unsigned = 1'b0, input logic jump = 1'b0,
      input logic serialize = 1'b0, input logic illegal = 1'b0);
    make_decode_ctrl = '{
        alu_op: alu_op,
        operand_a: operand_a,
        operand_b: operand_b,
        immediate: immediate,
        branch_op: branch_op,
        memory_size: memory_size,
        result_source: result_source,
        rs1_read: rs1_read,
        rs2_read: rs2_read,
        reg_write: reg_write,
        memory_read: memory_read,
        memory_write: memory_write,
        memory_unsigned: memory_unsigned,
        jump: jump,
        serialize: serialize,
        illegal: illegal
    };
  endfunction

  typedef struct packed {
    addr_t  pc;
    instr_t instr;
    logic   error;
  } if_id_payload_t;

  typedef struct packed {
    addr_t        pc;
    instr_t       instr;
    reg_addr_t    rs1;
    reg_addr_t    rs2;
    reg_addr_t    rd;
    word_t        immediate;
    decode_ctrl_t ctrl;
  } id_issue_payload_t;

  typedef struct packed {
    addr_t        pc;
    instr_t       instr;
    reg_addr_t    rd;
    word_t        rs1_data;
    word_t        rs2_data;
    word_t        immediate;
    decode_ctrl_t ctrl;
  } issue_ex_payload_t;

  typedef struct packed {
    addr_t          pc;
    instr_t         instr;
    reg_addr_t      rd;
    word_t          result;
    word_t          store_data;
    memory_size_e   memory_size;
    result_source_e result_source;
    logic           reg_write;
    logic           memory_read;
    logic           memory_write;
    logic           memory_unsigned;
    logic           illegal;
  } ex_mem_payload_t;

  typedef struct packed {
    addr_t     pc;
    instr_t    instr;
    reg_addr_t rd;
    word_t     result;
    logic      reg_write;
    logic      illegal;
  } mem_wb_payload_t;

endpackage
