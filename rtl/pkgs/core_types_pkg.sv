package core_types_pkg;

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
    ALU_SLTU = 4'b1001
  } alu_op_e;

  typedef enum logic [1:0] {
    OPERAND_A_ZERO = 2'b00,
    OPERAND_A_RS1  = 2'b01,
    OPERAND_A_PC   = 2'b10
  } operand_a_sel_e;

  typedef enum logic [1:0] {
    OPERAND_B_ZERO      = 2'b00,
    OPERAND_B_RS2       = 2'b01,
    OPERAND_B_IMM = 2'b10
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
    RESULT_MEM  = 2'b01,
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

endpackage
