"""Cenário de demonstração com dados FICTÍCIOS, usado pelo seed e pelo botão de reinício.

1. Cadastra o catálogo de fontes.
2. Sincroniza a referência ANS fictícia.
3. Ingere e publica a linha de base: tabelas de janeiro da Alfa e de março da Beta.
O PDF de reajuste de junho da Alfa fica para ser enviado durante a demonstração.
"""
import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import transaction

from catalogo.models import (
    DocumentoFonte, FonteDados, Operadora, Plano, ProdutoANS, RegistroAuditoria, TabelaPreco,
    ValorComercialANS, ValorFaixa,
)
from catalogo.servicos.ingestao import ingerir_documento
from catalogo.servicos.publicacao import aprovar
from catalogo.servicos.sincronizacao_ans import importar_referencia

PASTA = Path(settings.BASE_DIR) / "amostras"
LINHA_DE_BASE = ["alfa_pme_df_2026-01.pdf", "beta_pme_df_2026-03.pdf"]
PARA_DEMONSTRAR = "alfa_pme_df_2026-06.pdf"
DATA_REFERENCIA_ANS = date(2026, 9, 28)


def amostras_disponiveis() -> list[str]:
    gabarito = PASTA / "gabarito.json"
    if not gabarito.exists():
        return []
    return sorted(json.loads(gabarito.read_text(encoding="utf-8")))


def _garantir_amostras():
    if not (PASTA / "gabarito.json").exists() or not (PASTA / "ans" / "produtos.csv").exists():
        call_command("gerar_pdfs_exemplo")


def montar_cenario(log=print) -> None:
    _garantir_amostras()
    alfa, _ = Operadora.objects.get_or_create(nome="Alfa Saúde (fictícia)")
    beta, _ = Operadora.objects.get_or_create(nome="Beta Vida (fictícia)")
    fontes = {
        "alfa": FonteDados.objects.get_or_create(
            nome="Alfa Saúde: e-mail do comercial",
            defaults={"tipo": "pdf_email", "operadora": alfa, "frequencia_esperada_dias": 30, "confiabilidade": 3,
                      "responsavel": "Equipe de dados"},
        )[0],
        "beta": FonteDados.objects.get_or_create(
            nome="Beta Vida: portal do corretor",
            defaults={"tipo": "portal", "operadora": beta, "frequencia_esperada_dias": 30, "confiabilidade": 4,
                      "responsavel": "Equipe de dados"},
        )[0],
    }
    FonteDados.objects.get_or_create(
        nome="ANS: produtos e valor comercial (NTRP)",
        defaults={"tipo": "ans", "frequencia_esperada_dias": 7, "confiabilidade": 5,
                  "url": "https://dados.gov.br/dados/conjuntos-dados/valor-comercial-da-mensalidade-por-faixa-etaria",
                  "responsavel": "Sincronização automática"},
    )
    # Fonte sem canal digital: fica atrasada de propósito, para o painel de frescor mostrar o caso.
    FonteDados.objects.get_or_create(
        nome="Gama Saúde: contato do gerente comercial",
        defaults={"tipo": "upload", "frequencia_esperada_dias": 30, "confiabilidade": 2,
                  "responsavel": "Pessoa da equipe (dependência individual)"},
    )

    if not ProdutoANS.objects.exists():
        resumo = importar_referencia(
            (PASTA / "ans" / "produtos.csv").read_text(encoding="utf-8"),
            (PASTA / "ans" / "valor_comercial.csv").read_text(encoding="utf-8"),
            DATA_REFERENCIA_ANS,
        )
        log(f"Referência ANS: {resumo.produtos} produtos, {resumo.valores} valores")

    for arquivo, fonte in zip(LINHA_DE_BASE, (fontes["alfa"], fontes["beta"])):
        if DocumentoFonte.objects.filter(nome_original=arquivo).exists():
            log(f"{arquivo} já ingerido, pulando")
            continue
        _, tabelas = ingerir_documento((PASTA / arquivo).read_bytes(), arquivo, fonte, usuario="seed")
        for t in tabelas:
            aprovar(t, usuario="seed", observacao="Linha de base da demonstração")
        log(f"{arquivo}: {len(tabelas)} tabela(s) publicadas")


@transaction.atomic
def reiniciar(log=print) -> None:
    """Apaga tudo e recria o cenário. Só para o ambiente de demonstração."""
    RegistroAuditoria.objects.all().delete()
    ValorFaixa.objects.all().delete()
    TabelaPreco.objects.all().delete()
    DocumentoFonte.objects.all().delete()
    Plano.objects.all().delete()
    FonteDados.objects.all().delete()
    Operadora.objects.all().delete()
    ValorComercialANS.objects.all().delete()
    ProdutoANS.objects.all().delete()
    montar_cenario(log)
