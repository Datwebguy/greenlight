# @xstocker/agent-sdk

SDK for AI agents to trade tokenized U.S. stocks ([xStocks](https://xstocker.com)) on Solana.

No account. No API key. No OAuth. This SDK only reads public data and builds
unsigned transactions — it never touches a private key. You (or your agent
framework's wallet adapter) are responsible for signing and broadcasting the
returned transaction.

## Install

```bash
npm install @xstocker/agent-sdk
```

## Usage

```ts
import { xstocker } from "@xstocker/agent-sdk";

// 1. Discover tradable assets — reads the static list at
//    https://xstocker.com/agent/assets.json (CDN file, no API call)
const { assets, payTokens } = await xstocker.getAssets();

// 2. Build an unsigned buy transaction
const order = await xstocker.buildOrder({
  wallet: "USER_SOLANA_ADDRESS",
  asset: "NVDAx",
  amount: 100,
  payToken: "USDC", // or "SOL"
  side: "buy",       // or "sell"
});

console.log(order.details);
// { side: 'buy', asset: 'NVDAx', amountIn: '100 USDC',
//   expectedOut: '0.470123 NVDAx', fee: '0.002350 NVDAx', ... }

// 3a. If your agent CAN sign transactions programmatically (e.g. it has its
//     own wallet adapter), sign order.transaction (base64) with the user's
//     own wallet and send it. It expires after roughly a minute, so build it
//     right before signing and rebuild if it runs out.

// 3b. If your agent CANNOT sign transactions (e.g. a plain chat bot with no
//     wallet access), hand the user order.solanaPayUrl instead, as a link or
//     a QR code. Their wallet (e.g. Phantom) opens it and requests a fresh
//     transaction at the moment they approve, so nothing expires in between:
console.log(order.solanaPayUrl);
// "solana:https%3A%2F%2Fxstocker.com%2Fagent%2Fpay%3Fasset%3DNVDAx%26amount%3D100..."
// (a `partner` wallet, if you passed one, is carried inside the link)

// 4. Verify it landed
const status = await xstocker.getOrderStatus(signature);
console.log(status.status); // "confirmed" | "finalized" | "processed" | "failed" | "not_found"
```

## Selling

```ts
await xstocker.buildOrder({
  wallet: "USER_SOLANA_ADDRESS",
  asset: "NVDAx",
  amount: 0.5,        // amount of NVDAx to sell
  payToken: "USDC",   // token you receive
  side: "sell",
});
```

On a sell, `amount` is in the units the wallet shows (xStocks are scaled-UI
tokens, so this can differ from the raw on-chain amount; the API converts it).
Pass a number, or a decimal string for up to 8 decimals. The API never sells
more than the wallet holds.

### Sell everything

```ts
const order = await xstocker.buildOrder({
  wallet: "USER_SOLANA_ADDRESS",
  asset: "NVDAx",
  amount: "max",      // sell the entire balance (sells only)
  side: "sell",
});

console.log(order.details.amountIn); // e.g. "3.12345678 NVDAx" — what was actually sold
```

With `"max"` the API reads the exact on-chain balance itself, so you do not need
to look it up (and there is no rounding dust left behind).

## Referral partners

No registration, no API key, no claiming. A partner is just a Solana wallet
address. Pass it as `partner` and the partner's fee is sent to that wallet,
on-chain, **in the same transaction as the trade**. The trader pays it on top
of the standard fee (0.25% by default).

```ts
const order = await xstocker.buildOrder({
  wallet: "USER_SOLANA_ADDRESS",
  asset: "NVDAx",
  amount: 100,
  partner: "YOUR_WALLET_ADDRESS",
});

console.log(order.details.partnerFee);
// { applied: true, wallet: "...", bps: 25, amount: "0.25 USDC", destination: "..." }
```

USDC trades pay into the partner's USDC token account (it must exist: receive
any USDC to that wallet once), SOL trades pay into the wallet itself. If the
fee can't be paid, the trade is still built normally and `partnerFee` says why
(`applied: false`, `reason: "partner_usdc_account_missing"`, ...). Check a
wallet up front:

```ts
const check = await xstocker.checkPartner("YOUR_WALLET_ADDRESS");
console.log(check.usdc.ready, check.sol.ready);
```

## Custom client

```ts
import { XStockerAgentClient } from "@xstocker/agent-sdk";

const client = new XStockerAgentClient({ baseUrl: "https://api.xstocker.com" });
```

## Assets

`getAssets()` reads a static file from the CDN, not the API. `asset` in
`buildOrder()` accepts the ticker in any letter case (the trailing "x" is
optional) or the token's mint address.

## Error handling

```ts
import { XStockerAgentError } from "@xstocker/agent-sdk";

try {
  await xstocker.buildOrder({ wallet, asset: "NVDAx", amount: 100 });
} catch (err) {
  if (err instanceof XStockerAgentError) {
    console.error(err.code, err.message); // e.g. "no_route", "invalid_wallet"
  }
}
```

## Links

- [Agent API landing page](https://xstocker.com/agents)
- [Asset list (static JSON)](https://xstocker.com/agent/assets.json)
- [OpenAPI spec](https://xstocker.com/openapi.yaml)
- [agent.json](https://xstocker.com/.well-known/agent.json)

## License

MIT
