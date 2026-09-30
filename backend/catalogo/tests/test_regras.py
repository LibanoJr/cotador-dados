from decimal import Decimal

import pytest

from catalogo.servicos.faixas import faixa_por_idade, faixa_por_rotulo
from catalogo.servicos.numeros import parse_brl
from catalogo.servicos.validacao import validar_tabela

MULT = ["1.00", "1.18", "1.36", "1.55", "1.72", "1.95", "2.40", "3.05", "3.90", "5.50"]


def tabela(base="100.00"):
    return {i + 1: (Decimal(base) * Decimal(m)).quantize(Decimal("0.01")) for i, m in enumerate(MULT)}


def codigos(resultado, severidade=None):
    return {r["codigo"] for r in resultado if severidade is None or r["severidade"] == severidade}


@pytest.mark.parametrize("idade,faixa", [(0, 1), (18, 1), (19, 2), (43, 6), (44, 7), (58, 9), (59, 10), (90, 10)])
def test_faixa_por_idade(idade, faixa):
    assert faixa_por_idade(idade) == faixa


@pytest.mark.parametrize("rotulo,faixa", [("0 a 18", 1), ("00-18", 1), ("44 a 48", 7), ("59 ou mais", 10), ("59+", 10)])
def test_faixa_por_rotulo(rotulo, faixa):
    assert faixa_por_rotulo(rotulo) == faixa


def test_parse_brl():
    assert parse_brl("R$ 1.234,56") == Decimal("1234.56")
    assert parse_brl("210,40") == Decimal("210.40")
    assert parse_brl("abc") is None


def test_tabela_correta_nao_tem_erros():
    assert codigos(validar_tabela(tabela()), "erro") == set()


def test_faixa_ausente_e_erro():
    t = tabela()
    del t[5]
    assert "FAIXAS_INCOMPLETAS" in codigos(validar_tabela(t), "erro")


def test_rn63_limite_6x():
    t = tabela()
    t[10] = t[1] * 7
    assert "RN563_LIMITE_6X" in codigos(validar_tabela(t), "erro")


def test_rn63_variacao_7_a_10():
    t = tabela()
    t[7] = Decimal("150.00")  # 1->7: +50%
    t[8], t[9], t[10] = Decimal("200.00"), Decimal("250.00"), Decimal("300.00")  # 7->10: +100%
    assert "RN563_VARIACAO_7_10" in codigos(validar_tabela(t), "erro")


def test_variacao_negativa_entre_faixas_e_erro():
    t = tabela()
    t[8] = t[7] - Decimal("1")
    assert "VALOR_DECRESCENTE" in codigos(validar_tabela(t), "erro")


def test_variacao_atipica_contra_versao_anterior():
    anterior = tabela()
    nova = tabela("112.50")
    nova[3] = anterior[3] * 2
    r = validar_tabela(nova, anterior)
    assert "VARIACAO_ATIPICA" in codigos(r, "alerta")
    assert "REAJUSTE_NAO_UNIFORME" in codigos(r, "info")


def test_reajuste_uniforme_e_reconhecido():
    r = validar_tabela(tabela("112.50"), tabela())
    assert "REAJUSTE_UNIFORME" in codigos(r, "info")
    assert codigos(r, "alerta") == set()
