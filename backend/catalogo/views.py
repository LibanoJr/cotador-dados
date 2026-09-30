from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from catalogo.models import (
    DocumentoFonte, FonteDados, Plano, ProdutoANS, RegistroAuditoria, TabelaPreco, ValorFaixa,
)
from catalogo.serializers import (
    DocumentoFonteSerializer, FonteDadosSerializer, ProdutoANSSerializer, TabelaDetalheSerializer,
    TabelaResumoSerializer,
)
from catalogo.servicos import demo, publicacao
from catalogo.servicos.cotacao import cotar
from catalogo.servicos.extracao import ErroExtracao
from catalogo.servicos.ingestao import DocumentoDuplicado, ingerir_documento


def _erro(msg, codigo=status.HTTP_400_BAD_REQUEST, **extra):
    return Response({"erro": msg, **extra}, status=codigo)


@api_view(["GET"])
def raiz(request):
    return Response({"servico": "cotador-dados", "ok": True, "demo_permite_reiniciar": settings.DEMO_PERMITE_REINICIAR})


class FonteLista(ListAPIView):
    queryset = FonteDados.objects.select_related("operadora").order_by("nome")
    serializer_class = FonteDadosSerializer


class DocumentoLista(ListAPIView):
    queryset = DocumentoFonte.objects.select_related("fonte").order_by("-recebido_em")
    serializer_class = DocumentoFonteSerializer


@api_view(["POST"])
@parser_classes([MultiPartParser])
def enviar_documento(request):
    arquivo = request.FILES.get("arquivo")
    fonte_id = request.data.get("fonte_id")
    if not arquivo or not fonte_id:
        return _erro("Envie 'arquivo' e 'fonte_id'")
    fonte = FonteDados.objects.filter(pk=fonte_id).first()
    if not fonte:
        return _erro("Fonte não encontrada", status.HTTP_404_NOT_FOUND)
    if fonte.tipo == FonteDados.Tipo.ANS:
        return _erro("A fonte ANS é alimentada pela sincronização de dados abertos, não por envio de documentos")
    try:
        documento, tabelas = ingerir_documento(
            arquivo.read(), arquivo.name, fonte,
            metodo=request.data.get("metodo") or None, usuario=request.data.get("usuario", ""),
        )
    except DocumentoDuplicado as exc:
        return _erro(str(exc), status.HTTP_409_CONFLICT, documento_id=exc.documento.id)
    except ErroExtracao as exc:
        return _erro(f"Falha na extração: {exc}", status.HTTP_422_UNPROCESSABLE_ENTITY)
    return Response(
        {
            "documento": DocumentoFonteSerializer(documento).data,
            "tabelas": TabelaResumoSerializer(tabelas, many=True).data,
        },
        status=status.HTTP_201_CREATED,
    )


def documento_original(request, pk):
    """Devolve o arquivo original, para o revisor e o corretor conferirem a origem do valor."""
    documento = DocumentoFonte.objects.filter(pk=pk).first()
    if not documento:
        raise Http404("Documento não encontrado")
    if documento.conteudo:
        resposta = HttpResponse(bytes(documento.conteudo), content_type="application/pdf")
    else:
        try:
            resposta = FileResponse(documento.arquivo.open("rb"), content_type="application/pdf")
        except FileNotFoundError as exc:
            raise Http404("Original indisponível neste ambiente") from exc
    resposta["Content-Disposition"] = f'inline; filename="{documento.nome_original}"'
    return resposta


class ProdutoANSLista(ListAPIView):
    queryset = ProdutoANS.objects.all()
    serializer_class = ProdutoANSSerializer


@api_view(["GET"])
def amostras(request):
    return Response({"amostras": demo.amostras_disponiveis(), "sugerida": demo.PARA_DEMONSTRAR})


