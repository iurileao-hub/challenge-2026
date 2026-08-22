"""Gateway de ingestao -- a decisao arquitetural central do projeto.

O HCA G2 nao fala OCPP (so Modbus TCP) e a GoodWe nao liberou a OpenAPI de
desenvolvedor do SEMS. A Sprint 1 decidiu tratar isso como decisao de
arquitetura em vez de obstaculo: **nenhuma parte da plataforma conhece a fonte
do dado.** Todas as fontes desembocam num evento canonico, modelado no
vocabulario OCPP (StartTransaction -> MeterValues -> StopTransaction) que a
Frente 1 levantou.

O que se ganha com isso e concreto e testavel: trocar de fonte e escrever um
adaptador de ~50 linhas, nao refatorar o sistema. E o dia em que a GoodWe
liberar a API, o stub vira integracao real sem que o motor de rateio, a IA ou o
painel percebam.

O modelo canonico e deliberadamente menor que o esquema: ele carrega o que
QUALQUER carregador consegue reportar. O que o esquema tem a mais (credencial
resolvida, tarifa congelada, competencia) e responsabilidade da plataforma, nao
da fonte -- e por isso nao entra aqui.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from django.db import transaction

from core.models import (
    ChargePoint,
    ChargingSession,
    Condominium,
    Credential,
    MeasurementSource,
    TariffPeriod,
    TelemetryReading,
)


@dataclass
class CanonicalSession:
    """Uma sessao como qualquer fonte consegue descreve-la.

    Note o que NAO esta aqui: unidade, tarifa, valor, competencia. A fonte
    reporta o que o equipamento fez; quem a pessoa e e quanto custa e decisao
    da plataforma.
    """

    charge_point_serial: str
    auth_id: str
    auth_method: str
    session_start: datetime
    session_end: datetime | None
    meter_start: Decimal
    meter_stop: Decimal | None
    energy_kwh: Decimal
    max_power_kw: Decimal | None = None
    status: str = "completed"
    stop_reason: str | None = None
    measurement_source: str = MeasurementSource.CLOUD
    readings: list["CanonicalReading"] = field(default_factory=list)
    source_ref: str | None = None


@dataclass
class CanonicalReading:
    ts: datetime
    kind: str
    state: str | None = None
    power_kw: Decimal | None = None
    energy_kwh_total: Decimal | None = None


@dataclass
class IngestionReport:
    source: str
    sessions_ingested: int = 0
    sessions_skipped: int = 0
    readings_ingested: int = 0
    unresolved_credentials: list[str] = field(default_factory=list)

    def render(self) -> str:
        linhas = [
            f"fonte: {self.source}",
            f"  sessoes ingeridas: {self.sessions_ingested}",
            f"  sessoes ignoradas (ja existentes): {self.sessions_skipped}",
            f"  leituras de telemetria: {self.readings_ingested}",
        ]
        if self.unresolved_credentials:
            linhas.append(
                f"  credenciais nao resolvidas: {len(set(self.unresolved_credentials))} "
                f"-> {sorted(set(self.unresolved_credentials))[:5]}"
            )
        return "\n".join(linhas)


class SourceAdapter(abc.ABC):
    """Contrato que toda fonte cumpre. E a unica coisa que o gateway conhece."""

    name: str = "abstract"

    @abc.abstractmethod
    def fetch(self, **kwargs) -> list[CanonicalSession]:
        """Devolve sessoes canonicas. Sem efeito no banco -- so leitura."""


class IngestionGateway:
    """Normaliza, resolve credenciais, congela tarifa e persiste."""

    def __init__(self, condominium: Condominium):
        self.condo = condominium

    def _resolve_tariff(self, moment: datetime) -> TariffPeriod | None:
        from billing.competence import condo_tz

        d = moment.astimezone(condo_tz()).date()
        return (
            TariffPeriod.objects.filter(condominium=self.condo, valid_from__lte=d)
            .filter(valid_to__isnull=True)
            .order_by("-valid_from")
            .first()
        )

    @transaction.atomic
    def ingest(self, adapter: SourceAdapter, **kwargs) -> IngestionReport:
        report = IngestionReport(source=adapter.name)
        sessions = adapter.fetch(**kwargs)

        points = {p.serial_number: p for p in ChargePoint.objects.filter(condominium=self.condo)}
        creds = {c.auth_tag: c for c in Credential.objects.filter(
            user__unit__condominium=self.condo
        )}

        for cs in sessions:
            point = points.get(cs.charge_point_serial)
            if not point:
                report.sessions_skipped += 1
                continue

            # Deduplicacao pela chave natural do equipamento: mesmo ponto, mesmo
            # instante de inicio. Reingerir o mesmo arquivo nao duplica cobranca.
            if ChargingSession.objects.filter(
                charge_point=point, session_start=cs.session_start
            ).exists():
                report.sessions_skipped += 1
                continue

            credential = creds.get(cs.auth_id)
            if credential is None:
                # Sessao orfa: persistida com o auth_id BRUTO, fora do rateio ate
                # alguem vincular a credencial. Descartar seria perder o consumo;
                # cobrar de quem nao se sabe seria pior.
                report.unresolved_credentials.append(cs.auth_id)

            tariff = self._resolve_tariff(cs.session_start)
            encerrada = cs.status != "in_progress"
            session = ChargingSession.objects.create(
                charge_point=point,
                credential=credential,
                auth_id=cs.auth_id,
                auth_method=cs.auth_method,
                session_start=cs.session_start,
                session_end=cs.session_end,
                meter_start=cs.meter_start,
                meter_stop=cs.meter_stop,
                energy_kwh=cs.energy_kwh,
                max_power_kw=cs.max_power_kw,
                status=cs.status,
                stop_reason=cs.stop_reason,
                measurement_source=cs.measurement_source,
                applied_tariff=tariff if encerrada else None,
                # Congelar a tarifa e responsabilidade do gateway, no momento em
                # que a sessao entra -- e o snapshot da decisao 4.
                applied_tariff_kwh=(tariff.price_kwh if (tariff and encerrada) else None),
            )
            report.sessions_ingested += 1

            leituras = [
                TelemetryReading(
                    charge_point=point, session=session, ts=r.ts, kind=r.kind,
                    state=r.state, power_kw=r.power_kw,
                    energy_kwh_total=r.energy_kwh_total,
                    measurement_source=cs.measurement_source,
                )
                for r in cs.readings
            ]
            TelemetryReading.objects.bulk_create(leituras)
            report.readings_ingested += len(leituras)

        return report
