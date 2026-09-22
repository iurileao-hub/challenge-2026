"""Porta de entrada de dados pela linha de comando.

    manage.py ingest semsplus_log              # as 72 sessoes reais do HCA G2 da FIAP
    manage.py ingest sems_stub --path x.json   # payload no contrato SEMS
    manage.py ingest sems_stub --path x.json --resume   # so o que e novo desde a ultima vez
    manage.py ingest --replay                  # reprocessa a quarentena
    manage.py ingest --status                  # diario das ultimas execucoes

Em producao, `ingest <fonte> --resume` e o que um agendador (cron, Celery beat)
chama de tempos em tempos: e o modo PULL. O modo PUSH nao passa por aqui -- e o
endpoint `POST /api/v1/ingest/<fonte>/`.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import Condominium
from ingestion.adapters import PULLABLE
from ingestion.gateway import IngestionGateway
from ingestion.models import IngestionRun, RawEvent
from ingestion.replay import replay_quarantine


class Command(BaseCommand):
    help = "Ingere dados de uma fonte pelo gateway (ou reprocessa a quarentena)."

    def add_arguments(self, parser):
        parser.add_argument("source", nargs="?", choices=sorted(PULLABLE))
        parser.add_argument("--path", help="arquivo da fonte (payload SEMS, CSV do SEMS+, dataset)")
        parser.add_argument("--resume", action="store_true",
                            help="continua da marca d'agua da ultima execucao")
        parser.add_argument("--serial", help="(dataset) ponto onde reencenar as sessoes")
        parser.add_argument("--limit", type=int, help="(dataset) numero de sessoes")
        parser.add_argument("--shift-to", help="(dataset) desloca a serie para esta data")
        parser.add_argument("--replay", action="store_true", help="reprocessa a quarentena")
        parser.add_argument("--status", action="store_true", help="mostra o diario de execucoes")

    def handle(self, *args, **opts):
        condo = Condominium.objects.order_by("id").first()
        if not condo:
            raise CommandError("nenhum condominio: rode `manage.py seed_demo --months 6 --reset`")

        if opts["status"]:
            return self._status()
        if opts["replay"]:
            reports = replay_quarantine(condo, source=opts["source"])
            if not reports:
                self.stdout.write("quarentena vazia: nada a reprocessar")
            for r in reports:
                self.stdout.write(r.render())
            return
        if not opts["source"]:
            raise CommandError("informe a fonte, ou use --replay / --status")

        kwargs = {}
        if opts["path"]:
            chave = "payload_path" if opts["source"] == "sems_stub" else "path"
            kwargs[chave] = Path(opts["path"])
        elif opts["source"] == "sems_stub":
            raise CommandError("sems_stub precisa de --path")
        if opts["source"] == "asensio_dataset":
            kwargs["charge_point_serial"] = (
                opts["serial"] or condo.charge_points.order_by("id").first().serial_number
            )
            kwargs["limit"] = opts["limit"]
            kwargs["shift_to"] = opts["shift_to"]

        report = IngestionGateway(condo).ingest(
            PULLABLE[opts["source"]](), resume=opts["resume"], **kwargs
        )
        self.stdout.write(report.render())

    def _status(self):
        w = self.stdout.write
        w("ultimas execucoes:")
        for run in IngestionRun.objects.all()[:10]:
            w(f"  {run.started_at:%d/%m %H:%M}  {run.source:<18} {run.mode:<7} {run.status:<8} "
              f"recebidos {run.received:>4} · criadas {run.created:>4} · atualizadas {run.updated:>3} "
              f"· duplicatas {run.duplicates:>4} · quarentena {run.rejected + run.unknown_point + run.conflicts:>3}")
        pend = RawEvent.objects.filter(outcome__in=RawEvent.QUARANTINE, resolved_at__isnull=True)
        w(f"quarentena pendente: {pend.count()}")
        for ev in pend[:10]:
            w(f"  [{ev.outcome}] {ev.source}: {(ev.reason or '')[:100]}")
