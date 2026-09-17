package riscv;
  localparam int unsigned XLEN = cfg::XLEN;
  localparam int unsigned ILEN = 32;

  typedef struct packed {
    logic [31:25] funct7;
    logic [24:20] rs2;
    logic [19:15] rs1;
    logic [14:12] funct3;
    logic [11:7]  rd;
    logic [6:0]   opcode;
  } instr_rtype_t;

  typedef struct packed {
    logic [31:20] imm_11_0;
    logic [19:15] rs1;
    logic [14:12] funct3;
    logic [11:7]  rd;
    logic [6:0]   opcode;
  } instr_itype_t;

  typedef struct packed {
    logic [31:25] imm_11_5;
    logic [24:20] rs2;
    logic [19:15] rs1;
    logic [14:12] funct3;
    logic [11:7]  imm_4_0;
    logic [6:0]   opcode;
  } instr_stype_t;

  typedef struct packed {
    logic imm_12;
    logic [30:25] imm_10_5;
    logic [24:20] rs2;
    logic [19:15] rs1;
    logic [14:12] funct3;
    logic [11:8] imm_4_1;
    logic imm_11;
    logic [6:0] opcode;
  } instr_btype_t;

  typedef struct packed {
    logic imm_20;
    logic [30:21] imm_10_1;
    logic imm_11;
    logic [19:12] imm_19_12;
    logic [11:7] rd;
    logic [6:0] opcode;
  } instr_jtype_t;

  typedef struct packed {
    logic [31:12] imm_31_12;
    logic [11:7]  rd;
    logic [6:0]   opcode;
  } instr_utype_t;

endpackage
