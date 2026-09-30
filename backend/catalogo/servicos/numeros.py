from decimal import Decimal, InvalidOperation


def parse_brl(texto: str) -> Decimal | None:
    """Converte '1.234,56' ou 'R$ 1.234,56' em Decimal('1234.56'). Retorna None se inválido."""
    if texto is None:
        return None
    t = str(texto).replace("R$", "").replace("\xa0", " ").strip()
    if not t:
        return None
    t = t.replace(".", "").replace(",", ".")
    try:
        return Decimal(t).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def num_br(valor, casas: int = 1, sinal: bool = False) -> str:
    """Formata número no padrão brasileiro: 1.234,5 (sinal opcional: +12,5)."""
    texto = f"{float(valor):{'+' if sinal else ''},.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")
