from rest_framework import serializers

from catalogo.models import (
    DocumentoFonte, FonteDados, ProdutoANS, RegistroAuditoria, TabelaPreco, ValorFaixa,
)


def url_original(documento_id: int) -> str:
    """O original é servido pela API, venha do disco, do banco ou (em produção) do S3."""
    return f"/api/documentos/{documento_id}/original/"


class FonteDadosSerializer(serializers.ModelSerializer):
    atrasada = serializers.BooleanField(read_only=True)
    operadora = serializers.StringRelatedField()

    class Meta:
        model = FonteDados
        fields = [
            "id", "nome", "tipo", "operadora", "url", "frequencia_esperada_dias",
            "confiabilidade", "responsavel", "ultima_verificacao", "atrasada",
        ]


class DocumentoFonteSerializer(serializers.ModelSerializer):
    fonte = serializers.StringRelatedField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentoFonte
        fields = ["id", "nome_original", "url", "sha256", "recebido_em", "status",
                  "metodo_extracao", "mensagem_erro", "fonte"]

    def get_url(self, obj):
        return url_original(obj.id)


class ProdutoANSSerializer(serializers.ModelSerializer):
    situacao_rotulo = serializers.CharField(source="get_situacao_display", read_only=True)

    class Meta:
        model = ProdutoANS
        fields = ["registro_ans", "nome", "operadora", "contratacao", "situacao", "situacao_rotulo",
                  "situacao_desde", "data_referencia"]


class ValorFaixaSerializer(serializers.ModelSerializer):
    rotulo = serializers.CharField(source="get_faixa_display", read_only=True)
    corrigido_manualmente = serializers.BooleanField(read_only=True)

    class Meta:
        model = ValorFaixa
        fields = ["faixa", "rotulo", "valor", "valor_extraido", "corrigido_manualmente", "trecho_origem"]


class AuditoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroAuditoria
        fields = ["acao", "usuario", "detalhes", "criado_em"]


class TabelaResumoSerializer(serializers.ModelSerializer):
    operadora = serializers.CharField(source="plano.operadora.nome")
    plano = serializers.CharField(source="plano.nome")
    documento = serializers.CharField(source="documento.nome_original")
    plano_id = serializers.IntegerField(source="plano.id")
    registro_ans = serializers.CharField(source="plano.registro_ans")
    qtd_erros = serializers.SerializerMethodField()
    qtd_liberaveis = serializers.SerializerMethodField()
    qtd_alertas = serializers.SerializerMethodField()

    class Meta:
        model = TabelaPreco
        fields = [
            "id", "operadora", "plano", "plano_id", "registro_ans", "regiao", "tipo_contratacao",
            "coparticipacao", "vigencia_inicio", "vigencia_fim", "status", "versao", "documento",
            "criado_em", "qtd_erros", "qtd_liberaveis", "qtd_alertas",
        ]

    def get_qtd_erros(self, obj):
        """Só os erros que exigem correção; os liberáveis com justificativa são contados à parte."""
        return len(obj.erros_bloqueantes)

    def get_qtd_liberaveis(self, obj):
        return len(obj.erros_liberaveis)

    def get_qtd_alertas(self, obj):
        return sum(1 for v in obj.validacoes if v.get("severidade") == "alerta")


class TabelaDetalheSerializer(TabelaResumoSerializer):
    valores = ValorFaixaSerializer(many=True, read_only=True)
    auditoria = AuditoriaSerializer(many=True, read_only=True)
    documento_url = serializers.SerializerMethodField()
    fonte = serializers.CharField(source="documento.fonte.nome")
    comparacao = serializers.SerializerMethodField()
    versao_vigente_id = serializers.SerializerMethodField()
    comparacao_tipo = serializers.SerializerMethodField()

    class Meta(TabelaResumoSerializer.Meta):
        fields = TabelaResumoSerializer.Meta.fields + [
            "pagina_origem", "validacoes", "valores", "auditoria", "documento_url", "fonte",
            "revisado_por", "revisado_em", "observacao_revisao", "comparacao", "versao_vigente_id",
            "comparacao_tipo",
        ]

    def get_documento_url(self, obj):
        return url_original(obj.documento_id)

    def _atual(self, obj):
        """Versão usada como referência na comparação.

        Em revisão ou rejeitada: a versão publicada hoje, que seria substituída.
        Publicada ou substituída: a versão anterior, que ela substituiu.
        """
        from catalogo.servicos.publicacao import tabela_publicada_atual

        if not hasattr(self, "_cache_atual"):
            if obj.status in (TabelaPreco.Status.EM_REVISAO, TabelaPreco.Status.REJEITADA):
                self._cache_atual = tabela_publicada_atual(obj)
            else:
                self._cache_atual = (
                    TabelaPreco.objects.filter(
                        **obj.chave(),
                        status__in=[TabelaPreco.Status.PUBLICADA, TabelaPreco.Status.SUBSTITUIDA],
                        vigencia_inicio__lt=obj.vigencia_inicio,
                    )
                    .exclude(pk=obj.pk)
                    .order_by("-vigencia_inicio")
                    .first()
                )
        return self._cache_atual

    def get_comparacao_tipo(self, obj):
        if not self._atual(obj):
            return None
        return "vigente" if obj.status in (TabelaPreco.Status.EM_REVISAO, TabelaPreco.Status.REJEITADA) else "anterior"

    def get_comparacao(self, obj):
        from catalogo.servicos.validacao import comparar

        atual = self._atual(obj)
        return comparar(obj.valores_dict(), atual.valores_dict() if atual else None)

    def get_versao_vigente_id(self, obj):
        atual = self._atual(obj)
        return atual.id if atual else None
