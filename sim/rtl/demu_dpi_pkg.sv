`include "cc/register_bank.svh"

package demu_dpi_pkg;
  import riscv_pkg::*;

  localparam int unsigned WordBytes = $bits(byte_enable_t);
  typedef `CC_REG_BANK_REQ_TYPE(addr_t, word_t, byte_enable_t) mem_req_t;

  typedef enum byte unsigned {
    MEM_OKAY        = 0,
    MEM_DECODE_ERR  = 1,
    MEM_SLAVE_ERR   = 2,
    MEM_MISALIGNED  = 3,
    MEM_UNSUPPORTED = 4
  } mem_status_e;

  typedef struct packed {
    word_t       data;
    mem_status_e status;
  } mem_resp_t;

  import "DPI-C" context function chandle demu_context();

  import "DPI-C" context function int demu_submit(
    input chandle dpi_handle,
    input int unsigned port,
    input bit write,
    input int unsigned address,
    input int unsigned data,
    input int unsigned strobe,
    input int unsigned size,
    output longint unsigned transaction
  );

  import "DPI-C" context function int demu_poll(
    input chandle dpi_handle,
    input longint unsigned transaction,
    output int unsigned data,
    output byte unsigned status
  );

  import "DPI-C" context function int demu_complete(
    input chandle dpi_handle,
    input longint unsigned transaction
  );

  import "DPI-C" context function void demu_retire(
    input chandle dpi_handle,
    input int unsigned pc,
    input int unsigned instruction,
    input byte unsigned rd,
    input int unsigned data,
    input bit write,
    input bit illegal
  );

endpackage
