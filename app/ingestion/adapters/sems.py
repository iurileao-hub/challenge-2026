"""Adaptador SEMS -- stub do contrato, pronto para virar integracao real.

A GoodWe nao liberou a OpenAPI de desenvolvedor do SEMS para o desafio. A
Sprint 1 respondeu especificando o contrato a partir da documentacao publica e
do codigo aberto da comunidade, com nivel de confiabilidade declarado, e
congelando-o como stub.

Este arquivo e o congelamento. `fetch()` le um payload JSON no formato que o
contrato preve -- de um arquivo, hoje; de `GET /api/PowerStation/...`, no dia em
que houver credencial. O que muda nesse dia sao as ~10 linhas de `_load()`. O
mapeamento de campos, que e a parte que exige conhecimento do dominio, ja esta
escrito e testado.

Honestidade sobre o nivel de evidencia: os nomes de campo aqui vem da
documentacao publica e da observacao direta da plataforma SEMS+ (nivel [O] da
Frente 2), **nao** de uma chamada autenticada a API de carregadores -- que nao
existe publicamente documentada. Se a estrutura real divergir, diverge aqui, num
arquivo, e nao no motor de rateio.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from core.models import MeasurementSource
from ingestion.gateway import CanonicalReading, CanonicalSession, SourceAdapter
from ingestion.models import IngestionRun

#: Mapeamento contrato SEMS -> modelo canonico. Isolado como dado, e nao como
#: codigo, para que a divergencia futura seja uma edicao de dicionario.
FIELD_MAP = {
    "sn": "charge_point_serial",
    "card_no": "auth_id",
    "start_time": "session_start",
    "end_time": "session_end",
    "start_kwh": "meter_start",
    "end_kwh": "meter_stop",
    "charge_kwh": "energy_kwh",
    "max_power": "max_power_kw",
    "stop_reason": "stop_reason",
}


class SemsStubAdapter(SourceAdapter):
    name = "sems_stub"
    mode = IngestionRun.Mode.PULL

    def __init__(self, tz: str = "America/Sao_Paulo"):
        super().__init__()
        self.tz = ZoneInfo(tz)

    def _load(self, payload_path: Path) -> list[dict]:
        """O unico ponto que muda quando a API existir.

        Hoje: le arquivo. Amanha: `httpx.get(url, headers=auth).json()`.
        """
        data = json.loads(Path(payload_path).read_text())
        if isinstance(data, list):
            return data
        return data.get("data", {}).get("records", [])

    def _parse_dt(self, value: str | None):
        """Horario de parede da fonte -> instante com fuso.

        Se a string ja traz offset (`...-03:00`, `...Z`), ele e respeitado. A
        versao anterior fazia `replace(tzinfo=...)` incondicional: um `Z`
        viraria BRT sem converter, tres horas de erro silencioso -- o bastante
        para jogar uma sessao das 22h na competencia errada.
        """
        if not value:
            return None
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=self.tz)

    def ref_of(self, raw: dict) -> str | None:
        return f"sems:{raw['id']}" if raw.get("id") else None

    def iter_raw(self, *, since: str | None = None, payload_path: Path, **kwargs):
        """Pull incremental: so o que encerrou (ou mudou) depois de `since`.

        A marca d'agua e o maior `end_time` visto. Sessao ainda aberta nao a
        avanca, para que a proxima consulta a traga de novo, ja encerrada. A
        janela de consulta real deve recuar alguns minutos de `since`: a
        deduplicacao do gateway torna a sobreposicao inofensiva, e buraco entre
        duas janelas nao tem conserto.
        """
        corte = self._parse_dt(since) if since else None
        maior = corte
        for rec in self._load(payload_path):
            fim = None
            try:
                fim = self._parse_dt(rec.get("end_time"))
            except (ValueError, TypeError, AttributeError):
                pass  # registro torto segue adiante: quem o recusa e `fetch`
            if corte and fim and fim <= corte:
                continue
            if fim and (maior is None or fim > maior):
                maior = fim
            yield rec
        self.cursor = maior.isoformat() if maior else since

    def to_canonical(self, rec: dict) -> CanonicalSession:
        end = self._parse_dt(rec.get("end_time"))
        meter_start = rec.get("start_kwh")
        meter_stop = rec.get("end_kwh")
        return CanonicalSession(
            charge_point_serial=str(rec["sn"]),
            auth_id=str(rec.get("card_no") or "").strip(),
            # O SEMS reporta RFID em auto-start sem vinculo a pessoa
            # (achado [O] da Frente 2): quem e a pessoa e o cadastro
            # da plataforma que resolve, nao o carregador.
            auth_method="rfid" if rec.get("card_no") else "app",
            session_start=self._parse_dt(rec["start_time"]),
            session_end=end,
            meter_start=Decimal(str(meter_start)) if meter_start is not None else None,
            meter_stop=Decimal(str(meter_stop)) if meter_stop is not None else None,
            energy_kwh=Decimal(str(rec.get("charge_kwh", 0))),
            max_power_kw=(
                Decimal(str(rec["max_power"])) if rec.get("max_power") else None
            ),
            status="completed" if end else "in_progress",
            stop_reason=rec.get("stop_reason"),
            measurement_source=MeasurementSource.CLOUD,
            source_ref=self.ref_of(rec),
            readings=[
                CanonicalReading(
                    ts=self._parse_dt(r["ts"]),
                    kind="meter_value",
                    state=r.get("state", "charging"),
                    power_kw=Decimal(str(r["power"])) if r.get("power") is not None else None,
                    energy_kwh_total=(
                        Decimal(str(r["kwh_total"])) if r.get("kwh_total") is not None else None
                    ),
                )
                for r in rec.get("meter_values", [])
            ],
        )
