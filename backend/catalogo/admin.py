from django.contrib import admin

from catalogo import models


class ValorFaixaInline(admin.TabularInline):
    model = models.ValorFaixa
    extra = 0


@admin.register(models.TabelaPreco)
class TabelaPrecoAdmin(admin.ModelAdmin):
    list_display = ("plano", "regiao", "tipo_contratacao", "vigencia_inicio", "vigencia_fim", "status", "versao")
    list_filter = ("status", "regiao", "tipo_contratacao", "plano__operadora")
    inlines = [ValorFaixaInline]


@admin.register(models.FonteDados)
class FonteDadosAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "operadora", "frequencia_esperada_dias", "ultima_verificacao")


class ValorComercialInline(admin.TabularInline):
    model = models.ValorComercialANS
    extra = 0


@admin.register(models.ProdutoANS)
class ProdutoANSAdmin(admin.ModelAdmin):
    list_display = ("registro_ans", "nome", "operadora", "situacao", "situacao_desde", "data_referencia")
    list_filter = ("situacao",)
    inlines = [ValorComercialInline]


admin.site.register([models.Operadora, models.Plano, models.DocumentoFonte, models.RegistroAuditoria])
