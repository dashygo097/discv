package riscv_pkg;
  localparam int unsigned ILEN = 32;

  typedef logic [ILEN-1:0] instr_t;
  typedef logic [4:0] reg_addr_t;

  typedef enum logic [6:0] {
    OPCODE_LOAD     = 7'b0000011,
    OPCODE_MISC_MEM = 7'b0001111,
    OPCODE_OP_IMM   = 7'b0010011,
    OPCODE_AUIPC    = 7'b0010111,
    OPCODE_STORE    = 7'b0100011,
    OPCODE_OP       = 7'b0110011,
    OPCODE_LUI      = 7'b0110111,
    OPCODE_BRANCH   = 7'b1100011,
    OPCODE_JALR     = 7'b1100111,
    OPCODE_JAL      = 7'b1101111,
    OPCODE_SYSTEM   = 7'b1110011
  } opcode_e;

  typedef struct packed {
    logic [31:25] funct7;
    reg_addr_t    rs2;
    reg_addr_t    rs1;
    logic [14:12] funct3;
    reg_addr_t    rd;
    opcode_e      opcode;
  } instr_rtype_t;

  typedef struct packed {
    logic [31:20] imm_11_0;
    reg_addr_t    rs1;
    logic [14:12] funct3;
    reg_addr_t    rd;
    opcode_e      opcode;
  } instr_itype_t;

  typedef struct packed {
    logic [31:25] imm_11_5;
    reg_addr_t    rs2;
    reg_addr_t    rs1;
    logic [14:12] funct3;
    logic [11:7]  imm_4_0;
    opcode_e      opcode;
  } instr_stype_t;

  typedef struct packed {
    logic         imm_12;
    logic [30:25] imm_10_5;
    reg_addr_t    rs2;
    reg_addr_t    rs1;
    logic [14:12] funct3;
    logic [11:8]  imm_4_1;
    logic         imm_11;
    opcode_e      opcode;
  } instr_btype_t;

  typedef struct packed {
    logic         imm_20;
    logic [30:21] imm_10_1;
    logic         imm_11;
    logic [19:12] imm_19_12;
    reg_addr_t    rd;
    opcode_e      opcode;
  } instr_jtype_t;

  typedef struct packed {
    logic [31:12] imm_31_12;
    reg_addr_t    rd;
    opcode_e      opcode;
  } instr_utype_t;

endpackage
