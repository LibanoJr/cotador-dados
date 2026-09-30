"""Regras de validação de tabelas de preço.

Funções puras (sem banco) para facilitar teste e reuso.
Severidades:
- erro   -> bloqueia a aprovação até ser corrigido
- alerta -> exige atenção do revisor, mas não bloqueia
- info   -> contexto útil para a revisão
"""
from decimal import Decimal

from django.conf import settings

from catalogo.servicos.faixas import FAIXAS, NUMEROS_FAIXAS
from catalogo.servicos.numeros import num_br


def _brl(v: Decimal) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

ROTULOS = {f.numero: f.rotulo for f in FAIXAS}


def _item(codigo, severidade, mensagem, faixa=None):
    item = {"codigo": codigo, "severidade": severidade, "mensagem": mensagem}
    if faixa is not None:
        item["faixa"] = faixa
    return item


def _pct(novo: Decimal, antigo: Decimal) -> float:
    return float((novo - antigo) / antigo * 100)


def validar_tabela(valores: dict[int, Decimal], anteriores: dict[int, Decimal] | None = None) -> list[dict]:
    resultado: list[dict] = []

    faltando = [n for n in NUMEROS_FAIXAS if n not in valores]
    if faltando:
        resultado.append(
            _item("FAIXAS_INCOMPLETAS", "erro", f"Faixas ausentes: {', '.join(ROTULOS[n] for n in faltando)}")
        )

    for n, v in sorted(valores.items()):
        if v is None or v <= 0:
            resultado.append(_item("VALOR_INVALIDO", "erro", "Valor deve ser maior que zero", n))

    completos = not faltando and all(v and v > 0 for v in valores.values())
    if completos:
        v1, v7, v10 = valores[1], valores[7], valores[10]

        # RN 563/2022 (antiga RN 63/2003), art. 3º, I: a 10ª faixa não pode passar de 6x a 1ª.
        if v10 > v1 * 6:
            resultado.append(
                _item(
                    "RN563_LIMITE_6X", "erro",
                    f"Faixa 59+ ({_brl(v10)}) é {num_br(v10 / v1, 2)} vezes a faixa 0-18 ({_brl(v1)}); o limite é 6 vezes",
                    10,
                )
            )

        # Art. 3º, II: variação acumulada 7ª→10ª <= variação acumulada 1ª→7ª.
        # "Variação acumulada" no sentido matemático (razão entre valores), conforme STJ Tema 1.016.
        var_1_7 = _pct(v7, v1)
        var_7_10 = _pct(v10, v7)
        if var_7_10 > var_1_7:
            resultado.append(
                _item(
                    "RN563_VARIACAO_7_10", "erro",
                    f"Variação da faixa 44-48 até 59+ ({num_br(var_7_10)}%) supera a da faixa 0-18 até 44-48 "
                    f"({num_br(var_1_7)}%)",
                )
            )

        # Art. 3º, III (incluído pela RN 254/2011): variações por mudança de faixa não podem ser negativas.
        for n in NUMEROS_FAIXAS[1:]:
            if valores[n] < valores[n - 1]:
                resultado.append(
                    _item(
                        "VALOR_DECRESCENTE", "erro",
                        f"Faixa {ROTULOS[n]} ({_brl(valores[n])}) é mais barata que a anterior ({_brl(valores[n - 1])})",
                        n,
                    )
                )

    if anteriores:
        limite = settings.LIMITE_VARIACAO_ALERTA
        variacoes = []
        for n in NUMEROS_FAIXAS:
            novo, antigo = valores.get(n), anteriores.get(n)
            if novo and antigo:
                var = _pct(novo, antigo)
                variacoes.append(var)
                if abs(var) > limite:
                    resultado.append(
                        _item(
                            "VARIACAO_ATIPICA", "alerta",
                            f"Faixa {ROTULOS[n]} variou {num_br(var, sinal=True)}% em relação à versão vigente "
                            f"(limite {num_br(limite, 0)}%)",
                            n,
                        )
                    )
        if variacoes:
            menor, maior = min(variacoes), max(variacoes)
            if maior - menor > 1.0:
                resultado.append(
                    _item(
                        "REAJUSTE_NAO_UNIFORME", "info",
                        f"Reajuste varia entre {num_br(menor, sinal=True)}% e {num_br(maior, sinal=True)}% conforme a faixa",
                    )
                )
            else:
                resultado.append(
                    _item("REAJUSTE_UNIFORME", "info", f"Reajuste uniforme de aproximadamente {num_br(maior, sinal=True)}%")
                )

    return resultado


def comparar(valores: dict[int, Decimal], anteriores: dict[int, Decimal] | None) -> list[dict]:
    linhas = []
    for f in FAIXAS:
        novo = valores.get(f.numero)
        antigo = (anteriores or {}).get(f.numero)
        linhas.append(
            {
                "faixa": f.numero,
                "rotulo": f.rotulo,
                "anterior": str(antigo) if antigo is not None else None,
                "novo": str(novo) if novo is not None else None,
                "variacao_pct": round(_pct(novo, antigo), 2) if novo and antigo else None,
            }
        )
    return linhas
