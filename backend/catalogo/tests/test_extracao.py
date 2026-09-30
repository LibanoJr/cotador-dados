"""Extração: ancoragem no texto do documento, extrator LLM com cliente simulado e reprocessamento."""
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from catalogo.models import DocumentoFonte
from catalogo.servicos.extracao import ErroExtracao, ExtratorLLM, ancorar, texto_paginas
from catalogo.servicos.ingestao import ingerir_documento

JAN = "alfa_pme_df_2026-01.pdf"


class ClienteFalso:
    """Imita anthropic.Anthropic().messages.create devolvendo um texto fixo."""

    def __init__(self, texto):
        self.messages = SimpleNamespace(create=lambda **_: SimpleNamespace(
            content=[SimpleNamespace(type="text", text=texto)]
        ))


def resposta_llm(amostras, inventar=False, sem_trecho=False):
    gabarito = json.loads((amostras / "gabarito.json").read_text(encoding="utf-8"))[JAN]
    valores = dict(gabarito["tabelas"]["Essencial Enfermaria"])
    if inventar:
        valores["5"] = "999.99"  # plausível, mas não está no documento
    trechos = {k: f"linha {k}" for k in valores}
    if sem_trecho:
        trechos.pop("3")
    return json.dumps({
        "operadora": gabarito["operadora"], "regiao": "DF", "tipo_contratacao": "PME",
        "coparticipacao": False, "vigencia_inicio": gabarito["vigencia_inicio"],
        "tabelas": [{"plano": "Essencial Enfermaria", "registro_ans": "900.101/26-1", "acomodacao": "enfermaria",
                     "pagina": 1, "valores": valores, "trechos": trechos}],
        "avisos": [],
    })


def extrair_llm(amostras, **kw):
    conteudo = (amostras / JAN).read_bytes()
    r = ExtratorLLM(cliente=ClienteFalso(resposta_llm(amostras, **kw))).extrair(conteudo)
    return ancorar(r, texto_paginas(conteudo))


def test_llm_valido_passa_intacto(amostras):
    r = extrair_llm(amostras)
    assert len(r.tabelas[0].valores) == 10 and not r.avisos


def test_valor_inventado_pelo_llm_e_descartado(amostras):
    r = extrair_llm(amostras, inventar=True)
    assert 5 not in r.tabelas[0].valores
    assert any("999,99" in a and "não encontrado" in a for a in r.avisos)


def test_valor_sem_trecho_de_origem_e_descartado(amostras):
    r = extrair_llm(amostras, sem_trecho=True)
    assert 3 not in r.tabelas[0].valores
    assert any("sem trecho" in a for a in r.avisos)


def test_resposta_fora_do_formato_vira_erro(amostras):
    with pytest.raises(ErroExtracao, match="JSON"):
        ExtratorLLM(cliente=ClienteFalso("não é json")).extrair((amostras / JAN).read_bytes())


def test_llm_sem_chave_explica_o_motivo(amostras, settings):
    settings.ANTHROPIC_API_KEY = ""
    with pytest.raises(ErroExtracao, match="ANTHROPIC_API_KEY"):
        ExtratorLLM().extrair((amostras / JAN).read_bytes())


@pytest.mark.django_db
def test_valor_descartado_bloqueia_na_validacao(amostras, fonte, monkeypatch):
    from catalogo.servicos import extracao

    monkeypatch.setitem(
        extracao.EXTRATORES, "llm",
        lambda: ExtratorLLM(cliente=ClienteFalso(resposta_llm(amostras, inventar=True))),
    )
    _, tabelas = ingerir_documento((amostras / JAN).read_bytes(), JAN, fonte, metodo="llm")
    assert "FAIXAS_INCOMPLETAS" in {v["codigo"] for v in tabelas[0].validacoes}
    assert tabelas[0].valores.count() == 9


@pytest.mark.django_db
def test_documento_que_falhou_pode_ser_reenviado(amostras, fonte, monkeypatch):
    from catalogo.servicos import extracao

    monkeypatch.setitem(extracao.EXTRATORES, "llm", lambda: ExtratorLLM(cliente=ClienteFalso("quebrado")))
    with pytest.raises(ErroExtracao):
        ingerir_documento((amostras / JAN).read_bytes(), JAN, fonte, metodo="llm")
    assert DocumentoFonte.objects.get().status == "erro"

    documento, tabelas = ingerir_documento((amostras / JAN).read_bytes(), JAN, fonte)
    assert documento.status == "extraido" and len(tabelas) == 3
    assert DocumentoFonte.objects.count() == 1


def test_ancoragem_aceita_formato_brasileiro():
    from catalogo.servicos.extracao import ResultadoExtracao, TabelaExtraida

    r = ResultadoExtracao(
        operadora="X", regiao="DF", tipo_contratacao="PME", coparticipacao=False,
        vigencia_inicio="2026-01-01", metodo="teste",
        tabelas=[TabelaExtraida(plano="P", pagina=1, valores={1: Decimal("1234.56"), 2: Decimal("99.90")})],
    )
    ancorar(r, ["Faixa 0 a 18 R$ 1.234,56"])
    assert r.tabelas[0].valores == {1: Decimal("1234.56")}
