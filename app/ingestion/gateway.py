"""Gateway de ingestao -- a decisao arquitetural central do projeto.

O HCA G2 nao fala OCPP (so Modbus TCP) e a GoodWe nao liberou a OpenAPI de
desenvolvedor do SEMS. A Sprint 1 decidiu tratar isso como decisao de
arquitetura em vez de obstaculo: **nenhuma parte da plataforma conhece a fonte
do dado.** Todas as fontes desembocam num registro canonico, modelado no
vocabulario OCPP (StartTransaction -> MeterValues -> StopTransaction) que a
Frente 1 levantou.

O modelo canonico e deliberadamente menor que o esquema: ele carrega o que
QUALQUER carregador consegue reportar. O que o esquema tem a mais (credencial
resolvida, tarifa congelada, competencia) e responsabilidade da plataforma, nao
da fonte -- e por isso nao entra aqui.

Segunda versao: o que mudou e por que
-------------------------------------
A primeira versao provava a tese para UM formato de entrega: lote de sessoes ja
encerradas, lido de arquivo, uma vez. Nao sabemos como a GoodWe vai entregar o
dado -- e e plausivel que ela tambem nao saiba ainda. As formas realistas sao
tres (ver `docs/sprint2-ingestao-e-integracao.md`): consulta periodica a nuvem,
entrega de eventos por webhook, e gateway de borda lendo Modbus na garagem. As
tres tem em comum o que o lote de arquivo nao tem: **registro parcial, repetido,
fora de ordem, e ocasionalmente torto.** O gateway agora garante:

- *Idempotencia.* Reentregar nao duplica. A chave preferida e o id da fonte
  (`source`, `source_ref`); a de reserva e a chave natural do equipamento
  (ponto + inicio, com tolerancia de relogio entre fontes diferentes). As duas
  sao UNIQUE no banco: a corrida entre duas entregas simultaneas perde no
  Postgres, nao vira cobranca em dobro.
- *Ciclo de vida.* Sessao que chegou `in_progress` e FECHADA pela entrega
  seguinte. Antes, a segunda entrega era descartada como duplicata e o kWh
  nunca era cobrado.
- *Isolamento de falha por registro.* Cada registro roda no seu savepoint. Um
  JSON torto vai para a quarentena com motivo legivel; os outros 999 entram.
- *Nada se perde em silencio.* Todo registro recebido vira `RawEvent` com o
  payload original e o desfecho. Recusado nao e descartado: e reprocessavel.
- *Fatura fechada nao se reescreve.* Se a fonte corrigir a energia de uma
  sessao ja faturada, o gateway registra CONFLITO e nao toca na sessao. A
  correcao segue o mesmo caminho de tudo o que chega depois do fechamento:
  linha de ajuste, decidida por gente.

A fronteira com a IA e explicita: **o gateway recusa o que e impossivel de
armazenar; o detector sinaliza o que e implausivel.** Sessao de 0 kWh entra.
Sessao de 90 kWh num carro de 40 entra (e o detector a pega). Sessao que termina
antes de comecar nao entra.
"""

from __future__ import annotations

import abc
import math
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from core.models import (
    AppUser,
    ChargePoint,
    ChargingSession,
    Condominium,
    Credential,
    Invoice,
    InvoiceLine,
    MeasurementSource,
    TariffPeriod,
    TelemetryReading,
)
from ingestion.models import IngestionRun, RawEvent

#: Duas fontes diferentes descrevendo a MESMA sessao fisica nao concordam no
#: segundo: a nuvem carimba quando recebeu, a borda quando leu o registrador.
#: Dentro desta janela, no mesmo conector, e a mesma sessao -- dois carros nao
#: iniciam recarga no mesmo cabo com dois minutos de diferenca.
CLOCK_TOLERANCE = timedelta(seconds=120)

#: Relogio de equipamento sem NTP produz datas absurdas. Um dia de folga cobre
#: fuso mal configurado; alem disso e lixo, e lixo com data futura cairia numa
#: competencia que ainda nao existe.
FUTURE_TOLERANCE = timedelta(days=1)

