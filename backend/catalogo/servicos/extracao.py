"""Extração de tabelas de preço a partir de PDFs.

Dois extratores com a mesma interface:
- ExtratorDeterministico: pdfplumber + regras. Sem custo e sem chave. Funciona para o layout das amostras
  e, em produção, para operadoras cujo layout já foi mapeado ("perfil de layout").
- ExtratorLLM: envia o texto do PDF a um LLM e valida a resposta com o mesmo schema Pydantic.
  Útil para layouts novos. NÃO testado neste ambiente (exige ANTHROPIC_API_KEY).

Os dois extratores recebem o conteúdo em bytes, não um caminho: assim a extração não depende de
onde o original está guardado (disco local, S3 ou banco).

Depois de qualquer extrator, `ancorar` faz uma verificação simbólica: cada valor extraído precisa
aparecer, escrito no formato brasileiro, no texto da página indicada. O que não aparece é descartado
e vira aviso. Isso pega a alucinação clássica do LLM (valor plausível que não está no documento)
sem custo e sem depender do próprio LLM.

Em todos os casos, a saída passa pela validação e pela revisão humana antes de ser publicada.
"""
import io
import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

import pdfplumber
from django.conf import settings
from pydantic import BaseModel, Field, field_validator

from catalogo.servicos.faixas import faixa_por_rotulo
from catalogo.servicos.numeros import parse_brl


class ErroExtracao(Exception):
    pass


class TabelaExtraida(BaseModel):
    plano: str
    registro_ans: str = ""
    acomodacao: Literal["enfermaria", "apartamento", ""] = ""
    pagina: int | None = None
    valores: dict[int, Decimal]
    trechos: dict[int, str] = Field(default_factory=dict)

    @field_validator("valores")
    @classmethod
    def faixas_validas(cls, v):
        invalidas = [k for k in v if k < 1 or k > 10]
        if invalidas:
            raise ValueError(f"Faixas fora do intervalo 1-10: {invalidas}")
        return v


class ResultadoExtracao(BaseModel):
    operadora: str
    regiao: str
    tipo_contratacao: Literal["PF", "PME", "ADESAO"]
    coparticipacao: bool
    vigencia_inicio: date
    tabelas: list[TabelaExtraida]
    metodo: str
    avisos: list[str] = Field(default_factory=list)


def _abrir(conteudo: bytes):
    return pdfplumber.open(io.BytesIO(conteudo))


def texto_paginas(conteudo: bytes) -> list[str]:
    with _abrir(conteudo) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages]


def formatar_brl(valor: Decimal) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _normalizar_registro(texto: str) -> str:
    return re.sub(r"\s+", "", texto or "")


def ancorar(resultado: "ResultadoExtracao", textos: list[str]) -> "ResultadoExtracao":
    """Descarta valores que não aparecem literalmente no texto do documento.

    Compara a forma brasileira do número (ex.: 1.234,56) com o texto da página indicada; se a
    página não foi informada, procura no documento inteiro. Faixa descartada volta como ausente,
    o que dispara o erro de faixas incompletas na validação e leva o revisor a conferir o original.
    """
    documento = "\n".join(textos)
    for tabela in resultado.tabelas:
        if tabela.pagina and 1 <= tabela.pagina <= len(textos):
            base = textos[tabela.pagina - 1]
        else:
            base = documento
        compacto = base.replace(" ", "")
        for faixa, valor in list(tabela.valores.items()):
            if formatar_brl(valor).replace(" ", "") not in compacto:
                del tabela.valores[faixa]
                tabela.trechos.pop(faixa, None)
                resultado.avisos.append(
                    f"{tabela.plano}, faixa {faixa}: valor {formatar_brl(valor)} não encontrado no documento; descartado"
                )
    return resultado


def _inferir_acomodacao(nome: str) -> str:
    n = nome.lower()
    if "apart" in n or "apto" in n:
        return "apartamento"
    if "enf" in n:
        return "enfermaria"
    return ""


