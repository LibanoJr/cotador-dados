"""Endpoints de apoio: original do documento, amostras, reinício da demonstração e restrição de vigência."""
from datetime import date

import pytest
from django.db import IntegrityError, connection, transaction
from rest_framework.test import APIClient

from catalogo.models import DocumentoFonte, ProdutoANS, TabelaPreco
from catalogo.servicos import publicacao
from catalogo.servicos.ingestao import ingerir_documento

pytestmark = pytest.mark.django_db
JAN = "alfa_pme_df_2026-01.pdf"


@pytest.mark.parametrize("no_banco", [True, False])
def test_original_e_servido_pela_api(amostras, fonte, settings, no_banco):
    settings.ORIGINAIS_NO_BANCO = no_banco
    documento, _ = ingerir_documento((amostras / JAN).read_bytes(), JAN, fonte)
    r = APIClient().get(f"/api/documentos/{documento.id}/original/")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    corpo = b"".join(r.streaming_content) if r.streaming else r.content
    assert corpo.startswith(b"%PDF")
    assert (DocumentoFonte.objects.get().conteudo is not None) == no_banco


def test_amostras_listadas_e_protegidas(amostras):
    api = APIClient()
    lista = api.get("/api/amostras/").json()
    assert JAN in lista["amostras"] and lista["sugerida"].endswith(".pdf")
    assert api.get(f"/api/amostras/{JAN}/").status_code == 200
    assert api.get("/api/amostras/..%2Fconfig%2Fsettings.py/").status_code == 404


def test_reinicio_da_demo(settings, amostras):
    api = APIClient()
    settings.DEMO_PERMITE_REINICIAR = False
    assert api.post("/api/demo/reiniciar/").status_code == 403

    settings.DEMO_PERMITE_REINICIAR = True
    assert api.post("/api/demo/reiniciar/").status_code == 200
    assert TabelaPreco.objects.filter(status="publicada").count() == 5
    assert ProdutoANS.objects.count() == 6
    assert api.post("/api/demo/reiniciar/").status_code == 200  # idempotente
    assert TabelaPreco.objects.filter(status="publicada").count() == 5


def test_aprovar_com_justificativa_pela_api(amostras, fonte, referencia_ans):
    for t in ingerir_documento((amostras / JAN).read_bytes(), JAN, fonte)[1]:
        publicacao.aprovar(t, "ana")
    _, jun = ingerir_documento((amostras / "alfa_pme_df_2026-06.pdf").read_bytes(), "alfa_pme_df_2026-06.pdf", fonte)
    apto = next(t for t in jun if t.plano.nome == "Essencial Apartamento")
    api = APIClient()
    resumo = api.get("/api/tabelas/?status=em_revisao").json()
    item = next(t for t in resumo if t["id"] == apto.id)
    assert item["qtd_erros"] == 0 and item["qtd_liberaveis"] == 1

    assert api.post(f"/api/tabelas/{apto.id}/aprovar/", {"usuario": "ana"}, format="json").status_code == 409
    r = api.post(f"/api/tabelas/{apto.id}/aprovar/", {"usuario": "ana", "justificativa": "confirmado"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "publicada"

    # Depois de publicada, a tabela se compara com a versão que substituiu (janeiro), e não fica sem referência.
    detalhe = api.get(f"/api/tabelas/{apto.id}/").json()
    assert detalhe["comparacao_tipo"] == "anterior" and detalhe["versao_vigente_id"] is not None
    assert all(abs(float(c["variacao_pct"]) - 12.5) < 0.1 for c in detalhe["comparacao"])
    em_revisao = api.get(f"/api/tabelas/{next(t.id for t in jun if t.plano.nome == 'Premium Apartamento')}/").json()
    assert em_revisao["comparacao_tipo"] == "vigente"
    assert api.get("/api/metricas/").json()["bloqueios_liberados_com_justificativa"] == 1


def test_vincular_registro_pela_api(amostras, fonte):
    _, tabelas = ingerir_documento((amostras / JAN).read_bytes(), JAN, fonte)
    plano_id = tabelas[0].plano_id
    api = APIClient()
    assert api.patch(f"/api/planos/{plano_id}/registro/", {"registro_ans": ""}, format="json").status_code == 400
    r = api.patch(f"/api/planos/{plano_id}/registro/", {"registro_ans": "900.999/26-0", "usuario": "ana"},
                  format="json")
    assert r.status_code == 200 and r.json()["registro_ans"] == "900.999/26-0"


@pytest.mark.skipif(connection.vendor != "postgresql", reason="restrição de exclusão existe só no PostgreSQL")
def test_banco_recusa_duas_versoes_vigentes(amostras, fonte):
    for t in ingerir_documento((amostras / JAN).read_bytes(), JAN, fonte)[1]:
        publicacao.aprovar(t, "ana")
    publicada = TabelaPreco.objects.filter(status="publicada").first()
    publicada.pk = None  # clona a tabela publicada, com vigência aberta sobreposta
    publicada.vigencia_inicio = date(2026, 3, 1)
    with pytest.raises(IntegrityError), transaction.atomic():
        publicada.save()


def test_fonte_ans_nao_recebe_documento(amostras):
    from catalogo.models import FonteDados

    ans = FonteDados.objects.create(nome="ANS", tipo="ans")
    with open(amostras / JAN, "rb") as f:
        r = APIClient().post("/api/documentos/enviar/", {"arquivo": f, "fonte_id": ans.id}, format="multipart")
    assert r.status_code == 400 and "sincronização" in r.json()["erro"]


def test_documento_na_fonte_de_outra_operadora_gera_alerta(amostras):
    from catalogo.models import FonteDados, Operadora

    beta = Operadora.objects.create(nome="Beta Vida (fictícia)")
    fonte_beta = FonteDados.objects.create(nome="Beta: portal", tipo="portal", operadora=beta)
    _, tabelas = ingerir_documento((amostras / JAN).read_bytes(), JAN, fonte_beta)  # PDF é da Alfa
    alerta = next(v for v in tabelas[0].validacoes if v["codigo"] == "FONTE_DE_OUTRA_OPERADORA")
    assert alerta["severidade"] == "alerta" and "Alfa" in alerta["mensagem"]


def test_cotacao_informa_liberacao_justificada(amostras, fonte, referencia_ans):
    from catalogo.servicos.cotacao import cotar

    for t in ingerir_documento((amostras / JAN).read_bytes(), JAN, fonte)[1]:
        publicacao.aprovar(t, "ana")
    jun = "alfa_pme_df_2026-06.pdf"
    apto = next(t for t in ingerir_documento((amostras / jun).read_bytes(), jun, fonte)[1]
                if t.plano.nome == "Essencial Apartamento")
    publicacao.aprovar(apto, "ana", justificativa="confirmado com o comercial")
    r = cotar("DF", "PME", [30], date(2026, 7, 1))["resultados"]
    item = next(x for x in r if x["plano"] == "Essencial Apartamento")
    assert item["liberado_com_justificativa"] == "confirmado com o comercial"
    assert all(x["liberado_com_justificativa"] is None for x in r if x["plano"] != "Essencial Apartamento")


def test_mensagens_em_formato_brasileiro():
    from decimal import Decimal

    from catalogo.servicos.validacao import validar_tabela

    valores = {n: Decimal("100") * n for n in range(1, 11)}
    valores[10] = Decimal("1000.50")
    msgs = " ".join(v["mensagem"] for v in validar_tabela(valores))
    assert "10,01 vezes" in msgs and "R$ 1.000,50" in msgs
