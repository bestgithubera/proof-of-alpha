"""Register the Proof-of-Alpha agent on-chain (ERC-8004 Identity, BSC Testnet).

Gas-free: registration is sponsored by the MegaFuel paymaster on bsc-testnet,
so NO tBNB is required. If PRIVATE_KEY is not set, the SDK auto-generates a
fresh agent wallet and encrypts it to ~/.bnbagent/wallets/ — zero risk of
touching a real-funds wallet.

Required env (put in .env, gitignored):
    WALLET_PASSWORD   password used to encrypt/decrypt the keystore
Optional:
    PRIVATE_KEY       omit to auto-generate a fresh wallet (recommended)
    NETWORK           defaults to bsc-testnet

Usage:
    python scripts/register_agent.py
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from bnbagent import AgentEndpoint, ERC8004Agent, EVMWalletProvider

AGENT_NAME = "proof-of-alpha"
AGENT_DESCRIPTION = (
    "Falsification-first crypto strategy skill. Generates strategies from "
    "CoinMarketCap data and refuses to lie about them: deflated Sharpe, "
    "permutation nulls, CPCV/PBO, cost/capacity stress, regime splits."
)
# Planned ERC-8183 service endpoint. Embedded as metadata in the on-chain
# agent URI (base64 data URI) — does NOT need to be live to register.
AGENT_ENDPOINT = "https://proof-of-alpha.example/erc8183/status"


def main() -> int:
    load_dotenv()

    password = os.getenv("WALLET_PASSWORD")
    if not password:
        print("ERROR: set WALLET_PASSWORD in .env first (you choose it).", file=sys.stderr)
        return 1

    network = os.getenv("NETWORK", "bsc-testnet")

    wallet = EVMWalletProvider(
        password=password,
        private_key=os.getenv("PRIVATE_KEY"),  # None -> fresh wallet auto-generated
    )
    sdk = ERC8004Agent(network=network, wallet_provider=wallet)

    # Idempotency guard: if we already registered this name locally, stop.
    existing = sdk.get_local_agent_info(AGENT_NAME)
    if existing:
        print(f"Already registered locally: {existing}")
        return 0

    agent_uri = sdk.generate_agent_uri(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        endpoints=[
            AgentEndpoint(name="ERC-8183", endpoint=AGENT_ENDPOINT, version="0.1.0"),
        ],
    )

    print(f"Registering '{AGENT_NAME}' on {network} (gas-free via paymaster)...")
    result = sdk.register_agent(agent_uri=agent_uri)

    agent_id = result.get("agentId")
    tx = result.get("transactionHash")
    print(f"  Agent ID: {agent_id}")
    print(f"  TX:       {tx}")
    if tx:
        print(f"  Explorer: https://testnet.bscscan.com/tx/{tx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
