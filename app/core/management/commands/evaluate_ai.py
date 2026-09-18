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
from intelligence.evaluation import evaluate, sensitivity


class Command(BaseCommand):
    help = "Gera dados com gabarito, roda a deteccao e reporta recall e sensibilidade."

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=6)
        parser.add_argument("--seed", type=int, default=20260831)
        parser.add_argument("--seeds", type=int, default=3,
                            help="quantas sementes consecutivas medir (a partir de --seed)")
        parser.add_argument("--anomaly-rate", type=float, default=0.08)
        parser.add_argument("--no-isolation-forest", action="store_true")

    def handle(self, *args, **opts):
        """Mede SEM tocar no banco de demonstracao.

        Cada medicao roda numa transacao que e desfeita no fim. A versao
        anterior apagava o cenario inteiro para gerar o seu, e quem a rodasse
        antes de uma demonstracao encontrava 404 em todas as telas.
        """
        w = self.stdout.write
        seeds = [opts["seed"] + i for i in range(opts["seeds"])]

        w(self.style.MIGRATE_HEADING("\n[1/2] Anomalias NITIDAS -- o que e obvio e pego?"))
        w("      Intensidades bem alem do limiar das regras. Recall alto aqui e o esperado:\n"
          "      e teste de integracao do detector, NAO estimativa de desempenho em campo.\n")
        for seed in seeds:
            report, _, n = self._measure(seed, spread=False, opts=opts)
            w(f"  semente {seed} ({n} sessoes)")
            w("  " + report.render().replace("\n", "\n  ") + "\n")

        w(self.style.MIGRATE_HEADING("[2/2] Curva de sensibilidade -- ONDE o detector opera"))
        w("      Intensidades espalhadas, inclusive abaixo do limiar. Abaixo dele a politica do\n"
          "      condominio diz que NAO e anomalia: deteccao ali seria falso alarme.\n")
        acumulado: dict = {}
        for seed in seeds:
            _, curva, _ = self._measure(seed, spread=True, opts=opts, anomaly_rate=0.25)
            for cat, linhas in curva.items():
                for ln in linhas:
                    a = acumulado.setdefault((cat, ln["faixa"], ln["deve_sinalizar"]), [0, 0, 0])
                    a[0] += ln["injetadas"]
                    a[1] += ln["regra"]
                    a[2] += ln["floresta"]
        atual = None
        for (cat, faixa, deve), (inj, regra, floresta) in acumulado.items():
            if cat != atual:
                w(f"  {cat:<42} {'fase 1 (regra)':>16} {'fase 2 (IF)':>14}   politica")
                atual = cat
            pct = lambda n: f"{n:>3}/{inj:<3} {n / inj:>4.0%}" if inj else "      --"  # noqa: E731
            w(f"    {faixa:<40} {pct(regra):>16} {pct(floresta):>14}   "
              f"{'sinalizar' if deve else 'nao sinalizar'}")
        w(self.style.WARNING(
            "\nLeitura: a fase 1 e uma POLITICA com limiar declarado, nao um classificador\n"
            "treinado: degrau limpo no limiar e o comportamento correto. A fase 2 (Isolation\n"
            "Forest) so ve o que a fase 1 deixou passar, e cobre a zona cinzenta logo aquem do\n"
            "limiar -- o caso 'ainda nao violou a regra, mas ja destoa'. A 'precisao piso' da\n"
            "primeira tabela subestima o detector: o gerador produz ociosidade legitima que o\n"
            "gabarito nao marca."
        ))
        w(self.style.SUCCESS("\nBanco de demonstracao intacto: as medicoes foram desfeitas.\n"))

    def _measure(self, seed, *, spread, opts, anomaly_rate=None):
        tz = ZoneInfo("America/Sao_Paulo")
        end = date(2026, 5, 31)
        start = date(2026, max(6 - opts["months"], 1), 1)
        with transaction.atomic():
            for model in TEARDOWN_ORDER:
                model.objects.all().delete()
            condo = build_jardim_aurora(extra_residents=True)["condominium"]
            gen = SyntheticGenerator(
                condo, seed=seed, spread=spread,
                anomaly_rate=anomaly_rate or opts["anomaly_rate"],
            )
            result = gen.generate(start, end)
            run_detection(
                condo,
                datetime.combine(start, time.min, tzinfo=tz),
                datetime.combine(end, time.max, tzinfo=tz),
                use_isolation_forest=not opts["no_isolation_forest"],
            )
            out = (evaluate(result.ground_truth, condo),
                   sensitivity(result.ground_truth, condo), result.sessions_created)
            transaction.set_rollback(True)
        return out
