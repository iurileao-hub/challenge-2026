"""Reprocessamento da quarentena.

Registro recusado nao e registro perdido. As causas tipicas de recusa se
resolvem FORA do registro: o carregador ainda nao estava cadastrado, faltava a
vigencia de tarifa daquela data, o `session_ended` chegou antes do
`session_started`, o mapeamento do adaptador tinha um erro. Corrigida a causa,
o payload bruto guardado em `RawEvent` passa de novo pelo MESMO caminho de
qualquer entrega -- nao ha atalho de reprocessamento com regras proprias.
"""

from __future__ import annotations

from django.utils import timezone

from ingestion.adapters import adapter_for_replay
from ingestion.gateway import IngestionGateway, IngestionReport, MalformedRecord
from ingestion.models import IngestionRun, RawEvent


def replay_quarantine(condominium=None, source: str | None = None) -> list[IngestionReport]:
    pendentes = RawEvent.objects.filter(
        outcome__in=RawEvent.QUARANTINE, resolved_at__isnull=True
    ).exclude(outcome=RawEvent.Outcome.CONFLICT)  # conflito e decisao humana, nao se repete
    if source:
        pendentes = pendentes.filter(source=source)

    reports = []
    for nome in sorted(set(pendentes.values_list("source", flat=True))):
        lote = list(pendentes.filter(source=nome).order_by("received_at", "id"))
        adapter = adapter_for_replay(nome)
        run = IngestionRun.objects.create(
            condominium=condominium, source=nome, mode=IngestionRun.Mode.REPLAY
        )
        gw = IngestionGateway(condominium)
        report = IngestionReport(source=nome, run_id=run.id)
        for antigo in lote:
            try:
                item = adapter.to_canonical(antigo.payload)
                item.raw = antigo.payload
            except Exception as exc:  # noqa: BLE001
                item = MalformedRecord(
                    raw=antigo.payload, source_ref=antigo.source_ref,
                    reason=f"adaptador nao traduziu o registro: {type(exc).__name__}: {exc}",
                )
            desfecho = gw.process(item, run, report)
            if desfecho not in RawEvent.QUARANTINE:
                antigo.resolved_at = timezone.now()
                antigo.save(update_fields=["resolved_at"])
        reports.append(gw.finish(run, report))
    return reports
