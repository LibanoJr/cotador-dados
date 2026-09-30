"""Gera PDFs FICTÍCIOS de tabelas de preço, o gabarito da extração e a referência ANS fictícia.

Os dados são inventados. Nenhuma operadora real está representada; os registros ANS começam
com 900, faixa que não corresponde a produtos reais.

Cenário da demonstração, montado de propósito:
- Reajuste de junho da Alfa (12,5% uniforme):
  - Essencial Enfermaria passa em tudo;
  - Essencial Apartamento fica 35% acima do valor comercial da NTRP (banda de 30%), o que bloqueia
    com liberação justificada;
  - Premium Apartamento tem um erro de digitação na faixa 59+ (valor multiplicado por 10), que a
    regra das 6 vezes da RN 563/2022 bloqueia.
- Beta Vida Mais Enfermaria teve a comercialização suspensa pela ANS em 15/08/2026: sai da cotação
  a partir dessa data, mas continua aparecendo em cotações de datas anteriores.
"""
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from catalogo.servicos.faixas import FAIXAS

MULTIPLICADORES = [
    Decimal(x) for x in ("1.00", "1.18", "1.36", "1.55", "1.72", "1.95", "2.40", "3.05", "3.90", "5.50")
]
PASTA = Path(settings.BASE_DIR) / "amostras"

# Registros ANS fictícios por plano.
REGISTROS = {
    "Essencial Enfermaria": "900.101/26-1",
    "Essencial Apartamento": "900.102/26-0",
    "Premium Apartamento": "900.103/26-8",
    "Vida Mais Enfermaria": "900.201/26-5",
    "Vida Mais Apartamento": "900.202/26-3",
}

# Referência ANS fictícia: valor comercial = preço de janeiro / fator. Fator 1,20 deixa janeiro 20%
# acima da NTRP (dentro da banda) e o reajuste de 12,5% leva a 35% (fora da banda).
NTRP = {
    "Essencial Enfermaria": ("Alfa Saúde (fictícia)", "210.40", "1.05", "ativo", ""),
    "Essencial Apartamento": ("Alfa Saúde (fictícia)", "265.90", "1.20", "ativo", ""),
    "Premium Apartamento": ("Alfa Saúde (fictícia)", "398.70", "1.05", "ativo", ""),
    "Vida Mais Enfermaria": ("Beta Vida (fictícia)", "195.30", "1.05", "suspenso", "2026-08-15"),
    "Vida Mais Apartamento": ("Beta Vida (fictícia)", "248.10", "1.00", "ativo", ""),
}


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def brl(v: Decimal) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tabela_base(valor_inicial: str, reajuste: str = "0") -> dict[int, Decimal]:
    fator = 1 + Decimal(reajuste) / 100
    base = Decimal(valor_inicial)
    return {f.numero: _q(_q(base * m) * fator) for f, m in zip(FAIXAS, MULTIPLICADORES)}


AMOSTRAS = [
    {
        "arquivo": "alfa_pme_df_2026-01.pdf",
        "operadora": "Alfa Saúde (fictícia)", "regiao": "DF", "contratacao": "PME (2 a 29 vidas)",
        "tipo": "PME", "coparticipacao": False, "vigencia": "01/01/2026",
        "planos": {
            "Essencial Enfermaria": tabela_base("210.40"),
            "Essencial Apartamento": tabela_base("265.90"),
            "Premium Apartamento": tabela_base("398.70"),
        },
    },
    {
        "arquivo": "alfa_pme_df_2026-06.pdf",
        "operadora": "Alfa Saúde (fictícia)", "regiao": "DF", "contratacao": "PME (2 a 29 vidas)",
        "tipo": "PME", "coparticipacao": False, "vigencia": "01/06/2026",
        "planos": {
            "Essencial Enfermaria": tabela_base("210.40", "12.5"),
            "Essencial Apartamento": tabela_base("265.90", "12.5"),
            "Premium Apartamento": tabela_base("398.70", "12.5"),
        },
        # Erro proposital: dígito a mais digitado pela operadora/equipe (ex.: 2.466,86 -> 24.668,60)
        "erro_proposital": ("Premium Apartamento", 10),
    },
    {
        "arquivo": "beta_pme_df_2026-03.pdf",
        "operadora": "Beta Vida (fictícia)", "regiao": "DF", "contratacao": "PME",
        "tipo": "PME", "coparticipacao": True, "vigencia": "01/03/2026",
        "planos": {
            "Vida Mais Enfermaria": tabela_base("195.30"),
            "Vida Mais Apartamento": tabela_base("248.10"),
        },
    },
]


