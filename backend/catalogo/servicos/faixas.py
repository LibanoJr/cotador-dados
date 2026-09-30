"""Faixas etárias dos planos contratados a partir de 01/01/2004.

Base: RN ANS 563/2022, que revogou a RN 63/2003 mantendo o mesmo texto (art. 2º).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Faixa:
    numero: int
    idade_min: int
    idade_max: int | None
    rotulo: str


FAIXAS: tuple[Faixa, ...] = (
    Faixa(1, 0, 18, "0 a 18"),
    Faixa(2, 19, 23, "19 a 23"),
    Faixa(3, 24, 28, "24 a 28"),
    Faixa(4, 29, 33, "29 a 33"),
    Faixa(5, 34, 38, "34 a 38"),
    Faixa(6, 39, 43, "39 a 43"),
    Faixa(7, 44, 48, "44 a 48"),
    Faixa(8, 49, 53, "49 a 53"),
    Faixa(9, 54, 58, "54 a 58"),
    Faixa(10, 59, None, "59 ou mais"),
)

NUMEROS_FAIXAS = tuple(f.numero for f in FAIXAS)


def faixa_por_idade(idade: int) -> int:
    if idade < 0:
        raise ValueError("Idade inválida")
    for f in FAIXAS:
        if f.idade_max is None or idade <= f.idade_max:
            if idade >= f.idade_min:
                return f.numero
    raise ValueError("Idade inválida")


def faixa_por_rotulo(texto: str) -> int | None:
    """Reconhece rótulos comuns em tabelas: '0 a 18', '00-18', '59+', '59 ou mais'."""
    import re

    t = texto.strip().lower()
    m = re.match(r"^(\d{1,2})\s*(?:a|-|–|até)\s*(\d{1,2})", t)
    if m:
        ini = int(m.group(1))
    else:
        m = re.match(r"^(\d{1,2})\s*(?:\+|ou mais|anos ou mais|em diante)", t)
        if not m:
            return None
        ini = int(m.group(1))
    for f in FAIXAS:
        if f.idade_min == ini:
            return f.numero
    return None
