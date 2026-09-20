interface handshake_if #(
    parameter type payload_t = logic
);

  logic valid;
  logic ready;
  payload_t payload;

  modport sink(input valid, input payload, output ready);
  modport source(input ready, output valid, output payload);
  modport monitor(input valid, input ready, input payload);

endinterface