#: "Medicao certificada vale mais que numero de API" (Frente 2). Quando a mesma
#: sessao chega por duas fontes, a de maior lastro metrologico prevalece.
SOURCE_RANK = {
    MeasurementSource.CLOUD: 1,
    MeasurementSource.MODBUS_LOCAL: 2,
    MeasurementSource.MID_METER: 3,
}

VALID_STATUS = {c.value for c in ChargingSession.Status}
VALID_AUTH = {c.value for c in ChargingSession.AuthMethod}
VALID_KIND = {c.value for c in TelemetryReading.Kind}
VALID_STATE = {c.value for c in TelemetryReading.State}
LOCKED_INVOICE = {Invoice.Status.CLOSED, Invoice.Status.PAID, Invoice.Status.OVERDUE}


class RecordRejected(Exception):
    """O registro nao pode ser armazenado. A mensagem vai para a quarentena."""


@dataclass
class CanonicalReading:
    ts: datetime
    kind: str
    state: str | None = None
    power_kw: Decimal | None = None
    energy_kwh_total: Decimal | None = None


@dataclass
class CanonicalSession:
    """Uma sessao como qualquer fonte consegue descreve-la.

    Note o que NAO esta aqui: unidade, tarifa, valor, competencia. A fonte
    reporta o que o equipamento fez; quem a pessoa e e quanto custa e decisao
    da plataforma.

    `meter_start` e opcional desde que o primeiro dado REAL atravessou o
    gateway: o historico de sessoes do SEMS+ nao traz medidor acumulado. O
    campo obrigatorio era uma premissa nossa, nao uma propriedade dos
    carregadores.
    """

    charge_point_serial: str
    auth_id: str
    auth_method: str
    session_start: datetime
    session_end: datetime | None
    energy_kwh: Decimal
    meter_start: Decimal | None = None
    meter_stop: Decimal | None = None
    max_power_kw: Decimal | None = None
    status: str = "completed"
    stop_reason: str | None = None
    measurement_source: str = MeasurementSource.CLOUD
    readings: list[CanonicalReading] = field(default_factory=list)
    source_ref: str | None = None
    #: o registro como a fonte o entregou; vai para `RawEvent.payload`
    raw: dict | None = None


@dataclass
class CanonicalTelemetry:
    """Leitura que chega sozinha: heartbeat, mudanca de estado, MeterValues.

    O gateway a anexa a sessao aberta daquele ponto naquele instante, se houver.
    Se nao houver, fica fora de sessao -- e leitura fora de sessao e justamente
    o que denuncia carregador offline ou cabo conectado sem corrente.
    """

    charge_point_serial: str
    reading: CanonicalReading
    measurement_source: str = MeasurementSource.CLOUD
    raw: dict | None = None


@dataclass
class MalformedRecord:
    """O adaptador nao conseguiu traduzir. Segue para a quarentena como veio."""

    raw: dict
    reason: str
    source_ref: str | None = None


@dataclass
class IngestionReport:
    source: str
    run_id: int | None = None
    received: int = 0
    created: int = 0
    updated: int = 0
    duplicates: int = 0
    rejected: int = 0
    unknown_point: int = 0
    conflicts: int = 0
    readings_ingested: int = 0
    unresolved_credentials: list[str] = field(default_factory=list)
    rejections: list[str] = field(default_factory=list)
    sessions: list[ChargingSession] = field(default_factory=list)

    # Nomes da primeira versao, mantidos para quem ja os consumia. "Ignorada"
    # significava tres coisas diferentes; agora cada uma tem o seu contador.
    @property
    def sessions_ingested(self) -> int:
        return self.created

    @property
    def sessions_skipped(self) -> int:
        return self.duplicates + self.unknown_point

    @property
    def quarantined(self) -> int:
        return self.rejected + self.unknown_point + self.conflicts

    def render(self) -> str:
        linhas = [
            f"fonte: {self.source}",
            f"  registros recebidos: {self.received}",
            f"  sessoes criadas: {self.created} · atualizadas: {self.updated} "
            f"· duplicatas: {self.duplicates}",
            f"  leituras de telemetria: {self.readings_ingested}",
        ]
        if self.unknown_point:
            linhas.append(f"  carregador desconhecido (quarentena): {self.unknown_point}")
        if self.conflicts:
            linhas.append(f"  conflito com sessao ja faturada (quarentena): {self.conflicts}")
        if self.rejected:
            linhas.append(f"  recusados (quarentena): {self.rejected}")
            for motivo in self.rejections[:3]:
                linhas.append(f"    · {motivo[:110]}")
        orfas = sorted(set(self.unresolved_credentials))
        if orfas:
            linhas.append(f"  credenciais nao resolvidas: {len(orfas)} -> {orfas[:5]}")
        return "\n".join(linhas)


