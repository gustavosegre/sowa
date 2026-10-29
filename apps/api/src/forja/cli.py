"""Admin commands: `uv run python -m forja.cli create-user NAME` / `set-password NAME`."""

from __future__ import annotations

import argparse
import getpass
import sys

from forja.auth import hash_password
from forja.main import run_migrations
from forja.storage.db import session_scope
from forja.storage.repos import UserRepo


def _ask_password() -> str:
    pw = getpass.getpass("Senha (mínimo 8 caracteres): ")
    if len(pw) < 8:
        sys.exit("Senha curta demais.")
    if getpass.getpass("Repita a senha: ") != pw:
        sys.exit("As senhas não conferem.")
    return pw


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="forja.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("create-user", help="cria um usuário").add_argument("username")
    sub.add_parser("set-password", help="redefine a senha de um usuário").add_argument("username")
    args = parser.parse_args(argv)
    run_migrations()
    with session_scope() as s:
        repo = UserRepo(s)
        user = repo.by_username(args.username)
        if args.cmd == "create-user":
            if user is not None:
                sys.exit(f'Já existe um usuário "{args.username}".')
            repo.create(args.username, _ask_password())
            print(f'Usuário "{args.username}" criado.')
        else:
            if user is None:
                sys.exit(f'Usuário "{args.username}" não encontrado.')
            user.password_hash = hash_password(_ask_password())
            print(f'Senha de "{args.username}" redefinida.')


if __name__ == "__main__":
    main()
