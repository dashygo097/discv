`include "cc/assertions.svh"
`include "cc/registers.svh"

module virt_to_axi5_lite
  import axi5_pkg::*;
  import core_pkg::*;
  import riscv_pkg::*;
(
    handshake_if.sink   req,
    handshake_if.source resp,
    axi5_lite_if.source axi
);
  typedef enum logic [1:0] {
    IDLE,
    SEND_REQ,
    WAIT_RESP
  } state_e;

  localparam int unsigned WordBytes = $bits(byte_enable_t);
  localparam addr_t WordMask = addr_t'(WordBytes - 1);

  state_e state_r, state_d;
  dmem_req_t req_r;
  logic aw_sent_r, w_sent_r;
  logic req_fire, resp_fire, aw_fire, w_fire, ar_fire;

  always_comb begin
    req.ready   = axi.ARESETn && state_r == IDLE;
    axi.AWVALID = axi.ARESETn && state_r == SEND_REQ && req_r.write && !aw_sent_r;
    axi.AWADDR  = req_r.addr & ~WordMask;
    axi.WVALID  = axi.ARESETn && state_r == SEND_REQ && req_r.write && !w_sent_r;
    axi.WDATA   = req_r.data;
    axi.WSTRB   = req_r.strb;
    axi.ARVALID = axi.ARESETn && state_r == SEND_REQ && !req_r.write;
    axi.ARADDR  = req_r.addr & ~WordMask;
  end

  always_comb begin
    req_fire  = req.valid && req.ready;
    aw_fire   = axi.AWVALID && axi.AWREADY;
    w_fire    = axi.WVALID && axi.WREADY;
    ar_fire   = axi.ARVALID && axi.ARREADY;
    resp_fire = resp.valid && resp.ready;
  end

  always_comb begin
    axi.BREADY = state_r == WAIT_RESP && req_r.write && resp.ready;
    axi.RREADY = state_r == WAIT_RESP && !req_r.write && resp.ready;
  end

  always_comb begin
    resp.valid = state_r == WAIT_RESP && (req_r.write ? axi.BVALID : axi.RVALID);
    resp.payload = '{
        data: req_r.write ? '0 : word_t'(axi.RDATA),
        error: req_r.write ? axi.BRESP != BRESP_OKAY : axi.RRESP != RRESP_OKAY
    };
  end

  always_comb begin
    state_d = state_r;
    unique case (state_r)
      IDLE: if (req_fire) state_d = SEND_REQ;
      SEND_REQ: begin
        if (req_r.write ? ((aw_sent_r || aw_fire) && (w_sent_r || w_fire)) : ar_fire) begin
          state_d = WAIT_RESP;
        end
      end
      WAIT_RESP: if (resp_fire) state_d = IDLE;
      default: state_d = IDLE;
    endcase
  end

  `REG_ARSTN(state_r, state_d, IDLE, axi.ACLK, axi.ARESETn)
  `REG_CE(req_r, req.payload, req_fire, axi.ACLK)
  `REG_CE_CLR_ARSTN(aw_sent_r, 1'b1, aw_fire, req_fire, 1'b0, axi.ACLK, axi.ARESETn)
  `REG_CE_CLR_ARSTN(w_sent_r, 1'b1, w_fire, req_fire, 1'b0, axi.ACLK, axi.ARESETn)

  always_comb begin
    axi.AWAKEUP    = 1'b0;
    axi.AWPROT     = '0;
    axi.AWSIZE     = size_e'($clog2(WordBytes));
    axi.AWID       = '0;
    axi.AWIDUNQ    = 1'b0;
    axi.AWUSER     = '0;
    axi.AWTRACE    = 1'b0;
    axi.AWSUBSYSID = '0;
    axi.WUSER      = '0;
    axi.WTRACE     = 1'b0;
    axi.ARPROT     = '0;
    axi.ARSIZE     = size_e'($clog2(WordBytes));
    axi.ARID       = '0;
    axi.ARIDUNQ    = 1'b0;
    axi.ARUSER     = '0;
    axi.ARTRACE    = 1'b0;
    axi.ARSUBSYSID = '0;
  end

  `ASSERT_INIT(AxiWidths, $bits(axi.AWADDR) == $bits(addr_t) && $bits(axi.WDATA) == $bits(word_t)
               && $bits(axi.WSTRB) == WordBytes)
  `ASSERT_INIT(
      AxiOptions,
      axi.O_EN_STRB && !axi.O_EN_SIZE && !axi.OI_EN_PROT && !axi.OO_EN_ID && !axi.OO_EN_IDUNQ && !axi.O_EN_USER && !axi.C_EN_TRACE && !axi.O_EN_WAKEUP && !axi.O_EN_SUBSYSTEM)
  `ASSERT(WriteAddrStable, axi.AWVALID && !axi.AWREADY |=> axi.AWVALID && $stable(axi.AWADDR),
          axi.ACLK, axi.ARESETn)
  `ASSERT(WriteDataStable, axi.WVALID && !axi.WREADY |=> axi.WVALID && $stable
                           ({axi.WDATA, axi.WSTRB}), axi.ACLK, axi.ARESETn)
  `ASSERT(ReadAddrStable, axi.ARVALID && !axi.ARREADY |=> axi.ARVALID && $stable(axi.ARADDR),
          axi.ACLK, axi.ARESETn)
endmodule
