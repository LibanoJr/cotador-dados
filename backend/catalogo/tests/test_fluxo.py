"""Fluxo completo: ingestão -> validação -> correção -> publicação versionada -> cotação histórica."""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from catalogo.models import TabelaPreco
from catalogo.servicos import publicacao
from catalogo.servicos.cotacao import cotar
from catalogo.servicos.ingestao import DocumentoDuplicado, ingerir_documento

pytestmark = pytest.mark.django_db

JAN, JUN = "alfa_pme_df_2026-01.pdf", "alfa_pme_df_2026-06.pdf"


def ingerir(amostras, fonte, nome):
    return ingerir_documento((amostras / nome).read_bytes(), nome, fonte)


def publicar_janeiro(amostras, fonte):
    _, tabelas = ingerir(amostras, fonte, JAN)
    for t in tabelas:
        publicacao.aprovar(t, "ana")
    return tabelas


def test_ingestao_cria_tabelas_em_revisao(amostras, fonte):
    documento, tabelas = ingerir(amostras, fonte, JAN)
    assert documento.status == "extraido"
    assert len(tabelas) == 3
    assert all(t.status == "em_revisao" and not t.tem_erro for t in tabelas)
    fonte.refresh_from_db()
    assert fonte.ultima_verificacao is not None


def test_documento_duplicado_e_recusado(amostras, fonte):
    ingerir(amostras, fonte, JAN)
    with pytest.raises(DocumentoDuplicado):
        ingerir(amostras, fonte, JAN)


def test_erro_de_digitacao_bloqueia_ate_correcao(amostras, fonte):
    publicar_janeiro(amostras, fonte)
    _, tabelas = ingerir(amostras, fonte, JUN)
    premium = next(t for t in tabelas if t.plano.nome == "Premium Apartamento")
    assert premium.tem_erro

    with pytest.raises(publicacao.OperacaoInvalida):
        publicacao.aprovar(premium, "ana")

    publicacao.corrigir_valor(premium, 10, Decimal("2466.96"), "ana")
    premium.refresh_from_db()
    assert not premium.tem_erro
    assert premium.valores.get(faixa=10).corrigido_manualmente

    publicacao.aprovar(premium, "ana")
    premium.refresh_from_db()
    assert premium.status == "publicada" and premium.versao == 2


def test_publicacao_versiona_e_encerra_vigencia_anterior(amostras, fonte):
    publicar_janeiro(amostras, fonte)
    _, tabelas = ingerir(amostras, fonte, JUN)
    essencial = next(t for t in tabelas if t.plano.nome == "Essencial Enfermaria")
    publicacao.aprovar(essencial, "ana")

    antiga = TabelaPreco.objects.get(plano=essencial.plano, vigencia_inicio=date(2026, 1, 1))
    assert antiga.status == "substituida"
    assert antiga.vigencia_fim == date(2026, 5, 31)
    assert essencial.auditoria.filter(acao="publicada").exists()


def test_cotacao_respeita_a_data(amostras, fonte):
    publicar_janeiro(amostras, fonte)
    _, tabelas = ingerir(amostras, fonte, JUN)
    essencial = next(t for t in tabelas if t.plano.nome == "Essencial Enfermaria")
    publicacao.aprovar(essencial, "ana")

    def total(data):
        r = cotar("DF", "PME", [30, 45], data)["resultados"]
        return Decimal(next(x for x in r if x["plano"] == "Essencial Enfermaria")["total"])

    marco, julho = total(date(2026, 3, 10)), total(date(2026, 7, 10))
    assert julho > marco
    assert float(julho / marco) == pytest.approx(1.125, abs=0.002)


def test_nao_aceita_vigencia_retroativa(amostras, fonte):
    _, jun = ingerir(amostras, fonte, JUN)
    essencial_jun = next(t for t in jun if t.plano.nome == "Essencial Enfermaria")
    publicacao.aprovar(essencial_jun, "ana")
    _, jan = ingerir(amostras, fonte, JAN)
    essencial_jan = next(t for t in jan if t.plano.nome == "Essencial Enfermaria")
    with pytest.raises(publicacao.OperacaoInvalida):
        publicacao.aprovar(essencial_jan, "ana")


def test_api_fluxo_de_revisao(amostras, fonte):
    publicar_janeiro(amostras, fonte)
    api = APIClient()
    with open(amostras / JUN, "rb") as f:
        r = api.post("/api/documentos/enviar/", {"arquivo": f, "fonte_id": fonte.id}, format="multipart")
    assert r.status_code == 201
    premium_id = next(t["id"] for t in r.json()["tabelas"] if t["plano"] == "Premium Apartamento")

    detalhe = api.get(f"/api/tabelas/{premium_id}/").json()
    assert detalhe["qtd_erros"] >= 1
    assert detalhe["comparacao"][0]["variacao_pct"] == pytest.approx(12.5, abs=0.1)

    r = api.post(f"/api/tabelas/{premium_id}/aprovar/", {"usuario": "ana"}, format="json")
    assert r.status_code == 409

    r = api.patch(f"/api/tabelas/{premium_id}/valores/", {"faixa": 10, "valor": "2466.96", "usuario": "ana"},
                  format="json")
    assert r.status_code == 200 and r.json()["qtd_erros"] == 0

    r = api.post(f"/api/tabelas/{premium_id}/aprovar/", {"usuario": "ana"}, format="json")
    assert r.status_code == 200 and r.json()["versao"] == 2

    with open(amostras / JUN, "rb") as f:
        r = api.post("/api/documentos/enviar/", {"arquivo": f, "fonte_id": fonte.id}, format="multipart")
    assert r.status_code == 409

    cot = api.get("/api/cotacao/?regiao=DF&tipo=PME&idades=30,45&data=2026-07-01").json()["resultados"]
    assert cot and all("fonte" in c and "vigencia_inicio" in c for c in cot)

    m = api.get("/api/metricas/").json()
    assert m["campos_corrigidos_manualmente"] == 1
