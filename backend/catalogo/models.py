"""Modelo de dados do cotador.

Princípios:
- Nada é sobrescrito: cada mudança de preço gera uma nova versão de TabelaPreco.
- Todo valor publicado aponta para o documento de origem (rastreabilidade).
- Vigência (quando o preço vale) é separada de criação/revisão (quando registramos).
"""
from datetime import timedelta

from django.db import models
from django.utils import timezone

from catalogo.servicos.faixas import FAIXAS


class Operadora(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    registro_ans = models.CharField(max_length=20, blank=True)
    ativa = models.BooleanField(default=True)

    def __str__(self):
        return self.nome


class Plano(models.Model):
    class Acomodacao(models.TextChoices):
        ENFERMARIA = "enfermaria", "Enfermaria"
        APARTAMENTO = "apartamento", "Apartamento"

    operadora = models.ForeignKey(Operadora, on_delete=models.PROTECT, related_name="planos")
    nome = models.CharField(max_length=120)
    registro_ans = models.CharField(max_length=30, blank=True)
    acomodacao = models.CharField(max_length=20, choices=Acomodacao.choices, blank=True)

    class Meta:
        unique_together = [("operadora", "nome")]

    def __str__(self):
        return f"{self.operadora} / {self.nome}"


class FonteDados(models.Model):
    """Catálogo de fontes: de onde vem cada dado e com que frequência deveria mudar."""

    class Tipo(models.TextChoices):
        API = "api", "API / parceria"
        PLANILHA = "planilha", "Planilha"
        PDF_EMAIL = "pdf_email", "PDF por e-mail"
        PORTAL = "portal", "Portal do corretor (RPA)"
        UPLOAD = "upload", "Upload manual"
        ANS = "ans", "Dados abertos ANS"

    operadora = models.ForeignKey(
        Operadora, on_delete=models.PROTECT, related_name="fontes", null=True, blank=True
    )
    nome = models.CharField(max_length=160)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    url = models.URLField(blank=True)
    frequencia_esperada_dias = models.PositiveIntegerField(
        default=30, help_text="SLA de frescor: após esse prazo sem verificação, a fonte é marcada como atrasada."
    )
    confiabilidade = models.PositiveSmallIntegerField(
        default=3, help_text="1 (baixa) a 5 (oficial/estruturada)."
    )
    responsavel = models.CharField(max_length=120, blank=True)
    ultima_verificacao = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.nome

    @property
    def atrasada(self) -> bool:
        if not self.ultima_verificacao:
            return True
        limite = self.ultima_verificacao + timedelta(days=self.frequencia_esperada_dias)
        return timezone.now() > limite


class DocumentoFonte(models.Model):
    """Arquivo original recebido. Imutável; o hash impede reprocessar duplicatas."""

    class Status(models.TextChoices):
        RECEBIDO = "recebido", "Recebido"
        EXTRAIDO = "extraido", "Extraído"
        ERRO = "erro", "Erro na extração"

    fonte = models.ForeignKey(FonteDados, on_delete=models.PROTECT, related_name="documentos")
    arquivo = models.FileField(upload_to="documentos/%Y/%m/")
    nome_original = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64, unique=True)
    conteudo = models.BinaryField(
        null=True, blank=True, editable=False,
        help_text="Cópia do original no banco. Usada só no deploy serverless de demonstração (ORIGINAIS_NO_BANCO).",
    )
    recebido_em = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEBIDO)
    metodo_extracao = models.CharField(max_length=30, blank=True)
    mensagem_erro = models.TextField(blank=True)

    def __str__(self):
        return self.nome_original


