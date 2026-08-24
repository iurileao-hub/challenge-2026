"""Mede a deteccao de anomalias contra o gabarito do gerador.

E o comando que responde, com numero, a pergunta que a rubrica faz: a IA e
estrutural ou decorativa? Decorativa nao tem metrica.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from core.management.commands.seed_demo import TEARDOWN_ORDER
from core.scenarios import build_jardim_aurora
from ingestion.generator import SyntheticGenerator
from intelligence.anomalies import run_detection
from intelligence.evaluation import evaluate


class Command(BaseCommand):
    help = "Gera dados com gabarito, roda a deteccao e reporta precisao/recall."

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=6)
        parser.add_argument("--seed", type=int, default=20260831)
        parser.add_argument("--anomaly-rate", type=float, default=0.08)
        parser.add_argument("--no-isolation-forest", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        for model in TEARDOWN_ORDER:
            model.objects.all().delete()

        scenario = build_jardim_aurora(extra_residents=True)
        condo = scenario["condominium"]
        tz = ZoneInfo("America/Sao_Paulo")

        end = date(2026, 5, 31)
        start = date(2026, max(6 - opts["months"], 1), 1)
        gen = SyntheticGenerator(condo, seed=opts["seed"], anomaly_rate=opts["anomaly_rate"])
        result = gen.generate(start, end)
        self.stdout.write(
            f"Gerados {result.sessions_created} sessoes e {result.readings_created} leituras "
            f"({start:%m/%Y} a {end:%m/%Y}); {result.anomalies_injected} anomalias injetadas.\n"
        )

        flags = run_detection(
            condo,
            datetime.combine(start, time.min, tzinfo=tz),
            datetime.combine(end, time.max, tzinfo=tz),
            use_isolation_forest=not opts["no_isolation_forest"],
        )
        self.stdout.write(f"Deteccao produziu {len(flags)} flags.\n")

        report = evaluate(result.ground_truth, condo)
        self.stdout.write("\n" + report.render() + "\n")
        self.stdout.write(self.style.WARNING(
            "\nLeitura: recall e a metrica confiavel. A 'precisao piso' subestima o "
            "detector,\nporque o gerador produz sessoes legitimamente extremas que o "
            "gabarito nao marca\n(ociosidade real, por exemplo) e que sao achados "
            "corretos, nao falsos positivos."
        ))
        # Este comando gera cenario novo por cima do que estava no banco: as
        # faturas somem e os logins do portal ficam orfaos, porque o vinculo
        # entre conta de acesso e pessoa quem faz e o `seed_demo`. Quem roda
        # isso antes de uma demonstracao encontra 404 em todas as telas e nao
        # tem como adivinhar o motivo. Avisar aqui e mais barato que depurar.
        self.stdout.write(self.style.NOTICE(
            "\nO cenario de demonstracao foi substituido. Para restaurar o portal:\n"
            "  python manage.py seed_demo --months 6 --reset\n"
            "  python manage.py pipeline --reconciliar"
        ))
