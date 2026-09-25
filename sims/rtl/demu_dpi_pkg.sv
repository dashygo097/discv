package demu_dpi_pkg;

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
    output bit error
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
