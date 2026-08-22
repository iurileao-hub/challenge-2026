"""Invariantes de vigencia que o ORM nao expressa sozinho.

O dossie exige, em duas entidades, que periodos nao se sobreponham:

- `tariff_period`: "vigencias sem sobreposicao por condominio" (decisao 4);
- `program_enrollment`: "sem sobreposicao por unidade" (decisao 8).

Um CHECK nao resolve: a regra fala de *pares de linhas*, e CHECK so enxerga a
linha corrente. A ferramenta certa e a EXCLUSION CONSTRAINT do Postgres, que
recusa a insercao se o intervalo da nova linha intersectar (`&&`) o de outra
com o mesmo condominio/unidade (`=`). Combinar os operadores `&&` (GiST) e `=`
(B-tree) no mesmo indice exige a extensao `btree_gist`.

`upper` nulo vira infinito no DATERANGE -- exatamente a semantica de
"vigencia ainda aberta" que as duas tabelas usam.
"""

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeBoundary, RangeOperators
from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations, models
from django.db.models import Func


class DateRange(Func):
    """DATERANGE(inicio, fim, '[)') -- limite inferior fechado, superior aberto.

    O `[)` importa: uma vigencia que termina em 30/06 e outra que comeca em
    01/07 nao se tocam, mas com `[]` elas se sobreporiam no dia da virada.
    """

    function = "DATERANGE"
    output_field = DateRangeField()


class Migration(migrations.Migration):

    dependencies = [("core", "0001_initial")]

    operations = [
        BtreeGistExtension(),
        migrations.AddConstraint(
            model_name="tariffperiod",
            constraint=ExclusionConstraint(
                name="tariff_period_no_overlap_per_condo",
                expressions=[
                    (
                        DateRange(
                            "valid_from",
                            "valid_to",
                            RangeBoundary(inclusive_lower=True, inclusive_upper=False),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                    ("condominium", RangeOperators.EQUAL),
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name="programenrollment",
            constraint=ExclusionConstraint(
                name="enrollment_no_overlap_per_unit",
                expressions=[
                    (
                        DateRange(
                            "start_date",
                            "end_date",
                            RangeBoundary(inclusive_lower=True, inclusive_upper=False),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                    ("unit", RangeOperators.EQUAL),
                ],
            ),
        ),
    ]
