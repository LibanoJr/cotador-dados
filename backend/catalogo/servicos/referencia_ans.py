"""Nível 3 da validação: cruzamento com a referência oficial da ANS.

É a verificação independente que falta no processo manual de hoje: o documento da operadora é
conferido contra uma fonte que não é a operadora.

Regras:
- produto com registro existe e pode ser vendido (não suspenso nem cancelado);
- cada faixa dentro da banda de comercialização em torno do valor comercial da NTRP (±30%);
- o padrão entre faixas da tabela de venda acompanha o da NTRP. A ANS exige que a variação entre
  os valores comerciais de cada faixa mantenha relação com a praticada na tabela de venda.

A regra da banda bloqueia, mas o revisor pode liberar com justificativa (`liberavel`), porque um
preço fora da banda tem três explicações possíveis: erro nosso (o mais provável), nota técnica
desatualizada na base da ANS ou descumprimento pela operadora. A justificativa fica na auditoria.
"""
from decimal import Decimal

from django.conf import settings

from catalogo.servicos.faixas import FAIXAS, NUMEROS_FAIXAS
from catalogo.servicos.numeros import num_br

ROTULOS = {f.numero: f.rotulo for f in FAIXAS}


def _item(codigo, severidade, mensagem, faixas=None, liberavel=False):
    item = {"codigo": codigo, "severidade": severidade, "mensagem": mensagem, "nivel": "ans"}
    if faixas:
        item["faixas"] = faixas
        if len(faixas) == 1:
            item["faixa"] = faixas[0]
    if liberavel:
        item["liberavel"] = True
    return item


def _lista(faixas):
    if len(faixas) == len(NUMEROS_FAIXAS):
        return "todas as faixas"
    return ("faixa " if len(faixas) == 1 else "faixas ") + ", ".join(ROTULOS[f] for f in faixas)


def validar_contra_ans(registro_ans: str, valores: dict[int, Decimal], data_venda) -> list[dict]:
    from catalogo.models import ProdutoANS

    if not ProdutoANS.objects.exists():
        return [_item("ANS_SEM_REFERENCIA", "info", "Referência ANS ainda não sincronizada; cruzamento não aplicado")]

    if not registro_ans:
        return [
            _item(
                "ANS_SEM_REGISTRO", "alerta",
                "Plano sem registro ANS vinculado: não dá para conferir situação nem banda de preço. "
                "Vincule o registro uma vez; as próximas tabelas deste plano serão conferidas sozinhas.",
            )
        ]

    produto = ProdutoANS.objects.filter(registro_ans=registro_ans).prefetch_related("valores_comerciais").first()
    if not produto:
        return [
            _item(
                "ANS_REGISTRO_DESCONHECIDO", "alerta",
                f"Registro {registro_ans} não encontrado na referência ANS de "
                f"{ProdutoANS.objects.latest('data_referencia').data_referencia:%d/%m/%Y}. "
                "Pode ser erro de digitação no documento ou produto novo ainda fora da base.",
            )
        ]

    resultado = []
    if not produto.vendavel_em(data_venda):
        desde = f" desde {produto.situacao_desde:%d/%m/%Y}" if produto.situacao_desde else ""
        resultado.append(
            _item(
                f"ANS_PRODUTO_{produto.situacao.upper()}", "erro",
                f"Registro {registro_ans} está com situação '{produto.get_situacao_display()}'{desde} na ANS",
            )
        )

    referencia = {v.faixa: v.valor for v in produto.valores_comerciais.all()}
    if not referencia:
        resultado.append(_item("ANS_SEM_VALOR_COMERCIAL", "info", "Produto sem valor comercial de NTRP na base"))
        return resultado

    banda = Decimal(str(settings.BANDA_ANS_PCT)) / 100
    acima, abaixo, desvios = [], [], []
    for n in NUMEROS_FAIXAS:
        preco, vcm = valores.get(n), referencia.get(n)
        if not preco or not vcm:
            continue
        if preco > vcm * (1 + banda):
            acima.append(n)
            desvios.append(float((preco / vcm - 1) * 100))
        elif preco < vcm * (1 - banda):
            abaixo.append(n)
            desvios.append(float((preco / vcm - 1) * 100))
    ref = f"valor comercial da NTRP (referência ANS de {produto.data_referencia:%d/%m/%Y})"
    pior = max(desvios, key=abs) if desvios else 0
    if acima:
        resultado.append(
            _item(
                "ANS_ACIMA_DA_BANDA", "erro",
                f"Preço acima do teto em {_lista(acima)}: até {num_br(pior, sinal=True)}% sobre o {ref}; "
                f"o limite é +{num_br(settings.BANDA_ANS_PCT, 0)}%",
                acima, liberavel=True,
            )
        )
    if abaixo:
        resultado.append(
            _item(
                "ANS_ABAIXO_DA_BANDA", "erro",
                f"Preço abaixo do piso em {_lista(abaixo)}: até {num_br(pior, sinal=True)}% sob o {ref}; "
                f"o limite é -{num_br(settings.BANDA_ANS_PCT, 0)}%",
                abaixo, liberavel=True,
            )
        )

    # Padrão entre faixas: razão de cada faixa sobre a primeira, na venda e na NTRP.
    if valores.get(1) and referencia.get(1):
        tolerancia = settings.TOLERANCIA_PADRAO_FAIXAS_PCT
        destoantes = []
        for n in NUMEROS_FAIXAS[1:]:
            if valores.get(n) and referencia.get(n):
                venda = valores[n] / valores[1]
                ntrp = referencia[n] / referencia[1]
                if abs(float((venda - ntrp) / ntrp * 100)) > tolerancia:
                    destoantes.append(n)
        if destoantes:
            resultado.append(
                _item(
                    "ANS_PADRAO_FAIXAS_DIFERENTE", "alerta",
                    f"A proporção entre faixas difere da NTRP na {_lista(destoantes)}. "
                    "Sinal comum de valor trocado entre faixas ou de erro de digitação.",
                    destoantes,
                )
            )
    return resultado
