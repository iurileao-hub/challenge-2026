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
        super().__init__()
        self.tz = ZoneInfo(tz)

    def ref_of(self, raw: dict) -> str | None:
        return f"asensio:{raw['sessionId']}"

    def iter_raw(
        self,
        *,
        since: str | None = None,
        charge_point_serial: str,
        path: Path = DATASET_PATH,
        limit: int | None = None,
        shift_to: str | None = None,
        **kwargs,
    ):
        """Le o dataset e devolve uma linha por sessao, ja reencenada.

        `charge_point_serial` porque as 105 estacoes do dataset nao existem
        aqui: o dado real e reencenado no ponto do condominio. `shift_to`
        desloca a serie inteira para uma data recente, preservando os intervalos
        relativos -- 2014 nao serve para demonstrar operacao corrente.

        A reencenacao serializa as sessoes no conector: no dataset elas vem de
        105 estacoes e se sobrepoem livremente; num cabo so, a seguinte comeca
        quando a anterior termina. O medidor acumulado e reconstruido na mesma
        passada, porque o dataset so traz a energia de cada sessao.
        """
        df = pd.read_csv(path, sep="\t")
        if limit:
            df = df.head(limit)

        df["created"] = pd.to_datetime(df["created"])
        df["ended"] = pd.to_datetime(df["ended"])
        df = df.sort_values("created")

        offset = timedelta(0)
        if shift_to:
            offset = pd.Timestamp(shift_to) - df["created"].min().normalize()

        meter = Decimal("0.000")
        livre_em = None
        for row in df.itertuples(index=False):
            rec = row._asdict()
            energy = Decimal(str(round(float(row.kwhTotal), 3)))
            start = (row.created + offset).to_pydatetime().replace(tzinfo=self.tz)
            end = (row.ended + offset).to_pydatetime().replace(tzinfo=self.tz)
            if livre_em is not None and start < livre_em:
                atraso = livre_em - start + timedelta(minutes=5)
                start, end = start + atraso, end + atraso
            livre_em = max(end, start)
            rec.update(
                _serial=charge_point_serial, _start=start, _end=max(end, start),
                _meter_start=meter, _meter_stop=meter + energy, _energy=energy,
            )
            meter += energy
            yield rec

    def to_canonical(self, rec: dict) -> CanonicalSession:
        # pandas 3.0 mantem NaN em astype(str); por isso a checagem e feita
        # com isna() e nao comparando com a string "nan".
        platform = rec["platform"] if not pd.isna(rec["platform"]) else ""
        via_app = "android" in str(platform).lower() or "ios" in str(platform).lower()
        return CanonicalSession(
            charge_point_serial=rec["_serial"],
            auth_id=f"DS-{rec['userId']}",
            auth_method="app" if via_app else "rfid",
            session_start=rec["_start"],
            session_end=rec["_end"],
            meter_start=rec["_meter_start"],
            meter_stop=rec["_meter_stop"],
            energy_kwh=rec["_energy"],
            max_power_kw=None,
            status="completed",
            stop_reason="Local",
            # Dado de nuvem do operador original -- sem lastro metrologico
            # proprio, e o campo registra isso.
            measurement_source=MeasurementSource.CLOUD,
            source_ref=self.ref_of(rec),
        )
