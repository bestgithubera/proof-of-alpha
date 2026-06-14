"""Emit a live CMC regime-context JSON for the as-of overlay.

Prefers the CMC AI Agent Hub (via the cmc-skill-hub MCP, when an agent calls
this through an MCP client) and falls back to the CMC Pro REST client. The
output file is consumed by falsify_strategy.py --regime-context.

Usage: python skill/scripts/regime_context.py --out demo/output/regime_context.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from data_layer.cmc_client import CmcClient


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=ROOT / "demo" / "output" / "regime_context.json")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    client = CmcClient()
    if not client.has_key:
        print("no CMC_API_KEY set; writing empty context", file=sys.stderr)
        ctx = {"source": "none", "fear_greed": None, "top_by_volume": []}
    else:
        ctx = client.regime_context(top=args.top)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ctx, indent=2, default=str))
    fg = ctx.get("fear_greed")
    print(f"regime: F&G={fg['value'] if fg else 'n/a'} "
          f"({fg['classification'] if fg else 'n/a'}) -> {args.out}")


if __name__ == "__main__":
    main()
