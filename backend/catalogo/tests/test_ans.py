"""Nível 3: cruzamento com a referência ANS, liberação justificada e reação a suspensões."""
from datetime import date
from decimal import Decimal

import pytest

from catalogo.models import Plano, TabelaPreco
from catalogo.servicos import publicacao
from catalogo.servicos.cotacao import cotar
from catalogo.servicos.ingestao import ingerir_documento
from catalogo.servicos.referencia_ans import validar_contra_ans
from catalogo.servicos.sincronizacao_ans import ErroSincronizacao, importar_referencia

pytestmark = pytest.mark.django_db

JAN, JUN, BETA = "alfa_pme_df_2026-01.pdf", "alfa_pme_df_2026-06.pdf", "beta_pme_df_2026-03.pdf"


def ingerir(amostras, fonte, nome):
    return ingerir_documento((amostras / nome).read_bytes(), nome, fonte)[1]


def por_plano(tabelas, nome):
    return next(t for t in tabelas if t.plano.nome == nome)


def codigos(tabela):
    return {v["codigo"] for v in tabela.validacoes}


def publicar(tabelas):
    for t in tabelas:
        publicacao.aprovar(t, "ana")


def test_registro_ans_vem_do_documento(amostras, fonte, referencia_ans):
    tabelas = ingerir(amostras, fonte, JAN)
    assert por_plano(tabelas, "Essencial Enfermaria").plano.registro_ans == "900.101/26-1"
    assert all(not t.tem_erro for t in tabelas)


def test_preco_fora_da_banda_exige_justificativa(amostras, fonte, referencia_ans):
    publicar(ingerir(amostras, fonte, JAN))
    apto = por_plano(ingerir(amostras, fonte, JUN), "Essencial Apartamento")
    assert "ANS_ACIMA_DA_BANDA" in codigos(apto)
    assert apto.erros_liberaveis and not apto.erros_bloqueantes

    with pytest.raises(publicacao.OperacaoInvalida, match="justificativa"):
        publicacao.aprovar(apto, "ana")

    publicacao.aprovar(apto, "ana", justificativa="Tabela confirmada com o comercial; NTRP em revisão na ANS")
    apto.refresh_from_db()
    assert apto.status == TabelaPreco.Status.PUBLICADA
    liberacao = apto.auditoria.get(acao="bloqueio_liberado")
    assert liberacao.detalhes["regras"] == ["ANS_ACIMA_DA_BANDA"]


def test_justificativa_nao_libera_erro_de_regra(amostras, fonte, referencia_ans):
    publicar(ingerir(amostras, fonte, JAN))
    premium = por_plano(ingerir(amostras, fonte, JUN), "Premium Apartamento")
    assert {"RN563_LIMITE_6X", "ANS_ACIMA_DA_BANDA", "ANS_PADRAO_FAIXAS_DIFERENTE"} <= codigos(premium)
    with pytest.raises(publicacao.OperacaoInvalida, match="Corrija"):
        publicacao.aprovar(premium, "ana", justificativa="tentando passar")

    publicacao.corrigir_valor(premium, 10, Decimal("2466.96"), "ana")
    premium.refresh_from_db()
    assert not premium.tem_erro
    publicacao.aprovar(premium, "ana")


def test_plano_suspenso_sai_da_cotacao_a_partir_da_data(amostras, fonte, referencia_ans):
    publicar(ingerir(amostras, fonte, BETA))

    hoje = cotar("DF", "PME", [30], date(2026, 9, 30))
    assert "Vida Mais Enfermaria" not in [r["plano"] for r in hoje["resultados"]]
    assert any("Vida Mais Enfermaria" in a and "suspensa" in a for a in hoje["avisos"])

    antes = cotar("DF", "PME", [30], date(2026, 8, 14))
    assert "Vida Mais Enfermaria" in [r["plano"] for r in antes["resultados"]]
    assert not antes["avisos"]


def test_suspensao_nova_gera_reconferencia_uma_vez(amostras, fonte):
    publicar(ingerir(amostras, fonte, BETA))  # publicada antes de existir referência
    produtos = (amostras / "ans" / "produtos.csv").read_text(encoding="utf-8")
    valores = (amostras / "ans" / "valor_comercial.csv").read_text(encoding="utf-8")

    resumo = importar_referencia(produtos, valores, date(2026, 9, 28))
    assert any("Vida Mais Enfermaria" in p for p in resumo.planos_afetados)
    importar_referencia(produtos, valores, date(2026, 10, 5))

    tabela = TabelaPreco.objects.get(plano__nome="Vida Mais Enfermaria", status="publicada")
    assert tabela.auditoria.filter(acao="situacao_ans_alterada").count() == 1


def test_sincronizacao_vazia_nao_apaga_referencia(referencia_ans):
    with pytest.raises(ErroSincronizacao):
        importar_referencia("REGISTRO_PLANO;SITUACAO\n", "", date(2026, 10, 1))


def test_plano_sem_registro_e_vinculo_manual(amostras, fonte, referencia_ans):
    tabelas = ingerir(amostras, fonte, JAN)
    tabela = por_plano(tabelas, "Essencial Enfermaria")
    plano = Plano.objects.get(pk=tabela.plano_id)
    plano.registro_ans = ""
    plano.save()
    tabela = TabelaPreco.objects.get(pk=tabela.pk)
    publicacao.revalidar(tabela)
    assert "ANS_SEM_REGISTRO" in codigos(tabela)

    publicacao.vincular_registro(plano, " 900.101/26-1 ", "ana")
    tabela.refresh_from_db()
    assert "ANS_SEM_REGISTRO" not in codigos(tabela)
    assert tabela.auditoria.filter(acao="registro_vinculado").exists()


def test_registro_desconhecido_gera_alerta(referencia_ans):
    r = validar_contra_ans("999.999/99-9", {1: Decimal("100")}, date(2026, 9, 1))
    assert r[0]["codigo"] == "ANS_REGISTRO_DESCONHECIDO" and r[0]["severidade"] == "alerta"


def test_faixas_trocadas_destoam_do_padrao_da_ntrp(referencia_ans):
    from catalogo.models import ProdutoANS

    produto = ProdutoANS.objects.get(registro_ans="900.101/26-1")
    valores = {v.faixa: v.valor for v in produto.valores_comerciais.all()}
    valores[4], valores[5] = valores[5], valores[4]  # troca de colunas, erro clássico de digitação
    r = validar_contra_ans("900.101/26-1", valores, date(2026, 9, 1))
    padrao = next(v for v in r if v["codigo"] == "ANS_PADRAO_FAIXAS_DIFERENTE")
    assert set(padrao["faixas"]) == {4, 5}


def test_sem_referencia_sincronizada_so_informa():
    r = validar_contra_ans("900.101/26-1", {1: Decimal("100")}, date(2026, 9, 1))
    assert [v["codigo"] for v in r] == ["ANS_SEM_REFERENCIA"]
