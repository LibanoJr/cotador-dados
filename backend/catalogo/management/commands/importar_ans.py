"""Importa a referência da ANS a partir de arquivos locais ou URLs.

Uso:
    python manage.py importar_ans                                   # amostras fictícias
    python manage.py importar_ans --produtos URL --valores URL --data-referencia 2026-09-28

Em produção, este comando roda agendado (semanalmente, que é a periodicidade atual do conjunto
de valor comercial), por cron no EC2 ou por um fluxo do n8n que chama o endpoint equivalente.
"""
from datetime import date
from pathlib import Path
from urllib.request import urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalogo.servicos.sincronizacao_ans import ErroSincronizacao, importar_referencia

PASTA = Path(settings.BASE_DIR) / "amostras" / "ans"


def ler(origem: str) -> str:
    if origem.startswith(("http://", "https://")):
        with urlopen(origem, timeout=60) as resp:  # noqa: S310 - origem informada pelo operador
            bruto = resp.read()
    else:
        bruto = Path(origem).read_bytes()
    for codificacao in ("utf-8", "latin-1"):
        try:
            return bruto.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise CommandError(f"Não foi possível decodificar {origem}")


class Command(BaseCommand):
    help = "Importa cadastro de produtos e valor comercial (NTRP) da ANS"

    def add_arguments(self, parser):
        parser.add_argument("--produtos", default=str(PASTA / "produtos.csv"))
        parser.add_argument("--valores", default=str(PASTA / "valor_comercial.csv"))
        parser.add_argument("--data-referencia", default=None, help="AAAA-MM-DD; padrão: hoje")

    def handle(self, *args, produtos, valores, data_referencia, **opts):
        ref = date.fromisoformat(data_referencia) if data_referencia else date.today()
        try:
            resumo = importar_referencia(ler(produtos), ler(valores), ref)
        except ErroSincronizacao as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"Referência ANS de {ref:%d/%m/%Y}: {resumo.produtos} produtos, {resumo.valores} valores por faixa"
        ))
        for linha in resumo.linhas_ignoradas:
            self.stdout.write(self.style.WARNING(f"  ignorada: {linha}"))
        for plano in resumo.planos_afetados:
            self.stdout.write(self.style.WARNING(f"  plano publicado afetado: {plano}"))
