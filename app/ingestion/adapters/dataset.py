"""Adaptador do dataset real de Asensio et al. (2021).

Mapeia campo a campo as 3.395 sessoes reais para o contrato canonico. Serve
para dois propositos distintos, e vale separa-los:

1. **Demonstrar que o gateway e mesmo plugavel** -- se um CSV de 2014 de um
   estacionamento americano entra pelo mesmo cano que o SEMS entraria, o cano
   e agnostico de verdade, e nao so na prosa.
2. Alimentar a plataforma com **comportamento real de recarga**, com todas as
   sujeiras que dado real tem e dado sintetico nao inventa sozinho: sessoes de
   0 kWh, duracoes de 55 h, medidor que nao fecha.

O que o adaptador NAO faz e transformar o dado: as sessoes entram como estao,
inclusive as estranhas. Limpar na entrada esconderia justamente o que a
deteccao de anomalias existe para encontrar.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from core.models import MeasurementSource
from ingestion.calibration import DATASET_PATH
from ingestion.gateway import CanonicalSession, SourceAdapter

#: dataset (Asensio et al.) -> modelo canonico
FIELD_MAP = {
    "sessionId": "source_ref",
    "userId": "auth_id",
    "stationId": "charge_point_serial",
    "created": "session_start",
    "ended": "session_end",
    "kwhTotal": "energy_kwh",
    "platform": "auth_method",
}


class AsensioDatasetAdapter(SourceAdapter):
    name = "asensio_dataset"

    def __init__(self, tz: str = "America/Sao_Paulo"):
        self.tz = ZoneInfo(tz)

    def fetch(
        self,
        *,
        charge_point_serial: str,
        path: Path = DATASET_PATH,
        limit: int | None = None,
        shift_to: str | None = None,
        **kwargs,
    ) -> list[CanonicalSession]:
        """Le o dataset e devolve sessoes canonicas.

        `charge_point_serial` porque as 105 estacoes do dataset nao existem
        aqui: o dado real e reencenado no ponto do condominio. `shift_to`
        desloca a serie inteira para uma data recente, preservando os intervalos
        relativos -- 2014 nao serve para demonstrar operacao corrente.
        """
        df = pd.read_csv(path, sep="\t")
        if limit:
            df = df.head(limit)

        df["created"] = pd.to_datetime(df["created"])
        df["ended"] = pd.to_datetime(df["ended"])

        offset = timedelta(0)
        if shift_to:
            offset = pd.Timestamp(shift_to) - df["created"].min().normalize()

        out = []
        meter = Decimal("0.000")
        for row in df.itertuples(index=False):
            energy = Decimal(str(round(float(row.kwhTotal), 3)))
            meter_start = meter
            meter = meter + energy

            # pandas 3.0 mantem NaN em astype(str); por isso a checagem e feita
            # com isna() e nao comparando com a string "nan".
            platform = row.platform if not pd.isna(row.platform) else ""
            start = (row.created + offset).to_pydatetime().replace(tzinfo=self.tz)
            end = (row.ended + offset).to_pydatetime().replace(tzinfo=self.tz)

            out.append(
                CanonicalSession(
                    charge_point_serial=charge_point_serial,
                    auth_id=f"DS-{row.userId}",
                    auth_method="app" if "android" in str(platform).lower() or "ios" in str(platform).lower() else "rfid",
                    session_start=start,
                    session_end=end,
                    meter_start=meter_start,
                    meter_stop=meter,
                    energy_kwh=energy,
                    max_power_kw=None,
                    status="completed",
                    stop_reason="Local",
                    # Dado de nuvem do operador original -- sem lastro metrologico
                    # proprio, e o campo registra isso.
                    measurement_source=MeasurementSource.CLOUD,
                    source_ref=f"asensio:{row.sessionId}",
                )
            )
        return out
