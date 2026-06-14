# Proof of Alpha on-chain — ERC-8183 commerce demo (BNB AI Agent SDK)

**The pitch for "Best Use of BNB AI Agent SDK":** we don't bolt a swap call onto
an LLM. We use the SDK for what it is — **agent identity (ERC-8004) + agentic
commerce (ERC-8183)** — and make the *falsification verdict itself the tradeable
on-chain good*. Proof of Alpha is an ERC-8183 **provider agent**: a client asks
"give me a strategy that survives falsification", the agent runs the gate, and
the **evidence pack's keccak256 is anchored on-chain** as the deliverable. The
verdict — PASS or FAIL — is proof-of-alpha, settled trustlessly.

## What's on-chain already

- **ERC-8004 identity** — agent `proof-of-alpha`, **agentId 1379**, registered
  gas-free via the MegaFuel paymaster on BSC testnet.
  Registration tx: `0x697ebe4e9b965d367d7ee2b62fb4cb165dd46c46a6402cb7713f611dfe6566a0`
  ([BscScan testnet](https://testnet.bscscan.com/tx/0x697ebe4e9b965d367d7ee2b62fb4cb165dd46c46a6402cb7713f611dfe6566a0)).
- **Agent wallet:** `0xe541340f0372079bEB3aead9379A820EEc09EE81`
  (fresh, auto-generated keystore — never held real funds).

## The ERC-8183 lifecycle we exercise

`scripts: bnbagent_demo/erc8183_provider.py`

1. `create_job(provider, expired_at, description)` — open the job.
2. `register_job(job_id)` — bind the default `OptimisticPolicy`.
3. `set_budget` + `fund` — escrow the testnet payment token (`U`).
4. `submit(job_id, manifest_hash, {"deliverable_url": ...})` — the provider
   anchors `DeliverableManifest.manifest_hash()` (keccak256 of the canonical
   evidence manifest) on-chain. The full evidence pack stays fetchable at
   `deliverable_url` for verification.
5. `settle(job_id)` — permissionless; optimistic settlement → `COMPLETED`.

The deliverable manifest carries the verdict, the strategy name, the headline
Sharpe, and `raw_evidence_keccak256` (the keccak of the raw report file), so a
verifier can reproduce the hash from the published evidence pack.

## No real capital

Both legs are **testnet faucets**:
- tBNB (gas): https://www.bnbchain.org/en/testnet-faucet
- test `U` (escrow): https://united-coin-u.github.io/u-faucet/

Fund `0xe541340f0372079bEB3aead9379A820EEc09EE81`, then:

```bash
.venv/bin/python bnbagent_demo/erc8183_provider.py \
    --evidence demo/output/sentiment_divergence_report.json \
    --deliverable-url https://github.com/bestgithubera/proof-of-alpha/blob/main/demo/output/xs_momentum_report.md
```

The script is safe to run before funding — it computes the deliverable hash
offline, reads the on-chain balance, and prints the faucet steps instead of
erroring. After a successful run it writes `bnbagent_demo/last_job.json` with the
job id, the deliverable hash, and the create/submit/settle tx hashes — the
on-chain proof.

## Status

- [x] ERC-8004 identity registered on-chain (tx above)
- [x] Provider script implemented against the real SDK API (create/register/
      set_budget/fund/submit/settle), runs offline up to the funding gate
- [ ] ERC-8183 escrow loop broadcast — awaits faucet funding of the agent wallet
      (tx hashes will be recorded in `last_job.json` and here)
