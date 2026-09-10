"""CLI and backwards-compatible ASGI entry point."""

import argparse
import json
import secrets

from .api import create_app
from .config import load_config

app = create_app()


def main():
    parser = argparse.ArgumentParser(description="Wildlife shadow-pilot service; no physical signal outputs")
    parser.add_argument("--config", default="data/sample_config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate configuration and paths")
    sub.add_parser("token", help="generate a random API credential")
    server = sub.add_parser("serve", help="start API, dashboard and configured capture workers")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8000)
    demo = sub.add_parser("demo", help="run deterministic software scenarios without hardware")
    demo.add_argument("--output", default=None)
    args = parser.parse_args()
    if args.command == "token":
        print(secrets.token_urlsafe(32))
    elif args.command == "validate":
        cfg = load_config(args.config)
        print(json.dumps({"valid": True, "mode": cfg.mode, "sites": [s.id for s in cfg.sites]}))
    elif args.command == "demo":
        from .simulation import run_demo

        report = run_demo()
        text = json.dumps(report, indent=2)
        if args.output:
            from pathlib import Path

            Path(args.output).write_text(text + "\n")
        print(text)
    elif args.command == "serve":
        import uvicorn

        uvicorn.run(create_app(load_config(args.config)), host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