class Command(BaseCommand):
    help = "Gera PDFs fictícios de tabelas de preço em backend/amostras/ e o gabarito.json"

    def handle(self, *args, **opts):
        PASTA.mkdir(exist_ok=True)
        gabarito = {}
        estilos = getSampleStyleSheet()
        for a in AMOSTRAS:
            planos = {nome: dict(v) for nome, v in a["planos"].items()}
            if erro := a.get("erro_proposital"):
                plano, faixa = erro
                planos[plano][faixa] = planos[plano][faixa] * 10

            doc = SimpleDocTemplate(str(PASTA / a["arquivo"]), pagesize=A4)
            elementos = [
                Paragraph("MATERIAL FICTÍCIO - dados inventados para demonstração", estilos["Italic"]),
                Paragraph("Tabela de Preços", estilos["Title"]),
                Paragraph(f"Operadora: {a['operadora']}", estilos["Normal"]),
                Paragraph(f"Região: {a['regiao']}", estilos["Normal"]),
                Paragraph(f"Contratação: {a['contratacao']}", estilos["Normal"]),
                Paragraph(f"Coparticipação: {'Sim' if a['coparticipacao'] else 'Não'}", estilos["Normal"]),
                Paragraph(f"Vigência: a partir de {a['vigencia']}", estilos["Normal"]),
                Spacer(1, 16),
            ]
            nomes = list(planos)
            dados = [["Faixa etária", *nomes]]
            for f in FAIXAS:
                dados.append([f.rotulo, *[brl(planos[n][f.numero]) for n in nomes]])
            tabela = Table(dados)
            tabela.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EEF0")),
                        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ]
                )
            )
            elementos.append(tabela)
            elementos.append(Spacer(1, 16))
            elementos.append(Paragraph("Valores mensais por beneficiário, em reais.", estilos["Normal"]))
            elementos.append(Spacer(1, 12))
            registros = Table([["Plano", "Registro ANS"], *[[n, REGISTROS[n]] for n in nomes]])
            registros.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
            elementos.append(registros)
            doc.build(elementos)

            d, m, y = a["vigencia"].split("/")
            gabarito[a["arquivo"]] = {
                "operadora": a["operadora"], "regiao": a["regiao"], "tipo_contratacao": a["tipo"],
                "coparticipacao": a["coparticipacao"], "vigencia_inicio": f"{y}-{m}-{d}",
                "tabelas": {n: {str(k): str(v) for k, v in vals.items()} for n, vals in planos.items()},
                "registros": {n: REGISTROS[n] for n in planos},
            }
            self.stdout.write(f"Gerado {a['arquivo']}")

        (PASTA / "gabarito.json").write_text(json.dumps(gabarito, ensure_ascii=False, indent=2), encoding="utf-8")
        self._gerar_referencia_ans()
        self.stdout.write(self.style.SUCCESS(f"Amostras, gabarito e referência ANS em {PASTA}"))

    def _gerar_referencia_ans(self):
        pasta = PASTA / "ans"
        pasta.mkdir(exist_ok=True)
        produtos = ["REGISTRO_PLANO;NM_PLANO;RAZAO_SOCIAL;CONTRATACAO;SITUACAO;DT_SITUACAO"]
        valores = ["REGISTRO_PLANO;FAIXA_ETARIA;VL_COMERCIAL_MENSALIDADE"]
        for nome, (operadora, base, fator, situacao, desde) in NTRP.items():
            registro = REGISTROS[nome]
            produtos.append(f"{registro};{nome};{operadora};Coletivo empresarial;{situacao};{desde}")
            for f, v in tabela_base(base).items():
                vcm = _q(v / Decimal(fator))
                valores.append(f"{registro};{FAIXAS[f - 1].rotulo};{brl(vcm)}")
        # Um produto a mais, sem tabela no cotador, como numa base real.
        produtos.append("900.301/26-2;Gama Básico;Gama Saúde (fictícia);Coletivo por adesão;ativo;")
        (pasta / "produtos.csv").write_text("\n".join(produtos) + "\n", encoding="utf-8")
        (pasta / "valor_comercial.csv").write_text("\n".join(valores) + "\n", encoding="utf-8")