class SourceAdapter(abc.ABC):
    """Contrato que toda fonte cumpre. E a unica coisa que o gateway conhece.

    Um adaptador novo implementa duas coisas: `iter_raw` (COMO buscar: arquivo,
    HTTP, fila, Modbus) e `to_canonical` (o que cada campo SIGNIFICA). Separar
    as duas e o que faz a troca de transporte nao tocar no mapeamento, e
    vice-versa. `fetch` costura as duas com isolamento de falha por registro.
    """

    name: str = "abstract"
    mode: str = IngestionRun.Mode.FILE

    def __init__(self):
        self.cursor: str | None = None

    @abc.abstractmethod
    def iter_raw(self, *, since: str | None = None, **kwargs) -> Iterable[dict]:
        """Registros brutos da fonte, a partir da marca d'agua `since`."""

    @abc.abstractmethod
    def to_canonical(self, raw: dict) -> CanonicalSession | CanonicalTelemetry:
        """Traduz um registro. Pode levantar: `fetch` transforma em quarentena."""

    def ref_of(self, raw: dict) -> str | None:
        return None

    def fetch(self, *, since: str | None = None, **kwargs) -> Iterator:
        for raw in self.iter_raw(since=since, **kwargs):
            try:
                item = self.to_canonical(raw)
                if item.raw is None:
                    item.raw = raw
                yield item
            except Exception as exc:  # noqa: BLE001 -- a fronteira e esta
                yield MalformedRecord(
                    raw=raw if isinstance(raw, dict) else {"valor": repr(raw)},
                    reason=f"adaptador nao traduziu o registro: {type(exc).__name__}: {exc}",
                    source_ref=self._safe_ref(raw),
                )

    def _safe_ref(self, raw) -> str | None:
        try:
            return self.ref_of(raw)
        except Exception:  # noqa: BLE001
            return None


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float):
        # NaN e Infinity sao float valido em Python (e `json.loads` os aceita de
        # um corpo de webhook), mas nao sao JSON: o Postgres recusa o registro
        # inteiro. O diario nao pode ser o ponto que derruba a ingestao.
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return value.replace("\x00", "")  # jsonb nao armazena NUL
    if value is None or isinstance(value, (int, bool)):
        return value
    return str(value)


def _payload_of(item) -> dict:
    if getattr(item, "raw", None):
        return _jsonable(item.raw)
    data = asdict(item)
    data.pop("raw", None)
    # Sem payload proprio (gerador sintetico), o canonico E o registro. As
    # leituras ficam de fora: ja estao em `telemetry_reading`, e duplica-las
    # aqui multiplicaria a tabela por trinta sem acrescentar auditoria.
    if "readings" in data:
        data["readings"] = len(data["readings"])
    return _jsonable(data)


