// src/index.ts
var DEFAULT_BASE_URL = "https://api.xstocker.com";
var DEFAULT_ASSETS_URL = "https://xstocker.com/agent/assets.json";
var XStockerAgentError = class extends Error {
  constructor(code, message, httpStatus) {
    super(message);
    this.name = "XStockerAgentError";
    this.code = code;
    this.httpStatus = httpStatus;
  }
};
var XStockerAgentClient = class {
  constructor(options = {}) {
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, "");
    this.assetsUrl = options.assetsUrl ?? DEFAULT_ASSETS_URL;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }
  /**
   * List tradable xStocks with mint addresses, decimals, and accepted pay
   * tokens. Reads a static file from the CDN (not the API), so it is cheap
   * and safe to call often — but caching the result is still polite.
   */
  async getAssets() {
    const res = await this.fetchImpl(this.assetsUrl);
    return this.handle(res);
  }
  /**
   * Build an unsigned transaction that buys or sells an xStock against
   * USDC or SOL. Returns a base64 transaction the caller must have signed
   * by the user's own wallet before broadcasting.
   */
  async buildOrder(params) {
    const res = await this.fetchImpl(`${this.baseUrl}/agent/build-order`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        wallet: params.wallet,
        asset: params.asset,
        amount: params.amount,
        pay_token: params.payToken ?? "USDC",
        side: params.side ?? "buy",
        ...params.partner ? { partner: params.partner } : {}
      })
    });
    return this.handle(res);
  }
  /**
   * Check on-chain confirmation status for a previously signed and
   * broadcast transaction signature. No order state is stored server-side —
   * this is a thin, read-only proxy onto Solana RPC.
   */
  async getOrderStatus(signature) {
    const res = await this.fetchImpl(`${this.baseUrl}/agent/order/${encodeURIComponent(signature)}`);
    return this.handle(res);
  }
  /**
   * Check that a wallet can receive referral fees. There is no registration:
   * a partner is just a wallet address, passed as `partner` on buildOrder().
   * USDC fees land in the wallet's USDC token account (it must exist), SOL
   * fees in the wallet itself.
   */
  async checkPartner(wallet) {
    const res = await this.fetchImpl(`${this.baseUrl}/agent/partners/check?wallet=${encodeURIComponent(wallet)}`);
    return this.handle(res);
  }
  async handle(res) {
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      const code = body && body.error || "unknown_error";
      const message = body && body.message || `Request failed with status ${res.status}`;
      throw new XStockerAgentError(code, message, res.status);
    }
    return body;
  }
};
var xstocker = new XStockerAgentClient();
export {
  XStockerAgentClient,
  XStockerAgentError,
  xstocker
};
