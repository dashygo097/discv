interface valid_if #(
    parameter type payload_t = logic
);

  logic valid;
  payload_t payload;

  modport sink(input valid, input payload);
  modport source(output valid, output payload);
  modport monitor(input valid, input payload);

endinterface
