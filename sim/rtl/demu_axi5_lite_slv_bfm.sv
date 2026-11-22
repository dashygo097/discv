`include "cc/assertions.svh"
`include "cc/registers.svh"

module demu_axi5_lite_slv_bfm
  import axi5_pkg::*;
  import demu_dpi_pkg::*;
  import riscv_pkg::*;
#(
    parameter int unsigned PORT
) (
    axi5_lite_if.sink axi
);
  handshake_if #(.payload_t(mem_req_t)) req ();
  handshake_if #(.payload_t(mem_resp_t)) resp ();

  addr_t aw_addr_r, ar_addr_r;
  word_t w_data_r;
  byte_enable_t w_strb_r;
  logic aw_valid_r, ar_valid_r, w_valid_r;
  logic aw_fire, ar_fire, w_fire;
  logic write_pending, prefer_write_r, select_write, stage_req;

  mem_req_t req_r, next_req;
  logic req_valid_r, active_r, write_r;
  logic req_fire, resp_fire;

  always_comb begin
    axi.AWREADY = axi.ARESETn && !aw_valid_r;
    axi.WREADY  = axi.ARESETn && !w_valid_r;
    axi.ARREADY = axi.ARESETn && !ar_valid_r;
  end

  always_comb begin
    aw_fire = axi.AWVALID && axi.AWREADY;
    w_fire = axi.WVALID && axi.WREADY;
    ar_fire = axi.ARVALID && axi.ARREADY;

    write_pending = aw_valid_r && w_valid_r;
    select_write = write_pending && (!ar_valid_r || prefer_write_r);
    stage_req = !req_valid_r && (write_pending || ar_valid_r);
    next_req = '{
        addr: select_write ? aw_addr_r : ar_addr_r,
        write: select_write,
        data: select_write ? w_data_r : '0,
        strb: select_write ? w_strb_r : '0
    };
  end

  `REG_ARSTN(aw_valid_r, aw_fire || (aw_valid_r && !(stage_req && select_write)), 1'b0, axi.ACLK,
             axi.ARESETn)
  `REG_ARSTN(w_valid_r, w_fire || (w_valid_r && !(stage_req && select_write)), 1'b0, axi.ACLK,
             axi.ARESETn)
  `REG_ARSTN(ar_valid_r, ar_fire || (ar_valid_r && !(stage_req && !select_write)), 1'b0, axi.ACLK,
             axi.ARESETn)
  `REG_CE(aw_addr_r, axi.AWADDR, aw_fire, axi.ACLK)
  `REG_CE(w_data_r, axi.WDATA, w_fire, axi.ACLK)
  `REG_CE(w_strb_r, axi.WSTRB, w_fire, axi.ACLK)
  `REG_CE(ar_addr_r, axi.ARADDR, ar_fire, axi.ACLK)
  `REG_CE_ARSTN(prefer_write_r, !select_write, stage_req, 1'b0, axi.ACLK, axi.ARESETn)

  always_comb begin
    resp_fire   = resp.valid && resp.ready;
    req.valid   = req_valid_r && (!active_r || resp_fire);
    req.payload = req_r;
  end

  always_comb begin
    req_fire = req.valid && req.ready;
  end

  `REG_ARSTN(req_valid_r, stage_req || (req_valid_r && !req_fire), 1'b0, axi.ACLK, axi.ARESETn)
  `REG_CE(req_r, next_req, stage_req, axi.ACLK)
  `REG_ARSTN(active_r, req_fire || (active_r && !resp_fire), 1'b0, axi.ACLK, axi.ARESETn)
  `REG_CE(write_r, req_r.write, req_fire, axi.ACLK)

  always_comb begin
    resp.ready = active_r && (write_r ? axi.BREADY : axi.RREADY);
  end

  always_comb begin
    axi.BVALID = axi.ARESETn && active_r && write_r && resp.valid;
    axi.RVALID = axi.ARESETn && active_r && !write_r && resp.valid;
    axi.RDATA  = resp.payload.data;
    unique case (resp.payload.status)
      MEM_OKAY: begin
        axi.BRESP = BRESP_OKAY;
        axi.RRESP = RRESP_OKAY;
      end
      MEM_DECODE_ERR: begin
        axi.BRESP = BRESP_DECERR;
        axi.RRESP = RRESP_DECERR;
      end
      default: begin
        axi.BRESP = BRESP_SLVERR;
        axi.RRESP = RRESP_SLVERR;
      end
    endcase
  end

  always_comb begin
    axi.BID    = '0;
    axi.BIDUNQ = 1'b0;
    axi.BUSER  = '0;
    axi.BTRACE = 1'b0;
    axi.RID    = '0;
    axi.RIDUNQ = 1'b0;
    axi.RUSER  = '0;
    axi.RTRACE = 1'b0;
  end

  demu_dpi_bfm #(
      .PORT(PORT)
  ) u_dpi (
      .clk_i  (axi.ACLK),
      .rst_n_i(axi.ARESETn),
      .req    (req),
      .resp   (resp)
  );

  initial begin
    if ($bits(
            axi.AWADDR
        ) != $bits(
            addr_t
        ) || $bits(
            axi.WDATA
        ) != $bits(
            word_t
        ) || $bits(
            axi.WSTRB
        ) != WordBytes) begin
      $fatal(1, "AXI5-Lite BFM address and data widths must match DEMU");
    end
    if (!axi.O_EN_STRB || axi.O_EN_SIZE || axi.OO_EN_ID || axi.OO_EN_IDUNQ || axi.O_EN_USER ||
        axi.OI_EN_PROT || axi.C_EN_TRACE || axi.O_EN_WAKEUP || axi.O_EN_SUBSYSTEM) begin
      $fatal(1, "AXI5-Lite BFM requires WSTRB and all other optional signals disabled");
    end
  end

  `ASSERT(ReqStable, req.valid && !req.ready |=> req.valid && $stable(req.payload), axi.ACLK,
          axi.ARESETn)
  `ASSERT(BStable, axi.BVALID && !axi.BREADY |=> axi.BVALID && $stable(axi.BRESP), axi.ACLK,
          axi.ARESETn)
  `ASSERT(RStable, axi.RVALID && !axi.RREADY |=> axi.RVALID && $stable({axi.RRESP, axi.RDATA}),
          axi.ACLK, axi.ARESETn)
endmodule
