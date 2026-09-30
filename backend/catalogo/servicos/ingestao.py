"""Recebe um arquivo, guarda o original, extrai e cria tabelas em revisão."""
import hashlib

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from catalogo.models import (
    DocumentoFonte, FonteDados, Operadora, Plano, RegistroAuditoria, TabelaPreco, ValorFaixa,
)
from catalogo.servicos.extracao import ErroExtracao, ancorar, obter_extrator, texto_paginas
from catalogo.servicos.publicacao import calcular_validacoes


class DocumentoDuplicado(Exception):
    def __init__(self, documento):
        self.documento = documento
        super().__init__(f"Documento já recebido em {documento.recebido_em:%d/%m/%Y %H:%M} (id {documento.id})")


def _registrar_original(conteudo: bytes, nome_original: str, fonte: FonteDados, sha: str) -> DocumentoFonte:
    existente = DocumentoFonte.objects.filter(sha256=sha).first()
    if existente and existente.status != DocumentoFonte.Status.ERRO:
        raise DocumentoDuplicado(existente)
    if existente:
        # O mesmo arquivo falhou antes (ex.: layout ainda sem perfil). Reprocessa em vez de recusar.
        existente.status = DocumentoFonte.Status.RECEBIDO
        existente.mensagem_erro = ""
        existente.fonte = fonte
        existente.save(update_fields=["status", "mensagem_erro", "fonte"])
        return existente

    documento = DocumentoFonte(fonte=fonte, nome_original=nome_original, sha256=sha)
    if settings.ORIGINAIS_NO_BANCO:
        documento.conteudo = conteudo
    documento.arquivo.save(nome_original, ContentFile(conteudo), save=False)
    documento.save()
    return documento


def _vincular_registro(plano: Plano, registro: str, avisos: list[str]) -> None:
    """Primeira vez: grava o registro que veio no documento. Depois: só confere."""
    if not registro:
        return
    if not plano.registro_ans:
        plano.registro_ans = registro
        plano.save(update_fields=["registro_ans"])
    elif plano.registro_ans != registro:
        avisos.append(
            f"{plano.nome}: documento traz registro {registro}, mas o plano está vinculado a "
            f"{plano.registro_ans}. Mantido o vínculo atual; confira."
        )


def ingerir_documento(
    conteudo: bytes, nome_original: str, fonte: FonteDados, metodo: str | None = None, usuario: str = ""
) -> tuple[DocumentoFonte, list[TabelaPreco]]:
    sha = hashlib.sha256(conteudo).hexdigest()
    documento = _registrar_original(conteudo, nome_original, fonte, sha)

    extrator = obter_extrator(metodo)
    documento.metodo_extracao = extrator.nome
    try:
        resultado = ancorar(extrator.extrair(conteudo), texto_paginas(conteudo))
    except ErroExtracao as exc:
        documento.status = DocumentoFonte.Status.ERRO
        documento.mensagem_erro = str(exc)
        documento.save()
        raise

    tabelas = []
    with transaction.atomic():
        # MVP: operadora e plano resolvidos por nome exato. Próximo passo: tabela de apelidos
        # (ex.: "SulAmérica" x "Sul America"), com o registro ANS como chave definitiva do produto.
        operadora, _ = Operadora.objects.get_or_create(nome=resultado.operadora)
        for extraida in resultado.tabelas:
            avisos = list(resultado.avisos)
            plano, _ = Plano.objects.get_or_create(
                operadora=operadora,
                nome=extraida.plano,
                defaults={"acomodacao": extraida.acomodacao},
            )
            _vincular_registro(plano, extraida.registro_ans, avisos)
            tabela = TabelaPreco.objects.create(
                plano=plano,
                regiao=resultado.regiao,
                tipo_contratacao=resultado.tipo_contratacao,
                coparticipacao=resultado.coparticipacao,
                vigencia_inicio=resultado.vigencia_inicio,
                documento=documento,
                pagina_origem=extraida.pagina,
            )
            ValorFaixa.objects.bulk_create(
                [
                    ValorFaixa(
                        tabela=tabela, faixa=f, valor=v, valor_extraido=v,
                        trecho_origem=extraida.trechos.get(f, "")[:255],
                    )
                    for f, v in extraida.valores.items()
                ]
            )
            tabela.validacoes = calcular_validacoes(tabela, extraida.valores)
            tabela.save(update_fields=["validacoes"])
            RegistroAuditoria.objects.create(
                tabela=tabela, acao="extraida", usuario=usuario,
                detalhes={"metodo": extrator.nome, "avisos": avisos},
            )
            tabelas.append(tabela)

        documento.status = DocumentoFonte.Status.EXTRAIDO
        documento.save(update_fields=["status", "metodo_extracao"])
        fonte.ultima_verificacao = timezone.now()
        fonte.save(update_fields=["ultima_verificacao"])

    return documento, tabelas
