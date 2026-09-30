"""Mede a precisão de um extrator contra o gabarito (dataset com valores conferidos).

Uso: python manage.py avaliar_extracao [--metodo deterministico|llm]

Em produção, o gabarito cresce com tabelas reais já conferidas por humanos. Esse número
é o que autoriza (ou não) aumentar a automação, por exemplo aprovar sozinho reajustes uniformes.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from catalogo.servicos.extracao import ErroExtracao, ancorar, obter_extrator, texto_paginas


class Command(BaseCommand):
    help = "Avalia a extração contra backend/amostras/gabarito.json"

    def add_arguments(self, parser):
        parser.add_argument("--metodo", default=None)

    def handle(self, *args, metodo=None, **opts):
        pasta = Path(settings.BASE_DIR) / "amostras"
        gabarito = json.loads((pasta / "gabarito.json").read_text(encoding="utf-8"))
        extrator = obter_extrator(metodo)
        total = acertos = 0
        for arquivo, esperado in gabarito.items():
            conteudo = (pasta / arquivo).read_bytes()
            try:
                r = ancorar(extrator.extrair(conteudo), texto_paginas(conteudo))
            except ErroExtracao as exc:
                self.stdout.write(self.style.ERROR(f"{arquivo}: falhou ({exc})"))
                n = 5 + sum(len(v) for v in esperado["tabelas"].values()) + len(esperado.get("registros", {}))
                total += n
                continue
            obtido_meta = {
                "operadora": r.operadora, "regiao": r.regiao, "tipo_contratacao": r.tipo_contratacao,
                "coparticipacao": r.coparticipacao, "vigencia_inicio": r.vigencia_inicio.isoformat(),
            }
            erros = []
            for campo, valor in obtido_meta.items():
                total += 1
                if valor == esperado[campo]:
                    acertos += 1
                else:
                    erros.append(f"{campo}: esperado {esperado[campo]!r}, obtido {valor!r}")
            obtidas = {t.plano: t.valores for t in r.tabelas}
            registros = {t.plano: t.registro_ans for t in r.tabelas}
            for plano, registro in esperado.get("registros", {}).items():
                total += 1
                if registros.get(plano) == registro:
                    acertos += 1
                else:
                    erros.append(f"{plano} registro ANS: esperado {registro}, obtido {registros.get(plano)!r}")
            for plano, valores in esperado["tabelas"].items():
                for faixa, valor in valores.items():
                    total += 1
                    got = obtidas.get(plano, {}).get(int(faixa))
                    if got is not None and got == Decimal(valor):
                        acertos += 1
                    else:
                        erros.append(f"{plano} faixa {faixa}: esperado {valor}, obtido {got}")
            status = self.style.SUCCESS("ok") if not erros else self.style.WARNING(f"{len(erros)} divergência(s)")
            self.stdout.write(f"{arquivo}: {status}")
            for e in erros[:10]:
                self.stdout.write(f"   - {e}")
        taxa = acertos / total * 100 if total else 0
        self.stdout.write(self.style.SUCCESS(f"\nMétodo {extrator.nome}: {acertos}/{total} campos corretos ({taxa:.1f}%)"))
