"""On-chain Proof-of-Alpha commerce demo (ERC-8183, BSC testnet).

Frames the Skill as an ERC-8183 *provider agent*: the tradeable good is a
falsification verdict + evidence pack, whose keccak256 is anchored on-chain.
Reuses the registered ERC-8004 identity (agentId 1379). No real capital: escrow
uses the testnet payment token (U faucet) and tBNB for gas (BSC faucet).

The script is safe to run before funding: it computes the deliverable hash
offline, checks the agent's token balance, and — if unfunded — prints the agent
address + faucet links and exits cleanly instead of erroring.

Usage:
  python bnbagent_demo/erc8183_provider.py \
      --evidence demo/output/sentiment_divergence_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAUCET_TBNB = "https://www.bnbchain.org/en/testnet-faucet"
FAUCET_U = "https://united-coin-u.github.io/u-faucet/"


def _summary_from_evidence(path: Path) -> dict:
    """Pull the headline verdict from a *_report.json evidence pack."""
    rep = json.loads(path.read_text())
    h = rep.get("headline", {})
    return {
        "verdict": str(rep.get("verdict", "UNKNOWN")),
        "reason": str((rep.get("reasons") or ["n/a"])[0]),
        "sharpe_ann": str(h.get("sharpe_ann", "")),
        "strategy": str(rep.get("name", "")),
    }


def main() -> int:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path, required=True,
                    help="path to a *_report.json evidence pack")
    ap.add_argument("--network", default=os.getenv("NETWORK", "bsc-testnet"))
    ap.add_argument("--deliverable-url", default=os.getenv(
        "DELIVERABLE_URL",
        "https://github.com/bestgithubera/proof-of-alpha/blob/main/demo/output"),
        help="public URL where the full evidence pack can be fetched/verified")
    ap.add_argument("--budget-tokens", type=float, default=1.0,
                    help="escrow budget in payment-token units (testnet)")
    args = ap.parse_args()

    if not args.evidence.exists():
        print(f"evidence pack not found: {args.evidence}", file=sys.stderr)
        return 1

    if not os.getenv("WALLET_PASSWORD"):
        print("ERROR: set WALLET_PASSWORD in .env (the agent keystore password).",
              file=sys.stderr)
        return 1

    raw_hash = Web3.keccak(args.evidence.read_bytes()).hex()
    summary = _summary_from_evidence(args.evidence)
    print(f"evidence: {args.evidence.name}  verdict={summary['verdict']}")
    print(f"raw evidence keccak256: {raw_hash}")

    from bnbagent import EVMWalletProvider
    from bnbagent.erc8183 import ERC8183Client, DeliverableManifest, JobStatus
    from bnbagent.networks.addresses import BSC_TESTNET_CHAIN_ID

    wallet = EVMWalletProvider(password=os.environ["WALLET_PASSWORD"],
                               private_key=os.getenv("PRIVATE_KEY") or None)
    addr = wallet.address
    client = ERC8183Client(wallet, network=args.network)

    decimals = client.token_decimals()
    symbol = client.token_symbol()
    budget = int(args.budget_tokens * (10 ** decimals))
    bal = client.token_balance()
    print(f"agent wallet: {addr}")
    print(f"payment token: {symbol} (decimals {decimals}); balance {bal / 10**decimals:g} {symbol}")

    out = ROOT / "bnbagent_demo" / "last_job.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    if bal < budget:
        print("\nAgent wallet not funded for the escrow leg yet (NO REAL CAPITAL —")
        print("both are testnet faucets):")
        print(f"  1. tBNB for gas:   {FAUCET_TBNB}")
        print(f"  2. test {symbol} for escrow: {FAUCET_U}")
        print(f"  fund address:      {addr}")
        out.write_text(json.dumps({
            "status": "needs_funding", "agent_id": 1379, "agent_wallet": addr,
            "raw_evidence_keccak256": raw_hash, "verdict": summary["verdict"],
        }, indent=2))
        print(f"\nwrote {out} (status: needs_funding). Re-run after funding.")
        return 0

    # --- ERC-8183 lifecycle (provider == this agent, single-wallet demo) ---
    try:
        expired_at = int(time.time()) + 65 * 60
        created = client.create_job(provider=addr, expired_at=expired_at,
                                    description=f"Proof-of-Alpha verdict: {summary['strategy']}")
        job_id = int(created["jobId"])
        print(f"create_job -> jobId {job_id}  tx {created.get('transactionHash')}")

        client.register_job(job_id)
        client.set_budget(job_id, budget)
        client.fund(job_id, budget)
        print(f"funded job {job_id} with {args.budget_tokens} {symbol}")

        manifest = DeliverableManifest(
            version=1, job_id=job_id, chain_id=BSC_TESTNET_CHAIN_ID,
            contracts={"payment_token": client.payment_token},
            response={"deliverable_url": args.deliverable_url, **summary},
            metadata={"raw_evidence_keccak256": raw_hash, "agent_id": "1379",
                      "skill": "proof-of-alpha"},
        )
        manifest_hash = manifest.manifest_hash()
        submitted = client.submit(job_id, manifest_hash,
                                  {"deliverable_url": args.deliverable_url})
        print(f"submit -> deliverable {manifest_hash.hex()}  tx {submitted.get('transactionHash')}")

        settled = client.settle(job_id)
        status = client.get_job_status(job_id)
        print(f"settle -> tx {settled.get('transactionHash')}  status {status.name}")

        out.write_text(json.dumps({
            "status": status.name, "agent_id": 1379, "agent_wallet": addr,
            "job_id": job_id,
            "raw_evidence_keccak256": raw_hash,
            "deliverable_manifest_hash": manifest_hash.hex(),
            "verdict": summary["verdict"],
            "tx": {"create": created.get("transactionHash"),
                   "submit": submitted.get("transactionHash"),
                   "settle": settled.get("transactionHash")},
        }, indent=2, default=str))
        print(f"\nwrote {out} (status: {status.name}).")
        return 0
    except Exception as exc:  # likely missing tBNB gas — actionable, not fatal
        print(f"\non-chain step failed: {exc}", file=sys.stderr)
        print(f"if this is a gas error, fund {addr} with tBNB: {FAUCET_TBNB}",
              file=sys.stderr)
        out.write_text(json.dumps({
            "status": "error", "agent_wallet": addr, "error": str(exc),
            "raw_evidence_keccak256": raw_hash,
        }, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
