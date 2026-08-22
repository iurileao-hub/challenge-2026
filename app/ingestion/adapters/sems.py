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

    def __init__(self, tz: str = "America/Sao_Paulo"):
        self.tz = ZoneInfo(tz)

    def _load(self, payload_path: Path) -> list[dict]:
        """O unico ponto que muda quando a API existir.

        Hoje: le arquivo. Amanha: `httpx.get(url, headers=auth).json()`.
        """
        data = json.loads(Path(payload_path).read_text())
        return data.get("data", {}).get("records", data if isinstance(data, list) else [])

    def _parse_dt(self, value: str | None):
        if not value:
            return None
        return datetime.fromisoformat(value).replace(tzinfo=self.tz)

    def fetch(self, *, payload_path: Path, **kwargs) -> list[CanonicalSession]:
        out = []
        for rec in self._load(payload_path):
            end = self._parse_dt(rec.get("end_time"))
            meter_stop = rec.get("end_kwh")
            out.append(
                CanonicalSession(
                    charge_point_serial=str(rec["sn"]),
                    auth_id=str(rec.get("card_no") or "").strip(),
                    # O SEMS reporta RFID em auto-start sem vinculo a pessoa
                    # (achado [O] da Frente 2): quem e a pessoa e o cadastro
                    # da plataforma que resolve, nao o carregador.
                    auth_method="rfid" if rec.get("card_no") else "app",
                    session_start=self._parse_dt(rec["start_time"]),
                    session_end=end,
                    meter_start=Decimal(str(rec.get("start_kwh", 0))),
                    meter_stop=Decimal(str(meter_stop)) if meter_stop is not None else None,
                    energy_kwh=Decimal(str(rec.get("charge_kwh", 0))),
                    max_power_kw=(
                        Decimal(str(rec["max_power"])) if rec.get("max_power") else None
                    ),
                    status="completed" if end else "in_progress",
                    stop_reason=rec.get("stop_reason"),
                    measurement_source=MeasurementSource.CLOUD,
                    source_ref=f"sems:{rec.get('id') or rec.get('sn')}",
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
            )
        return out
