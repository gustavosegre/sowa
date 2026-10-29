"""Admin commands: `uv run python -m forja.cli [--data-dir DIR] [--web-url URL] token [--new]` (`make token`)."""

from __future__ import annotations

import argparse
import os
import sys

from forja.auth import new_token, resolve_token, token_path, write_token_file
from forja.settings import get_settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="forja.cli")
    parser.add_argument("--data-dir", help="pasta de dados (padrão: FORJA_DATA_DIR)")
    parser.add_argument("--web-url", help="endereço da interface (padrão: FORJA_WEB_URL)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    tok = sub.add_parser("token", help="mostra o endereço da Forja com o token de acesso")
    tok.add_argument("--new", action="store_true", help="gera um token novo (o anterior deixa de valer)")
    args = parser.parse_args(argv)
    # Before the settings are read (and cached).
    if args.data_dir:
        os.environ["FORJA_DATA_DIR"] = args.data_dir
    if args.web_url:
        os.environ["FORJA_WEB_URL"] = args.web_url

    s = get_settings()
    if not s.auth_enabled:
        sys.exit("O login está desligado (FORJA_AUTH_ENABLED=false): não há token.")
    if args.new:
        if s.token.strip():
            sys.exit("O token vem de FORJA_TOKEN: troque a variável de ambiente.")
        write_token_file(new_token())
        print(f"Token novo gravado em {token_path()}. Reinicie a API para ele valer.")
    auth = resolve_token()
    print(f"{s.web_url.rstrip('/')}/#token={auth.token}")
    print(f"(token de {auth.source}; chamadas à API usam 'Authorization: Bearer <token>')")


if __name__ == "__main__":
    main()