def _normalizar_contratacao(texto: str) -> str:
    t = texto.lower()
    if "ades" in t:
        return "ADESAO"
    if "pme" in t or "empresa" in t:
        return "PME"
    if "individual" in t or "famil" in t or t.strip() == "pf":
        return "PF"
    raise ErroExtracao(f"Tipo de contratação não reconhecido: {texto!r}")


class ExtratorDeterministico:
    nome = "deterministico"

    PADROES = {
        "operadora": r"Operadora:\s*(.+)",
        "regiao": r"Regi[aã]o:\s*(.+)",
        "contratacao": r"Contrata[cç][aã]o:\s*(.+)",
        "coparticipacao": r"Coparticipa[cç][aã]o:\s*(Sim|N[aã]o)",
        "vigencia": r"Vig[eê]ncia:.*?(\d{2}/\d{2}/\d{4})",
    }

    def extrair(self, conteudo: bytes) -> ResultadoExtracao:
        textos = texto_paginas(conteudo)
        cabecalho = textos[0] if textos else ""
        meta = {}
        for chave, padrao in self.PADROES.items():
            m = re.search(padrao, cabecalho, flags=re.IGNORECASE)
            if not m:
                raise ErroExtracao(f"Campo '{chave}' não encontrado no cabeçalho do documento")
            meta[chave] = m.group(1).strip()

        tabelas: list[TabelaExtraida] = []
        avisos: list[str] = []
        registros: dict[str, str] = {}
        with _abrir(conteudo) as pdf:
            for num_pagina, pagina in enumerate(pdf.pages, start=1):
                for tabela in pagina.extract_tables():
                    if self._eh_tabela_registros(tabela):
                        registros.update(self._ler_registros(tabela))
                    else:
                        tabelas.extend(self._ler_tabela(tabela, num_pagina, avisos))

        if not tabelas:
            raise ErroExtracao("Nenhuma tabela de preços reconhecida no documento")
        for t in tabelas:
            t.registro_ans = registros.get(t.plano, "")

        return ResultadoExtracao(
            operadora=meta["operadora"],
            regiao=meta["regiao"].upper(),
            tipo_contratacao=_normalizar_contratacao(meta["contratacao"]),
            coparticipacao=meta["coparticipacao"].lower() == "sim",
            vigencia_inicio=datetime.strptime(meta["vigencia"], "%d/%m/%Y").date(),
            tabelas=tabelas,
            metodo=self.nome,
            avisos=avisos,
        )

    @staticmethod
    def _eh_tabela_registros(linhas) -> bool:
        if not linhas:
            return False
        cabecalho = " ".join((c or "") for c in linhas[0]).lower()
        return "registro" in cabecalho and "ans" in cabecalho

    @staticmethod
    def _ler_registros(linhas) -> dict[str, str]:
        """Tabela 'Plano | Registro ANS', comum nas tabelas de venda reais."""
        return {
            (linha[0] or "").strip(): _normalizar_registro(linha[1])
            for linha in linhas[1:]
            if len(linha) >= 2 and linha[0] and linha[1]
        }

    def _ler_tabela(self, linhas, pagina, avisos) -> list[TabelaExtraida]:
        if not linhas or len(linhas) < 2:
            return []
        cabecalho = [(c or "").strip() for c in linhas[0]]
        if not cabecalho or "faixa" not in cabecalho[0].lower():
            return []
        planos = cabecalho[1:]
        por_plano = {i: {"valores": {}, "trechos": {}} for i in range(len(planos))}
        for linha in linhas[1:]:
            rotulo = (linha[0] or "").strip()
            faixa = faixa_por_rotulo(rotulo)
            if faixa is None:
                avisos.append(f"Página {pagina}: linha ignorada, faixa não reconhecida: {rotulo!r}")
                continue
            for i, celula in enumerate(linha[1:]):
                if i >= len(planos):
                    break
                valor = parse_brl(celula)
                if valor is None:
                    avisos.append(f"Página {pagina}: valor ilegível em {planos[i]} / {rotulo}: {celula!r}")
                    continue
                por_plano[i]["valores"][faixa] = valor
                por_plano[i]["trechos"][faixa] = f"p.{pagina} | {rotulo} | {celula}"
        return [
            TabelaExtraida(
                plano=nome,
                acomodacao=_inferir_acomodacao(nome),
                pagina=pagina,
                valores=dados["valores"],
                trechos=dados["trechos"],
            )
            for nome, dados in zip(planos, por_plano.values())
            if dados["valores"]
        ]


