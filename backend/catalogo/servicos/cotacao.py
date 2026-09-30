"""Cotação: soma o valor de cada vida conforme a faixa etária, usando só tabelas publicadas e vigentes.

Plano que a ANS suspendeu ou cancelou sai da cotação a partir da data da situação, com aviso.
O corretor vê o motivo em vez de simplesmente não encontrar o plano.
"""
from datetime import date
from decimal import Decimal

from django.utils import timezone

from catalogo.models import ProdutoANS
from catalogo.servicos.faixas import faixa_por_idade
from catalogo.servicos.publicacao import tabelas_vigentes


def cotar(regiao: str, tipo_contratacao: str, idades: list[int], data: date | None = None,
          coparticipacao: bool | None = None) -> dict:
    if not idades:
        raise ValueError("Informe ao menos uma idade")
    data = data or timezone.localdate()
    faixas = [faixa_por_idade(i) for i in idades]
    qs = tabelas_vigentes(data).filter(regiao=regiao.upper(), tipo_contratacao=tipo_contratacao)
    if coparticipacao is not None:
        qs = qs.filter(coparticipacao=coparticipacao)
    qs = qs.select_related("plano__operadora", "documento__fonte").prefetch_related("valores", "auditoria")

    tabelas = list(qs)
    registros = {t.plano.registro_ans for t in tabelas if t.plano.registro_ans}
    produtos = {p.registro_ans: p for p in ProdutoANS.objects.filter(registro_ans__in=registros)}

    resultado, avisos = [], []
    for tabela in tabelas:
        produto = produtos.get(tabela.plano.registro_ans)
        if produto and not produto.vendavel_em(data):
            avisos.append(
                f"{tabela.plano.nome} ({tabela.plano.operadora.nome}) fora da cotação: registro "
                f"{produto.registro_ans} com situação '{produto.get_situacao_display()}' na ANS "
                f"desde {produto.situacao_desde:%d/%m/%Y}."
            )
            continue
        valores = tabela.valores_dict()
        if any(f not in valores for f in faixas):
            continue
        vidas = [{"idade": i, "faixa": f, "valor": str(valores[f])} for i, f in zip(idades, faixas)]
        total = sum((valores[f] for f in faixas), Decimal("0"))
        fonte = tabela.documento.fonte
        resultado.append(
            {
                "tabela_id": tabela.id,
                "operadora": tabela.plano.operadora.nome,
                "plano": tabela.plano.nome,
                "registro_ans": tabela.plano.registro_ans or None,
                "conferido_na_ans": produto is not None,
                "acomodacao": tabela.plano.acomodacao,
                "coparticipacao": tabela.coparticipacao,
                "total": str(total),
                "vidas": vidas,
                "vigencia_inicio": tabela.vigencia_inicio.isoformat(),
                "vigencia_fim": tabela.vigencia_fim.isoformat() if tabela.vigencia_fim else None,
                "versao": tabela.versao,
                "fonte": fonte.nome,
                "fonte_atrasada": fonte.atrasada,
                "documento": tabela.documento.nome_original,
                "documento_id": tabela.documento_id,
                "pagina": tabela.pagina_origem,
                "verificado_em": tabela.revisado_em.isoformat() if tabela.revisado_em else None,
                # Preço fora da banda da ANS, publicado com justificativa da equipe: o corretor fica sabendo.
                "liberado_com_justificativa": next(
                    (a.detalhes.get("justificativa") for a in tabela.auditoria.all() if a.acao == "bloqueio_liberado"),
                    None,
                ),
            }
        )
    return {"resultados": sorted(resultado, key=lambda r: Decimal(r["total"])), "avisos": avisos}
