from django.urls import path

from catalogo import views

urlpatterns = [
    path("", views.raiz),
    path("fontes/", views.FonteLista.as_view()),
    path("documentos/", views.DocumentoLista.as_view()),
    path("documentos/enviar/", views.enviar_documento),
    path("documentos/<int:pk>/original/", views.documento_original),
    path("tabelas/", views.TabelaLista.as_view()),
    path("tabelas/<int:pk>/", views.TabelaDetalhe.as_view()),
    path("tabelas/<int:pk>/aprovar/", views.aprovar_tabela),
    path("tabelas/<int:pk>/rejeitar/", views.rejeitar_tabela),
    path("tabelas/<int:pk>/valores/", views.corrigir_valor),
    path("tabelas/<int:pk>/historico/", views.historico_tabela),
    path("planos/<int:pk>/registro/", views.vincular_registro),
    path("referencia-ans/", views.ProdutoANSLista.as_view()),
    path("cotacao/", views.cotacao),
    path("metricas/", views.metricas),
    path("amostras/", views.amostras),
    path("amostras/<str:nome>/", views.amostra_pdf),
    path("demo/reiniciar/", views.reiniciar_demo),
]
