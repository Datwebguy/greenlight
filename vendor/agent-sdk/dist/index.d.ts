/**
 * @xstocker/agent-sdk
 *
 * Minimal SDK for AI agents to trade tokenized U.S. stocks (xStocks) on
 * Solana through the xStocker Agent API (https://xstocker.com/agents).
 *
 * This SDK only builds unsigned transactions and reads public data — it
 * never touches a private key. The caller is responsible for having the
 * returned transaction signed by the user's own wallet and broadcasting it.
 */
type PayToken = "USDC" | "SOL";
type OrderSide = "buy" | "sell";
interface Asset {
    symbol: string;
    name: string;
    sector: string;
    class: string;
    mint: string;
    decimals: number;
    chain: "solana";
}
interface PayTokenInfo {
    symbol: PayToken;
    mint: string;
    decimals: number;
}
interface AssetsResponse {
    assets: Asset[];
    payTokens: PayTokenInfo[];
}
interface BuildOrderParams {
    /** The user's Solana wallet address (base58). Never a private key. */
    wallet: string;
    /**
     * xStock ticker, e.g. "NVDAx" (case-insensitive; the trailing "x" is
     * optional), or the token's mint address. Must match an asset from getAssets().
     */
    asset: string;
    /**
     * On a buy: amount to spend, in payToken units (a positive number).
     *
     * On a sell: amount of the xStock to sell, in the units the user's wallet
     * shows (xStocks are scaled-UI tokens, so this can differ from the raw
     * on-chain amount; the API converts it). A number, or a decimal string for
     * up to 8 decimals. Pass "max" to sell the ENTIRE balance: the API reads the
     * exact on-chain balance itself. "max" is valid on sells only; the real
     * amount sold is returned in details.amountIn.
     */
    amount: number | "max" | (string & {});
    /** The non-xStock side of the trade. Defaults to "USDC". */
    payToken?: PayToken;
    /** Defaults to "buy". */
    side?: OrderSide;
    /**
     * Optional referral partner: the partner's Solana wallet address (no
     * registration). The trader pays a small extra fee (0.25% by default) that
     * is sent straight to that wallet, on-chain, in the same transaction as the
     * trade. See details.partnerFee for what was applied.
     */
    partner?: string;
}
interface BuildOrderDetails {
    side: OrderSide;
    asset: string;
    amountIn: string;
    expectedOut: string;
    fee: string;
    slippageBps: number;
    lastValidBlockHeight: number | null;
    /** Present only when `partner` was supplied. */
    partnerFee?: PartnerFee;
}
interface PartnerFee {
    /** true: the fee transfer is part of the returned transaction. */
    applied: boolean;
    wallet: string;
    bps: number;
    /** e.g. "0.25 USDC" (only when applied). */
    amount?: string;
    /** The token account (USDC) or wallet (SOL) that receives the fee (only when applied). */
    destination?: string;
    /**
     * Why it was NOT applied, e.g. "partner_usdc_account_missing",
     * "partner_wallet_unfunded", "fee_below_minimum", "tx_too_large". The trade
     * itself is still built normally.
     */
    reason?: string;
}
interface PartnerCheckResponse {
    status: "ok";
    partner: string;
    fee_bps: number;
    usdc: {
        ready: boolean;
        token_account: string;
        fix?: string;
    };
    sol: {
        ready: boolean;
        fix?: string;
    };
}
interface BuildOrderResponse {
    status: "ready";
    /**
     * Base64-encoded unsigned Solana transaction. For agents that can sign
     * programmatically. It expires after roughly a minute (see
     * details.lastValidBlockHeight): build it right before signing, sign and
     * send it immediately, and rebuild if it expires.
     */
    transaction: string;
    /**
     * Solana Pay "transaction request" link (solana:https%3A...). Hand it to a
     * person (as a link or QR code) when your agent has no wallet of its own:
     * their wallet (e.g. Phantom) opens it and requests a FRESH transaction at
     * the moment they approve, so nothing expires. Carries `partner` along
     * when one was supplied.
     */
    solanaPayUrl?: string;
    /**
     * @deprecated Prefer solanaPayUrl. Link to xstocker.com/agents for this order.
     */
    confirmUrl: string;
    details: BuildOrderDetails;
}
type OrderStatus = "processed" | "confirmed" | "finalized" | "failed" | "not_found";
interface OrderStatusResponse {
    status: OrderStatus;
    signature: string;
    tx: string;
    error?: unknown;
}
declare class XStockerAgentError extends Error {
    readonly code: string;
    readonly httpStatus: number;
    constructor(code: string, message: string, httpStatus: number);
}
interface XStockerAgentClientOptions {
    /** Override the API base URL. Defaults to https://api.xstocker.com. */
    baseUrl?: string;
    /** Override the static asset list URL. Defaults to https://xstocker.com/agent/assets.json. */
    assetsUrl?: string;
    /** Custom fetch implementation (useful for testing or non-standard runtimes). */
    fetchImpl?: typeof fetch;
}
declare class XStockerAgentClient {
    private readonly baseUrl;
    private readonly assetsUrl;
    private readonly fetchImpl;
    constructor(options?: XStockerAgentClientOptions);
    /**
     * List tradable xStocks with mint addresses, decimals, and accepted pay
     * tokens. Reads a static file from the CDN (not the API), so it is cheap
     * and safe to call often — but caching the result is still polite.
     */
    getAssets(): Promise<AssetsResponse>;
    /**
     * Build an unsigned transaction that buys or sells an xStock against
     * USDC or SOL. Returns a base64 transaction the caller must have signed
     * by the user's own wallet before broadcasting.
     */
    buildOrder(params: BuildOrderParams): Promise<BuildOrderResponse>;
    /**
     * Check on-chain confirmation status for a previously signed and
     * broadcast transaction signature. No order state is stored server-side —
     * this is a thin, read-only proxy onto Solana RPC.
     */
    getOrderStatus(signature: string): Promise<OrderStatusResponse>;
    /**
     * Check that a wallet can receive referral fees. There is no registration:
     * a partner is just a wallet address, passed as `partner` on buildOrder().
     * USDC fees land in the wallet's USDC token account (it must exist), SOL
     * fees in the wallet itself.
     */
    checkPartner(wallet: string): Promise<PartnerCheckResponse>;
    private handle;
}
/** Convenience singleton using the default base URL. Fine for most agents. */
declare const xstocker: XStockerAgentClient;

export { type Asset, type AssetsResponse, type BuildOrderDetails, type BuildOrderParams, type BuildOrderResponse, type OrderSide, type OrderStatus, type OrderStatusResponse, type PartnerCheckResponse, type PartnerFee, type PayToken, type PayTokenInfo, XStockerAgentClient, type XStockerAgentClientOptions, XStockerAgentError, xstocker };
