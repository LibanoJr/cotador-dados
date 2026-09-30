"""Ciclo de vida de uma tabela: correção, aprovação (publicação versionada) e rejeição."""
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from catalogo.models import RegistroAuditoria, TabelaPreco
from catalogo.servicos.referencia_ans import validar_contra_ans
from catalogo.servicos.validacao import validar_tabela


class OperacaoInvalida(Exception):
    pass


def tabela_publicada_atual(tabela: TabelaPreco) -> TabelaPreco | None:
    return (
        TabelaPreco.objects.filter(status=TabelaPreco.Status.PUBLICADA, **tabela.chave())
        .exclude(pk=tabela.pk)
        .first()
    )


def tabelas_vigentes(data: date | None = None):
    """Tabelas que valiam na data (inclui substituídas, para consultas históricas)."""
    data = data or timezone.localdate()
    return TabelaPreco.objects.filter(
        status__in=[TabelaPreco.Status.PUBLICADA, TabelaPreco.Status.SUBSTITUIDA],
        vigencia_inicio__lte=data,
    ).filter(Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=data))


def calcular_validacoes(tabela: TabelaPreco, valores: dict | None = None) -> list[dict]:
    """Os quatro níveis numa lista só: estrutura, regras da RN 563, histórico e referência ANS."""
    valores = valores if valores is not None else tabela.valores_dict()
    atual = tabela_publicada_atual(tabela)
    resultado = validar_tabela(valores, atual.valores_dict() if atual else None)
    resultado += validar_contra_ans(tabela.plano.registro_ans, valores, tabela.vigencia_inicio)
    fonte = tabela.documento.fonte
    if fonte.operadora_id and fonte.operadora_id != tabela.plano.operadora_id:
        resultado.append({
            "codigo": "FONTE_DE_OUTRA_OPERADORA", "severidade": "alerta",
            "mensagem": f"O documento traz a operadora {tabela.plano.operadora}, mas foi recebido pela fonte "
                        f"'{fonte.nome}', que é de {fonte.operadora}. Confira se a fonte escolhida está certa: "
                        "ela define o SLA de frescor e a procedência mostrada ao corretor.",
        })
    return resultado


def revalidar(tabela: TabelaPreco) -> list[dict]:
    tabela.validacoes = calcular_validacoes(tabela)
    tabela.save(update_fields=["validacoes"])
    return tabela.validacoes


def _exigir_em_revisao(tabela):
    if tabela.status != TabelaPreco.Status.EM_REVISAO:
        raise OperacaoInvalida(f"Tabela está '{tabela.get_status_display()}', não pode ser alterada")


@transaction.atomic
def corrigir_valor(tabela: TabelaPreco, faixa: int, valor: Decimal, usuario: str) -> TabelaPreco:
    _exigir_em_revisao(tabela)
    item = tabela.valores.filter(faixa=faixa).first()
    anterior = str(item.valor) if item else None
    if item:
        item.valor = valor
        item.save(update_fields=["valor"])
    else:
        tabela.valores.create(faixa=faixa, valor=valor, trecho_origem="incluído manualmente")
    revalidar(tabela)
    RegistroAuditoria.objects.create(
        tabela=tabela, acao="valor_corrigido", usuario=usuario,
        detalhes={"faixa": faixa, "de": anterior, "para": str(valor)},
    )
    return tabela


@transaction.atomic
def aprovar(tabela: TabelaPreco, usuario: str, observacao: str = "", justificativa: str = "") -> TabelaPreco:
    tabela = TabelaPreco.objects.select_for_update().get(pk=tabela.pk)
    _exigir_em_revisao(tabela)
    if not usuario:
        raise OperacaoInvalida("Informe quem está aprovando")
    revalidar(tabela)
    if tabela.erros_bloqueantes:
        raise OperacaoInvalida("Existem erros de validação. Corrija os valores antes de aprovar.")
    liberados = tabela.erros_liberaveis
    if liberados and not justificativa.strip():
        raise OperacaoInvalida(
            "Há preços fora da banda da referência ANS. Confira o original e, se estiverem certos, "
            "publique informando a justificativa."
        )
    if liberados:
        RegistroAuditoria.objects.create(
            tabela=tabela, acao="bloqueio_liberado", usuario=usuario,
            detalhes={"justificativa": justificativa.strip(), "regras": [v["codigo"] for v in liberados]},
        )

    atual = (
        TabelaPreco.objects.select_for_update()
        .filter(status=TabelaPreco.Status.PUBLICADA, **tabela.chave())
        .exclude(pk=tabela.pk)
        .first()
    )
    if atual:
        if tabela.vigencia_inicio <= atual.vigencia_inicio:
            raise OperacaoInvalida(
                f"A vigência nova ({tabela.vigencia_inicio:%d/%m/%Y}) precisa ser posterior à vigente "
                f"({atual.vigencia_inicio:%d/%m/%Y})"
            )
        atual.status = TabelaPreco.Status.SUBSTITUIDA
        atual.vigencia_fim = tabela.vigencia_inicio - timedelta(days=1)
        atual.save(update_fields=["status", "vigencia_fim"])
        RegistroAuditoria.objects.create(
            tabela=atual, acao="substituida", usuario=usuario, detalhes={"por": tabela.pk}
        )

    tabela.status = TabelaPreco.Status.PUBLICADA
    tabela.versao = (atual.versao or 0) + 1 if atual else 1
    tabela.revisado_por = usuario
    tabela.revisado_em = timezone.now()
    tabela.observacao_revisao = observacao
    tabela.save()
    RegistroAuditoria.objects.create(
        tabela=tabela, acao="publicada", usuario=usuario,
        detalhes={"versao": tabela.versao, "substituiu": atual.pk if atual else None},
    )
    return tabela


@transaction.atomic
def rejeitar(tabela: TabelaPreco, usuario: str, motivo: str) -> TabelaPreco:
    _exigir_em_revisao(tabela)
    if not motivo:
        raise OperacaoInvalida("Informe o motivo da rejeição")
    tabela.status = TabelaPreco.Status.REJEITADA
    tabela.revisado_por = usuario
    tabela.revisado_em = timezone.now()
    tabela.observacao_revisao = motivo
    tabela.save()
    RegistroAuditoria.objects.create(tabela=tabela, acao="rejeitada", usuario=usuario, detalhes={"motivo": motivo})
    return tabela


@transaction.atomic
def vincular_registro(plano, registro_ans: str, usuario: str) -> list[TabelaPreco]:
    """Ligação manual de um plano ao registro ANS. Feita uma vez; vale para as próximas tabelas."""
    registro = "".join((registro_ans or "").split())
    if not registro:
        raise OperacaoInvalida("Informe o registro ANS")
    if not usuario:
        raise OperacaoInvalida("Informe quem está vinculando")
    anterior = plano.registro_ans
    plano.registro_ans = registro
    plano.save(update_fields=["registro_ans"])
    abertas = list(plano.tabelas.filter(status=TabelaPreco.Status.EM_REVISAO))
    for tabela in abertas:
        revalidar(tabela)
        RegistroAuditoria.objects.create(
            tabela=tabela, acao="registro_vinculado", usuario=usuario,
            detalhes={"de": anterior or None, "para": registro},
        )
    return abertas
