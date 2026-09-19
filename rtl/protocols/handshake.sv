interface handshake_if #(
    parameter type payload_t = logic
);

  logic valid;
  logic ready;
  payload_t payload;

  modport source(input ready, output valid, output payload);
  modport sink(input valid, input payload, output ready);
  modport monitor(input valid, input ready, input payload);

endinterface
