"""Build na Vercel: migra o banco e monta o cenário de demonstração.

Roda depois da instalação das dependências e antes da publicação da função. Assim o deploy fica
completo sem ninguém precisar rodar comandos contra o banco a partir do próprio computador.

- Usa a conexão direta (DATABASE_URL_UNPOOLED), quando existir, porque migrações e CREATE EXTENSION
  não combinam bem com o pool de conexões.
- O cenário (seed_demo) é idempotente: se já existe, nada muda.
- Sem banco configurado, não faz nada; o build segue.
"""
import os
import sys

import django
from django.core.management import call_command


def main() -> int:
    direta = os.environ.get("DATABASE_URL_UNPOOLED") or os.environ.get("POSTGRES_URL_NON_POOLING")
    if direta:
        os.environ["DATABASE_URL"] = direta
    if not (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")):
        print("build_vercel: nenhum banco configurado; migração e cenário não executados.")
        return 0

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    print("build_vercel: aplicando migrações...")
    call_command("migrate", interactive=False, verbosity=1)
    if os.environ.get("DEMO_SEED_NO_BUILD", "1") == "1":
        print("build_vercel: montando cenário de demonstração (idempotente)...")
        call_command("seed_demo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
