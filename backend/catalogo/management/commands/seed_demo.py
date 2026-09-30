"""Prepara o cenário de demonstração com dados FICTÍCIOS (ver catalogo/servicos/demo.py)."""
from django.core.management.base import BaseCommand

from catalogo.servicos.demo import PARA_DEMONSTRAR, montar_cenario, reiniciar


class Command(BaseCommand):
    help = "Cria fontes, sincroniza a referência ANS fictícia e publica a linha de base"

    def add_arguments(self, parser):
        parser.add_argument("--reiniciar", action="store_true", help="Apaga tudo antes de montar o cenário")

    def handle(self, *args, **opts):
        (reiniciar if opts.get("reiniciar") else montar_cenario)(self.stdout.write)
        self.stdout.write(self.style.SUCCESS(
            f"Pronto. Na demonstração, envie {PARA_DEMONSTRAR} pela tela de conferência."
        ))
