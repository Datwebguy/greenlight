# Demo video (strictly under 90 seconds)

Rules from the hackathon: show the plugin working, post the video on X, tag @NousResearch, keep it strictly under 90 seconds. Aim for about 75 seconds so there is margin.

## Before recording
- `hermes plugins install https://github.com/Datwebguy/greenlight` and `hermes plugins enable greenlight`
- Enable Greenlight in Desktop > Capabilities > Plugins and set `default_wallet` to a wallet you control
- Run one proposal beforehand so the Node SDK is already installed (the first run installs it)
- Use a small amount ($25) and a wallet you are happy to show

## Shot list
| Time | On screen | Say |
|---|---|---|
| 0:00-0:08 | Title card: "Greenlight: explicit approval for xStocks trades in Hermes" | "Agents that move money need a hard gate. This is Greenlight." |
| 0:08-0:18 | Type: "Propose buying $25 of NVDAx" | "I ask Hermes to buy $25 of NVDA." |
| 0:18-0:35 | Pane opens: quote, price, risk score and factors, cap remaining | "It simulates the trade against the live xStocks API and scores the risk. No transaction exists yet." |
| 0:35-0:45 | Ask the agent for the transaction before approving; it shows `pending` and no link | "Until I approve, nothing is released. Not even to the agent." |
| 0:45-0:55 | Click Approve | "I approve in the native pane." |
| 0:55-1:05 | Solana Pay link appears; click Open in wallet (wallet opens) | "Only now is the unsigned link released. My wallet signs. Greenlight never touches keys." |
| 1:05-1:15 | Receipts list with "chain verified"; flash `/greenlight` in chat | "Every decision is a hash-chained local receipt, and /greenlight works from the terminal too." |
| 1:15-1:20 | End card with repo URL | "Greenlight. Non-custodial, explicit approval." |

## Post text
> Greenlight for @NousResearch Hermes Agent: explicit approval for xStocks trades. Simulate, risk-score, approve in a native Desktop pane, then release the unsigned transaction. Non-custodial, hash-chained receipts, daily caps. https://github.com/Datwebguy/greenlight
