"""Garante no banco que a mesma tabela nunca tenha duas versões valendo no mesmo dia.

A regra também existe na aplicação (servicos/publicacao.py), mas a aplicação pode ter bug e
pode haver mais de um processo publicando ao mesmo tempo. A restrição de exclusão do PostgreSQL
é a última linha de defesa: o banco recusa a gravação que criaria sobreposição de vigência.

Só roda no PostgreSQL. No SQLite (testes locais rápidos) a migração não faz nada.
"""
from django.db import migrations

CRIAR = """
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE catalogo_tabelapreco
  ADD CONSTRAINT tabelapreco_vigencia_sem_sobreposicao
  EXCLUDE USING gist (
    plano_id WITH =,
    regiao WITH =,
    tipo_contratacao WITH =,
    (coparticipacao::int) WITH =,
    daterange(vigencia_inicio, vigencia_fim, '[]') WITH &&
  )
  WHERE (status IN ('publicada', 'substituida'));
"""

REMOVER = """
ALTER TABLE catalogo_tabelapreco DROP CONSTRAINT IF EXISTS tabelapreco_vigencia_sem_sobreposicao;
"""


def _executar(sql):
    def rodar(apps, schema_editor):
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(sql)

    return rodar


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0002_referencia_ans")]

    operations = [migrations.RunPython(_executar(CRIAR), _executar(REMOVER))]
