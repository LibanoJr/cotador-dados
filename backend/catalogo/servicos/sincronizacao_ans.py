"""Importa a referência oficial da ANS (cadastro de produtos e valor comercial da NTRP).

Formato de trabalho dos arquivos (CSV com ';', decimal com vírgula, como nos dados abertos da ANS):

    produtos:        REGISTRO_PLANO;NM_PLANO;RAZAO_SOCIAL;CONTRATACAO;SITUACAO;DT_SITUACAO
    valor comercial: REGISTRO_PLANO;FAIXA_ETARIA;VL_COMERCIAL_MENSALIDADE

O nome VL_COMERCIAL_MENSALIDADE é o do dicionário oficial. Os demais nomes e a chave de junção
entre os conjuntos reais (a ANS usa um identificador interno do plano, ID_PLANO, além do número de
registro) precisam ser confirmados na fase de descoberta; por isso o mapeamento está isolado em
COLUNAS, e trocar de layout é mudar só este dicionário.

Depois de importar, o serviço faz a reconferência: plano publicado cujo produto deixou de ser
vendável ganha um registro de auditoria, e as tabelas em revisão são revalidadas.
"""
import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime

from django.db import transaction
from django.utils import timezone

from catalogo.models import FonteDados, Plano, ProdutoANS, RegistroAuditoria, TabelaPreco, ValorComercialANS
from catalogo.servicos.faixas import faixa_por_rotulo
from catalogo.servicos.numeros import parse_brl

COLUNAS = {
    "registro": "REGISTRO_PLANO",
    "nome": "NM_PLANO",
    "operadora": "RAZAO_SOCIAL",
    "contratacao": "CONTRATACAO",
    "situacao": "SITUACAO",
    "situacao_desde": "DT_SITUACAO",
    "faixa": "FAIXA_ETARIA",
    "valor": "VL_COMERCIAL_MENSALIDADE",
}

SITUACOES = {
    "ativo": ProdutoANS.Situacao.ATIVO,
    "ativa": ProdutoANS.Situacao.ATIVO,
    "suspenso": ProdutoANS.Situacao.SUSPENSO,
    "comercializacao suspensa": ProdutoANS.Situacao.SUSPENSO,
    "cancelado": ProdutoANS.Situacao.CANCELADO,
}


class ErroSincronizacao(Exception):
    pass


@dataclass
class ResumoSincronizacao:
    produtos: int = 0
    valores: int = 0
    linhas_ignoradas: list[str] = field(default_factory=list)
    planos_afetados: list[str] = field(default_factory=list)


def _linhas(texto: str) -> list[dict]:
    leitor = csv.DictReader(io.StringIO(texto.lstrip("\ufeff")), delimiter=";")
    return [{(k or "").strip(): (v or "").strip() for k, v in linha.items()} for linha in leitor]


def _data(texto: str) -> date | None:
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def _registro(texto: str) -> str:
    return "".join(texto.split())


@transaction.atomic
def importar_referencia(produtos_csv: str, valores_csv: str, data_referencia: date) -> ResumoSincronizacao:
    resumo = ResumoSincronizacao()
    c = COLUNAS

    for n, linha in enumerate(_linhas(produtos_csv), start=2):
        registro = _registro(linha.get(c["registro"], ""))
        situacao = SITUACOES.get(linha.get(c["situacao"], "").lower())
        if not registro or not situacao:
            resumo.linhas_ignoradas.append(f"produtos, linha {n}: registro ou situação inválidos")
            continue
        ProdutoANS.objects.update_or_create(
            registro_ans=registro,
            defaults={
                "nome": linha.get(c["nome"], ""),
                "operadora": linha.get(c["operadora"], ""),
                "contratacao": linha.get(c["contratacao"], ""),
                "situacao": situacao,
                "situacao_desde": _data(linha.get(c["situacao_desde"], "")),
                "data_referencia": data_referencia,
            },
        )
        resumo.produtos += 1

    produtos = {p.registro_ans: p for p in ProdutoANS.objects.all()}
    for n, linha in enumerate(_linhas(valores_csv), start=2):
        produto = produtos.get(_registro(linha.get(c["registro"], "")))
        faixa = faixa_por_rotulo(linha.get(c["faixa"], ""))
        valor = parse_brl(linha.get(c["valor"], ""))
        if not produto or not faixa or not valor:
            resumo.linhas_ignoradas.append(f"valor comercial, linha {n}: produto, faixa ou valor inválidos")
            continue
        ValorComercialANS.objects.update_or_create(produto=produto, faixa=faixa, defaults={"valor": valor})
        resumo.valores += 1

    if resumo.produtos == 0:
        raise ErroSincronizacao("Nenhum produto válido no arquivo; referência anterior mantida")

    _reconferir(resumo, produtos, data_referencia)
    FonteDados.objects.filter(tipo=FonteDados.Tipo.ANS).update(ultima_verificacao=timezone.now())
    return resumo


def _reconferir(resumo: ResumoSincronizacao, produtos: dict, data_referencia: date) -> None:
    from catalogo.servicos.publicacao import revalidar

    hoje = timezone.localdate()
    for plano in Plano.objects.exclude(registro_ans="").select_related("operadora"):
        produto = produtos.get(plano.registro_ans)
        if not produto or produto.vendavel_em(hoje):
            continue
        publicadas = plano.tabelas.filter(status=TabelaPreco.Status.PUBLICADA)
        for tabela in publicadas:
            ja_avisado = tabela.auditoria.filter(
                acao="situacao_ans_alterada", detalhes__situacao=produto.situacao
            ).exists()
            if not ja_avisado:
                RegistroAuditoria.objects.create(
                    tabela=tabela, acao="situacao_ans_alterada", usuario="sincronizacao_ans",
                    detalhes={"situacao": produto.situacao, "desde": str(produto.situacao_desde),
                              "referencia": str(data_referencia)},
                )
        if publicadas.exists():
            resumo.planos_afetados.append(f"{plano} ({produto.get_situacao_display()})")

    for tabela in TabelaPreco.objects.filter(status=TabelaPreco.Status.EM_REVISAO).select_related("plano"):
        revalidar(tabela)