class IngestionGateway:
    """Valida, deduplica, resolve credencial, congela tarifa e persiste.

    Com `condominium`, so aceita carregadores daquele condominio (execucao por
    arquivo ou pull, que tem dono). Sem ele, descobre o condominio pelo numero
    de serie de cada registro -- e o caso do push, em que um unico endpoint
    recebe eventos de todos os condominios.
    """

    def __init__(self, condominium: Condominium | None = None):
        self.condo = condominium
        self._points: dict[str, ChargePoint] = {}

    # ------------------------------------------------------------------ API

    def last_cursor(self, source: str) -> str | None:
        run = (
            IngestionRun.objects.filter(source=source, condominium=self.condo)
            .exclude(status=IngestionRun.Status.FAILED)
            .exclude(cursor_after__isnull=True)
            .order_by("-started_at")
            .first()
        )
        return run.cursor_after if run else None

    def ingest(self, adapter: SourceAdapter, *, resume: bool = False, **kwargs) -> IngestionReport:
        """Executa um adaptador. `resume=True` continua da ultima marca d'agua."""
        since = kwargs.pop("since", None)
        if resume and since is None:
            since = self.last_cursor(adapter.name)
        run = IngestionRun.objects.create(
            condominium=self.condo, source=adapter.name, mode=adapter.mode,
            cursor_before=since,
        )
        try:
            report = self.ingest_items(adapter.fetch(since=since, **kwargs), run=run)
        except Exception as exc:
            # Falha do TRANSPORTE (arquivo ausente, HTTP fora): nao ha registro
            # a por em quarentena, mas a execucao fica no diario como falha, e a
            # marca d'agua nao avanca.
            run.status = IngestionRun.Status.FAILED
            run.error = f"{type(exc).__name__}: {exc}"
            run.finished_at = timezone.now()
            run.save()
            raise
        run.cursor_after = getattr(adapter, "cursor", None) or since
        run.save(update_fields=["cursor_after"])
        return report

    def ingest_items(self, items: Iterable, *, run: IngestionRun) -> IngestionReport:
        report = IngestionReport(source=run.source, run_id=run.id)
        for item in items:
            self.process(item, run, report)
        return self.finish(run, report)

    def finish(self, run: IngestionRun, report: IngestionReport) -> IngestionReport:
        """Fecha a execucao no diario: contadores, situacao, horario."""
        run.received = report.received
        run.created = report.created
        run.updated = report.updated
        run.duplicates = report.duplicates
        run.rejected = report.rejected
        run.unknown_point = report.unknown_point
        run.conflicts = report.conflicts
        run.orphans = len(report.unresolved_credentials)
        run.readings = report.readings_ingested
        run.status = IngestionRun.Status.PARTIAL if report.quarantined else IngestionRun.Status.OK
        run.finished_at = timezone.now()
        run.save()
        return report

    # ------------------------------------------------------------- registro

    def process(self, item, run: IngestionRun, report: IngestionReport) -> str:
        """Um registro, do canonico ao banco. Devolve o desfecho."""
        report.received += 1
        source_ref = getattr(item, "source_ref", None)
        if isinstance(item, MalformedRecord):
            self._log(run, item.raw, RawEvent.Outcome.REJECTED, item.reason, source_ref)
            report.rejected += 1
            report.rejections.append(item.reason)
            return RawEvent.Outcome.REJECTED

        payload = _payload_of(item)
        try:
            # Savepoint por registro: o IntegrityError de um nao envenena a
            # transacao dos outros.
            with transaction.atomic():
                if isinstance(item, CanonicalTelemetry):
                    outcome, reason, session, warnings = self._persist_telemetry(item, report)
                else:
                    outcome, reason, session, warnings = self._persist_session(item, run, report)
        except RecordRejected as exc:
            outcome, reason, session, warnings = RawEvent.Outcome.REJECTED, str(exc), None, []
        except IntegrityError as exc:
            # Perdeu a corrida para outra entrega do mesmo evento, ou violou um
            # CHECK que a validacao nao previu. Nos dois casos: quarentena.
            outcome, reason, session, warnings = (
                RawEvent.Outcome.REJECTED, f"banco recusou: {str(exc).splitlines()[0]}", None, [],
            )

        if outcome == RawEvent.Outcome.REJECTED:
            report.rejected += 1
            report.rejections.append(reason or "")
        self._log(run, payload, outcome, reason, source_ref, session, warnings)
        return outcome

    def _log(self, run, payload, outcome, reason, source_ref, session=None, warnings=None):
        RawEvent.objects.create(
            run=run, source=run.source, source_ref=source_ref, payload=_jsonable(payload),
            outcome=outcome, reason=reason, session=session, warnings=warnings or [],
        )

    # ------------------------------------------------------------ validacao

    def _validate(self, cs: CanonicalSession) -> None:
        if not cs.charge_point_serial:
            raise RecordRejected("sem numero de serie do carregador")
        if not isinstance(cs.session_start, datetime):
            raise RecordRejected("sem instante de inicio")
        if cs.session_start.tzinfo is None:
            raise RecordRejected(
                "inicio sem fuso horario: o adaptador precisa declarar em que fuso a fonte escreve"
            )
        if cs.session_end is not None:
            if cs.session_end.tzinfo is None:
                raise RecordRejected("fim sem fuso horario")
            if cs.session_end < cs.session_start:
                raise RecordRejected(
                    f"fim ({cs.session_end.isoformat()}) anterior ao inicio ({cs.session_start.isoformat()})"
                )
        if cs.session_start > timezone.now() + FUTURE_TOLERANCE:
            raise RecordRejected(f"inicio no futuro ({cs.session_start.isoformat()}): relogio da fonte suspeito")
        if cs.status not in VALID_STATUS:
            raise RecordRejected(f"situacao desconhecida: {cs.status!r}")
        if cs.status != "in_progress" and cs.session_end is None:
            raise RecordRejected(f"sessao {cs.status} sem instante de fim")
        if cs.auth_method not in VALID_AUTH:
            raise RecordRejected(f"metodo de autenticacao desconhecido: {cs.auth_method!r}")
        if cs.measurement_source not in SOURCE_RANK:
            raise RecordRejected(f"origem de medicao desconhecida: {cs.measurement_source!r}")
        try:
            if cs.energy_kwh is None or Decimal(cs.energy_kwh) < 0:
                raise RecordRejected(f"energia invalida: {cs.energy_kwh!r}")
        except (InvalidOperation, TypeError) as exc:
            raise RecordRejected(f"energia nao numerica: {cs.energy_kwh!r}") from exc

    def _point(self, serial: str) -> ChargePoint | None:
        if serial not in self._points:
            qs = ChargePoint.objects.select_related("condominium").filter(serial_number=serial)
            if self.condo is not None:
                qs = qs.filter(condominium=self.condo)
            self._points[serial] = qs.first()
        return self._points[serial]

    def _resolve_credential(self, cs, point, warnings) -> Credential | None:
        """Quem e a pessoa. Nulo = sessao orfa, persistida e fora do rateio.

        Descartar seria perder o consumo; cobrar de quem nao se sabe seria pior.
        """
        if not cs.auth_id:
            return None
        cred = (
            Credential.objects.select_related("user__unit")
            .filter(auth_tag=cs.auth_id)
            .first()
        )
        if cred is None:
            return None
        unit = cred.user.unit
        if unit is not None and unit.condominium_id != point.condominium_id:
            warnings.append(f"credencial {cs.auth_id} pertence a outro condominio: sessao mantida orfa")
            return None
        if cred.status != Credential.Status.ACTIVE:
            # Atribui (o historico de um cartao substituido precisa continuar
            # resolvendo), mas avisa: cartao revogado em uso e caso de gestor.
            warnings.append(f"credencial {cs.auth_id} esta {cred.get_status_display().lower()}")
        return cred

    def _freeze_tariff(self, cs, point, credential):
        """Congela a tarifa no momento em que a sessao ENCERRA na plataforma.

        A data de referencia e o inicio da sessao no fuso civil do condominio
        -- a mesma regra da competencia. Visitante tem tarifa propria.
        """
        from billing.competence import condo_tz

        day = cs.session_start.astimezone(condo_tz()).date()
        tariff = TariffPeriod.objects.in_force_on(point.condominium, day)
        if tariff is None:
            raise RecordRejected(
                f"nenhuma vigencia de tarifa cobre {day.isoformat()}: cadastre a vigencia e reprocesse"
            )
        price = tariff.price_kwh
        if credential is not None and credential.user.role == AppUser.Role.VISITOR:
            price = point.condominium.visitor_price_kwh or price
        return tariff, price

    # ---------------------------------------------------------- persistencia

    def _find_existing(self, cs, point, source: str) -> ChargingSession | None:
        if cs.source_ref:
            found = ChargingSession.objects.filter(source=source, source_ref=cs.source_ref).first()
            if found:
                return found
        return (
            ChargingSession.objects.filter(
                charge_point=point,
                session_start__gte=cs.session_start - CLOCK_TOLERANCE,
                session_start__lte=cs.session_start + CLOCK_TOLERANCE,
            )
            .order_by("session_start")
            .first()
        )

    def _persist_session(self, cs: CanonicalSession, run, report):
        self._validate(cs)
        point = self._point(cs.charge_point_serial)
        if point is None:
            report.unknown_point += 1
            return (
                RawEvent.Outcome.UNKNOWN_POINT,
                f"carregador {cs.charge_point_serial} nao cadastrado: cadastre o ponto e reprocesse",
                None, [],
            )

        warnings: list[str] = []
        existing = self._find_existing(cs, point, run.source)
        if existing is not None:
            return self._update_existing(existing, cs, point, run, report, warnings)

        credential = self._resolve_credential(cs, point, warnings)
        if credential is None:
            report.unresolved_credentials.append(cs.auth_id)
        closed = cs.status != "in_progress"
        tariff, price = self._freeze_tariff(cs, point, credential) if closed else (None, None)

        overlap = (
            ChargingSession.objects.filter(charge_point=point, session_start__lt=cs.session_end or cs.session_start)
            .filter(session_end__gt=cs.session_start)
            .first()
        )
        if overlap is not None:
            warnings.append(
                f"sobrepoe a sessao {overlap.pk} no mesmo conector: relogio da fonte ou sessao duplicada"
            )

        session = ChargingSession.objects.create(
            charge_point=point, credential=credential,
            auth_id=cs.auth_id or "", auth_method=cs.auth_method,
            session_start=cs.session_start, session_end=cs.session_end,
            meter_start=cs.meter_start, meter_stop=cs.meter_stop,
            energy_kwh=cs.energy_kwh, max_power_kw=cs.max_power_kw,
            status=cs.status, stop_reason=cs.stop_reason,
            measurement_source=cs.measurement_source,
            applied_tariff=tariff, applied_tariff_kwh=price,
            source=run.source, source_ref=cs.source_ref,
        )
        report.created += 1
        report.sessions.append(session)
        report.readings_ingested += self._persist_readings(session, point, cs)
        return RawEvent.Outcome.CREATED, None, session, warnings

    def _update_existing(self, existing, cs, point, run, report, warnings):
        changed: list[str] = []
        new_readings = self._persist_readings(existing, point, cs, dedupe=True)
        report.readings_ingested += new_readings

        if existing.status == "in_progress":
            closing = cs.status != "in_progress"
            if closing:
                tariff, price = self._freeze_tariff(cs, point, existing.credential)
                existing.applied_tariff, existing.applied_tariff_kwh = tariff, price
                existing.session_end = cs.session_end
                existing.status = cs.status
                existing.stop_reason = cs.stop_reason
                changed.append(f"encerrada ({cs.status})")
            if Decimal(cs.energy_kwh) != existing.energy_kwh:
                changed.append(f"energia {existing.energy_kwh} -> {cs.energy_kwh} kWh")
                existing.energy_kwh = cs.energy_kwh
            if cs.meter_stop is not None:
                existing.meter_stop = cs.meter_stop
            if cs.max_power_kw is not None:
                existing.max_power_kw = cs.max_power_kw
            if changed:
                existing.save()
        elif cs.status != "in_progress" and Decimal(cs.energy_kwh) != existing.energy_kwh:
            # A mesma sessao, ja encerrada, com outro numero. So prevalece a
            # fonte de MAIOR lastro metrologico -- e nunca sobre fatura fechada.
            incoming = SOURCE_RANK[cs.measurement_source]
            stored = SOURCE_RANK.get(existing.measurement_source, 0)
            if incoming > stored:
                billed = InvoiceLine.objects.filter(
                    session=existing, invoice__status__in=LOCKED_INVOICE
                ).exists()
                if billed:
                    report.conflicts += 1
                    return (
                        RawEvent.Outcome.CONFLICT,
                        f"sessao {existing.pk} ja faturada com {existing.energy_kwh} kWh; "
                        f"{cs.measurement_source} reporta {cs.energy_kwh} kWh. Fatura fechada "
                        "nao se reescreve: decidir ajuste manualmente",
                        existing, warnings,
                    )
                changed.append(
                    f"energia {existing.energy_kwh} -> {cs.energy_kwh} kWh "
                    f"({existing.measurement_source} -> {cs.measurement_source})"
                )
                existing.energy_kwh = cs.energy_kwh
                existing.measurement_source = cs.measurement_source
                if cs.meter_start is not None:
                    existing.meter_start = cs.meter_start
                if cs.meter_stop is not None:
                    existing.meter_stop = cs.meter_stop
                existing.save()
            else:
                warnings.append(
                    f"{cs.measurement_source} reporta {cs.energy_kwh} kWh para sessao gravada com "
                    f"{existing.energy_kwh} kWh ({existing.measurement_source}): mantido o gravado"
                )

        if changed or new_readings:
            report.updated += 1
            report.sessions.append(existing)
            motivo = "; ".join(changed) or f"{new_readings} leitura(s) nova(s)"
            return RawEvent.Outcome.UPDATED, motivo, existing, warnings
        report.duplicates += 1
        return RawEvent.Outcome.DUPLICATE, None, existing, warnings

    def _persist_readings(self, session, point, cs, dedupe: bool = False) -> int:
        if not cs.readings:
            return 0
        seen = set()
        if dedupe:
            seen = set(session.readings.values_list("ts", "kind"))
        rows = []
        for r in cs.readings:
            self._validate_reading(r)
            if (r.ts, r.kind) in seen:
                continue
            seen.add((r.ts, r.kind))
            rows.append(TelemetryReading(
                charge_point=point, session=session, ts=r.ts, kind=r.kind, state=r.state,
                power_kw=r.power_kw, energy_kwh_total=r.energy_kwh_total,
                measurement_source=cs.measurement_source,
            ))
        TelemetryReading.objects.bulk_create(rows, batch_size=2000)
        return len(rows)

    def _validate_reading(self, r: CanonicalReading) -> None:
        if not isinstance(r.ts, datetime) or r.ts.tzinfo is None:
            raise RecordRejected("leitura de telemetria sem instante com fuso")
        if r.kind not in VALID_KIND:
            raise RecordRejected(f"tipo de leitura desconhecido: {r.kind!r}")
        if r.state is not None and r.state not in VALID_STATE:
            raise RecordRejected(f"estado de conector desconhecido: {r.state!r}")

    def _persist_telemetry(self, item: CanonicalTelemetry, report):
        r = item.reading
        self._validate_reading(r)
        point = self._point(item.charge_point_serial)
        if point is None:
            report.unknown_point += 1
            return (
                RawEvent.Outcome.UNKNOWN_POINT,
                f"carregador {item.charge_point_serial} nao cadastrado", None, [],
            )
        if TelemetryReading.objects.filter(charge_point=point, ts=r.ts, kind=r.kind).exists():
            report.duplicates += 1
            return RawEvent.Outcome.DUPLICATE, None, None, []
        session = (
            ChargingSession.objects.filter(charge_point=point, session_start__lte=r.ts)
            .filter(Q(session_end__isnull=True) | Q(session_end__gte=r.ts))
            .order_by("-session_start")
            .first()
        )
        TelemetryReading.objects.create(
            charge_point=point, session=session, ts=r.ts, kind=r.kind, state=r.state,
            power_kw=r.power_kw, energy_kwh_total=r.energy_kwh_total,
            measurement_source=item.measurement_source,
        )
        report.readings_ingested += 1
        return RawEvent.Outcome.TELEMETRY, None, session, []