class TabelaPreco(models.Model):
    """Uma versão de tabela de preços para uma combinação plano + região + contratação."""

    class TipoContratacao(models.TextChoices):
        PF = "PF", "Individual/Familiar"
        PME = "PME", "Empresarial (PME)"
        ADESAO = "ADESAO", "Coletivo por adesão"

    class Status(models.TextChoices):
        EM_REVISAO = "em_revisao", "Em revisão"
        PUBLICADA = "publicada", "Publicada"
        SUBSTITUIDA = "substituida", "Substituída"
        REJEITADA = "rejeitada", "Rejeitada"

    plano = models.ForeignKey(Plano, on_delete=models.PROTECT, related_name="tabelas")
    regiao = models.CharField(max_length=60, help_text="UF ou região comercial, ex.: DF")
    tipo_contratacao = models.CharField(max_length=10, choices=TipoContratacao.choices)
    coparticipacao = models.BooleanField(default=False)

    vigencia_inicio = models.DateField()
    vigencia_fim = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.EM_REVISAO)
    versao = models.PositiveIntegerField(null=True, blank=True)
    documento = models.ForeignKey(DocumentoFonte, on_delete=models.PROTECT, related_name="tabelas")
    pagina_origem = models.PositiveIntegerField(null=True, blank=True)

    validacoes = models.JSONField(default=list, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    revisado_por = models.CharField(max_length=120, blank=True)
    revisado_em = models.DateTimeField(null=True, blank=True)
    observacao_revisao = models.TextField(blank=True)

    class Meta:
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["plano", "regiao", "tipo_contratacao", "coparticipacao", "status"]),
            models.Index(fields=["vigencia_inicio", "vigencia_fim"]),
        ]

    def __str__(self):
        return f"{self.plano} [{self.regiao}/{self.tipo_contratacao}] {self.vigencia_inicio} ({self.status})"

    def chave(self) -> dict:
        """Campos que identificam 'a mesma tabela' ao longo das versões."""
        return {
            "plano": self.plano,
            "regiao": self.regiao,
            "tipo_contratacao": self.tipo_contratacao,
            "coparticipacao": self.coparticipacao,
        }

    def valores_dict(self) -> dict[int, "Decimal"]:  # noqa: F821
        return {v.faixa: v.valor for v in self.valores.all()}

    @property
    def tem_erro(self) -> bool:
        return any(v.get("severidade") == "erro" for v in self.validacoes)

    @property
    def erros_bloqueantes(self) -> list[dict]:
        """Erros que só somem corrigindo o valor (regras da RN 563, estrutura, produto suspenso)."""
        return [v for v in self.validacoes if v.get("severidade") == "erro" and not v.get("liberavel")]

    @property
    def erros_liberaveis(self) -> list[dict]:
        """Erros que o revisor pode liberar com justificativa (banda de preço da ANS)."""
        return [v for v in self.validacoes if v.get("severidade") == "erro" and v.get("liberavel")]


class ValorFaixa(models.Model):
    tabela = models.ForeignKey(TabelaPreco, on_delete=models.CASCADE, related_name="valores")
    faixa = models.PositiveSmallIntegerField(choices=[(f.numero, f.rotulo) for f in FAIXAS])
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    valor_extraido = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Valor original da extração. Diferente de 'valor' quando houve correção humana.",
    )
    trecho_origem = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [("tabela", "faixa")]
        ordering = ["faixa"]

    @property
    def corrigido_manualmente(self) -> bool:
        return self.valor_extraido is not None and self.valor_extraido != self.valor


class RegistroAuditoria(models.Model):
    """Trilha de quem fez o quê. Base do histórico e das métricas de qualidade."""

    tabela = models.ForeignKey(TabelaPreco, on_delete=models.CASCADE, related_name="auditoria")
    acao = models.CharField(max_length=40)
    usuario = models.CharField(max_length=120, blank=True)
    detalhes = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em"]


class ProdutoANS(models.Model):
    """Cadastro oficial do produto, sincronizado dos dados abertos da ANS.

    É a referência independente da operadora: diz se o plano existe, se pode ser vendido
    e qual é o valor comercial registrado na nota técnica (NTRP).
    """

    class Situacao(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        SUSPENSO = "suspenso", "Comercialização suspensa"
        CANCELADO = "cancelado", "Cancelado"

    registro_ans = models.CharField(max_length=30, unique=True)
    nome = models.CharField(max_length=160)
    operadora = models.CharField(max_length=160, blank=True)
    contratacao = models.CharField(max_length=40, blank=True)
    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.ATIVO)
    situacao_desde = models.DateField(null=True, blank=True)
    data_referencia = models.DateField(help_text="Data do conjunto de dados da ANS de onde veio este registro.")
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["registro_ans"]

    def __str__(self):
        return f"{self.registro_ans} {self.nome}"

    def vendavel_em(self, data) -> bool:
        if self.situacao == self.Situacao.ATIVO:
            return True
        return bool(self.situacao_desde and data < self.situacao_desde)


class ValorComercialANS(models.Model):
    """Valor comercial da mensalidade por faixa etária, informado na NTRP do produto."""

    produto = models.ForeignKey(ProdutoANS, on_delete=models.CASCADE, related_name="valores_comerciais")
    faixa = models.PositiveSmallIntegerField(choices=[(f.numero, f.rotulo) for f in FAIXAS])
    valor = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = [("produto", "faixa")]
        ordering = ["faixa"]