def amostra_pdf(request, nome):
    """Serve os PDFs fictícios, para quem testa pela versão publicada não precisar baixar o repositório."""
    if nome not in demo.amostras_disponiveis():
        raise Http404("Amostra não encontrada")
    resposta = FileResponse((demo.PASTA / nome).open("rb"), content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    return resposta


@api_view(["POST"])
def reiniciar_demo(request):
    if not settings.DEMO_PERMITE_REINICIAR:
        return _erro("Reinício desativado neste ambiente", status.HTTP_403_FORBIDDEN)
    demo.reiniciar(log=lambda *_: None)
    return Response({"ok": True})


@api_view(["PATCH"])
@parser_classes([JSONParser])
def vincular_registro(request, pk):
    plano = Plano.objects.filter(pk=pk).first()
    if not plano:
        return _erro("Plano não encontrado", status.HTTP_404_NOT_FOUND)
    try:
        abertas = publicacao.vincular_registro(plano, request.data.get("registro_ans", ""), request.data.get("usuario", ""))
    except publicacao.OperacaoInvalida as exc:
        return _erro(str(exc))
    return Response({"plano_id": plano.id, "registro_ans": plano.registro_ans, "tabelas_revalidadas": [t.id for t in abertas]})


class TabelaLista(ListAPIView):
    serializer_class = TabelaResumoSerializer

    def get_queryset(self):
        qs = TabelaPreco.objects.select_related("plano__operadora", "documento")
        if s := self.request.query_params.get("status"):
            qs = qs.filter(status=s)
        return qs


class TabelaDetalhe(RetrieveAPIView):
    queryset = TabelaPreco.objects.select_related("plano__operadora", "documento__fonte").prefetch_related(
        "valores", "auditoria"
    )
    serializer_class = TabelaDetalheSerializer


def _executar(acao, pk, *args):
    tabela = TabelaPreco.objects.filter(pk=pk).first()
    if not tabela:
        return _erro("Tabela não encontrada", status.HTTP_404_NOT_FOUND)
    try:
        acao(tabela, *args)
    except publicacao.OperacaoInvalida as exc:
        return _erro(str(exc), status.HTTP_409_CONFLICT)
    tabela.refresh_from_db()
    return Response(TabelaDetalheSerializer(tabela).data)


@api_view(["POST"])
@parser_classes([JSONParser])
def aprovar_tabela(request, pk):
    d = request.data
    return _executar(publicacao.aprovar, pk, d.get("usuario", ""), d.get("observacao", ""), d.get("justificativa", ""))


@api_view(["POST"])
@parser_classes([JSONParser])
def rejeitar_tabela(request, pk):
    return _executar(publicacao.rejeitar, pk, request.data.get("usuario", ""), request.data.get("motivo", ""))


@api_view(["PATCH"])
@parser_classes([JSONParser])
def corrigir_valor(request, pk):
    try:
        faixa = int(request.data["faixa"])
        valor = Decimal(str(request.data["valor"])).quantize(Decimal("0.01"))
    except (KeyError, ValueError, InvalidOperation):
        return _erro("Envie 'faixa' (1 a 10) e 'valor' numérico")
    if not 1 <= faixa <= 10 or valor <= 0:
        return _erro("Faixa deve estar entre 1 e 10 e valor deve ser positivo")
    return _executar(publicacao.corrigir_valor, pk, faixa, valor, request.data.get("usuario", ""))


@api_view(["GET"])
def historico_tabela(request, pk):
    tabela = TabelaPreco.objects.filter(pk=pk).first()
    if not tabela:
        return _erro("Tabela não encontrada", status.HTTP_404_NOT_FOUND)
    versoes = TabelaPreco.objects.filter(**tabela.chave()).order_by("vigencia_inicio", "criado_em")
    return Response(TabelaResumoSerializer(versoes, many=True).data)


@api_view(["GET"])
def cotacao(request):
    p = request.query_params
    try:
        idades = [int(i) for i in p.get("idades", "").split(",") if i.strip()]
        data = date.fromisoformat(p["data"]) if p.get("data") else None
        copart = {"sim": True, "nao": False}.get(p.get("coparticipacao", "").lower())
        resultado = cotar(p.get("regiao", ""), p.get("tipo", "PME").upper(), idades, data, copart)
    except (ValueError, KeyError) as exc:
        return _erro(f"Parâmetros inválidos: {exc}")
    return Response(resultado)


@api_view(["GET"])
def metricas(request):
    """Indicadores para acompanhar se a solução está funcionando."""
    por_status = dict(TabelaPreco.objects.values_list("status").annotate(n=Count("id")))
    publicados = ValorFaixa.objects.filter(
        tabela__status__in=[TabelaPreco.Status.PUBLICADA, TabelaPreco.Status.SUBSTITUIDA]
    )
    total_campos = publicados.count()
    corrigidos = sum(1 for v in publicados.only("valor", "valor_extraido") if v.corrigido_manualmente)
    fontes = list(FonteDados.objects.all())
    ultima_ref = ProdutoANS.objects.order_by("-data_referencia").values_list("data_referencia", flat=True).first()
    em_revisao = TabelaPreco.objects.filter(status=TabelaPreco.Status.EM_REVISAO).select_related("plano")
    return Response(
        {
            "tabelas_por_status": por_status,
            "campos_publicados": total_campos,
            "campos_corrigidos_manualmente": corrigidos,
            "taxa_aceite_sem_edicao": round(1 - corrigidos / total_campos, 4) if total_campos else None,
            "fontes_total": len(fontes),
            "fontes_atrasadas": sum(1 for f in fontes if f.atrasada),
            "documentos_com_erro": DocumentoFonte.objects.filter(status=DocumentoFonte.Status.ERRO).count(),
            "bloqueios_liberados_com_justificativa": RegistroAuditoria.objects.filter(acao="bloqueio_liberado").count(),
            "planos_sem_registro_ans": Plano.objects.filter(registro_ans="").count(),
            "planos_total": Plano.objects.count(),
            "produtos_ans": ProdutoANS.objects.count(),
            "referencia_ans_de": ultima_ref,
            "fila_em_revisao": em_revisao.count(),
        }
    )