class ExtratorLLM:
    """Extrator genérico via LLM, para layouts ainda sem perfil determinístico.

    Exige ANTHROPIC_API_KEY. Os testes cobrem o tratamento da resposta com um cliente simulado
    (inclusive valor inventado sendo descartado por `ancorar`); a chamada real à API não é testada aqui.
    """

    nome = "llm"

    INSTRUCOES = (
        "Você extrai tabelas de preço de planos de saúde de documentos de operadoras brasileiras. "
        "Responda APENAS com JSON válido, sem markdown, no formato: "
        '{"operadora": str, "regiao": str (UF), "tipo_contratacao": "PF"|"PME"|"ADESAO", '
        '"coparticipacao": bool, "vigencia_inicio": "AAAA-MM-DD", '
        '"tabelas": [{"plano": str, "registro_ans": str, "acomodacao": "enfermaria"|"apartamento"|"", "pagina": int, '
        '"valores": {"1": "123.45", ..., "10": "678.90"}, "trechos": {"1": "texto literal de onde saiu"}}], '
        '"avisos": [str]}. '
        "Faixas: 1=0-18, 2=19-23, 3=24-28, 4=29-33, 5=34-38, 6=39-43, 7=44-48, 8=49-53, 9=54-58, 10=59+. "
        "Copie os valores exatamente como aparecem no documento. Cada valor precisa de um trecho literal "
        "em 'trechos'. Nunca invente valores: se algo estiver ilegível ou ausente, omita a faixa e registre "
        "em 'avisos'. Se o registro ANS do plano não aparecer, deixe registro_ans vazio."
    )

    def __init__(self, cliente=None):
        self._cliente = cliente

    def _obter_cliente(self):
        if self._cliente is not None:
            return self._cliente
        if not settings.ANTHROPIC_API_KEY:
            raise ErroExtracao("ANTHROPIC_API_KEY não configurada; use o extrator determinístico")
        import anthropic

        return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def extrair(self, conteudo: bytes) -> ResultadoExtracao:
        cliente = self._obter_cliente()
        textos = texto_paginas(conteudo)
        corpo = "\n\n".join(f"=== PÁGINA {i} ===\n{t}" for i, t in enumerate(textos, start=1))
        resposta = cliente.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=4000,
            system=self.INSTRUCOES,
            messages=[{"role": "user", "content": corpo}],
        )
        texto = "".join(b.text for b in resposta.content if getattr(b, "type", "") == "text")
        texto = re.sub(r"^```(?:json)?|```$", "", texto.strip()).strip()
        try:
            dados = json.loads(texto)
        except json.JSONDecodeError as exc:
            raise ErroExtracao(f"Resposta do LLM não é JSON válido: {exc}") from exc
        dados["metodo"] = self.nome
        try:
            resultado = ResultadoExtracao.model_validate(dados)
        except Exception as exc:  # pydantic.ValidationError
            raise ErroExtracao(f"Resposta do LLM fora do schema: {exc}") from exc
        for t in resultado.tabelas:
            t.registro_ans = _normalizar_registro(t.registro_ans)
            sem_trecho = [f for f in t.valores if not t.trechos.get(f)]
            for f in sem_trecho:
                del t.valores[f]
                resultado.avisos.append(f"{t.plano}, faixa {f}: valor sem trecho de origem; descartado")
        return resultado


EXTRATORES = {e.nome: e for e in (ExtratorDeterministico, ExtratorLLM)}


def obter_extrator(nome: str | None = None):
    nome = nome or settings.EXTRATOR_PADRAO
    if nome not in EXTRATORES:
        raise ErroExtracao(f"Extrator desconhecido: {nome}")
    return EXTRATORES[nome]()
