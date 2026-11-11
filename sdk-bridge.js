#!/usr/bin/env node
// Thin bridge to @xstocker/agent-sdk. Reads one JSON request on stdin, writes one
// JSON response on stdout. It builds UNSIGNED transactions and reads public data
// only; no private key ever passes through here.
//
// Request:  {"op": "assets" | "buildOrder" | "orderStatus", "sdkDir": "<dir>", ...}
// Response: {"ok": true, "result": ...} | {"ok": false, "error": {"code", "message"}}
"use strict";

const path = require("node:path");
const { createRequire } = require("node:module");

function loadSdk(sdkDir) {
  const base = path.join(sdkDir || __dirname, "package.json");
  return createRequire(base)("@xstocker/agent-sdk");
}

async function run(req) {
  const { xstocker } = loadSdk(req.sdkDir);
  switch (req.op) {
    case "assets":
      return xstocker.getAssets();
    case "buildOrder":
      return xstocker.buildOrder({
        wallet: req.wallet,
        asset: req.asset,
        amount: req.amount,
        payToken: req.payToken || "USDC",
        side: req.side || "buy",
      });
    case "orderStatus":
      return xstocker.getOrderStatus(req.signature);
    default:
      throw Object.assign(new Error("unknown op: " + req.op), { code: "bad_op" });
  }
}

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (c) => (input += c));
process.stdin.on("end", async () => {
  let out;
  try {
    out = { ok: true, result: await run(JSON.parse(input || "{}")) };
  } catch (err) {
    out = { ok: false, error: { code: (err && err.code) || "bridge_error", message: String((err && err.message) || err) } };
  }
  process.stdout.write(JSON.stringify(out));
});
