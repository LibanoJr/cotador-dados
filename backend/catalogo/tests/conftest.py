from pathlib import Path

import pytest
from django.core.management import call_command

AMOSTRAS = Path(__file__).resolve().parents[2] / "amostras"


@pytest.fixture(autouse=True)
def media_temporaria(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture(scope="session")
def amostras():
    if not (AMOSTRAS / "gabarito.json").exists():
        call_command("gerar_pdfs_exemplo")
    return AMOSTRAS


@pytest.fixture
def fonte(db):
    from catalogo.models import FonteDados

    return FonteDados.objects.create(nome="Fonte de teste", tipo="upload", frequencia_esperada_dias=30)


@pytest.fixture
def referencia_ans(db, amostras):
    """Carrega a referência ANS fictícia (inclui um produto suspenso desde 15/08/2026)."""
    from datetime import date

    from catalogo.servicos.sincronizacao_ans import importar_referencia

    return importar_referencia(
        (amostras / "ans" / "produtos.csv").read_text(encoding="utf-8"),
        (amostras / "ans" / "valor_comercial.csv").read_text(encoding="utf-8"),
        date(2026, 9, 28),
    )
