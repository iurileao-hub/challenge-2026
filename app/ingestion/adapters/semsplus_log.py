"""Adaptador do historico de sessoes do SEMS+ -- o primeiro dado REAL.

Ate aqui o projeto declarava um limite: nenhum evento de um HCA G2 de verdade
tinha atravessado o pipeline. Este adaptador o fecha, com o que a equipe tem.

O que e o dado. Em 26/06/2026 a GoodWe concedeu acesso de monitoramento a planta
"LAB FIAP Eco Smart Home". A tela "Registo de carregamento" do SEMS+ (endpoint
`chargePile/queryChargeLogList`) listou 18 sessoes encerradas do carregador
SN 57000HPA247L0002, de 31/05 a 25/06/2026. A equipe as registrou na integra em
`docs/frente-2-sems-plus-acesso.md`; o CSV em `data/` e essa mesma tabela, gerada
por script a partir do documento (total conferido: 136,66 kWh).

Honestidade sobre o nivel de evidencia: e observacao de primeira mao da TELA
(nivel [O] da Frente 2), nao resposta de chamada autenticada a API -- que segue
negada. Os numeros sao reais; o formato de transporte ainda nao e o definitivo.
Por isso `iter_raw` (de onde vem) e `to_canonical` (o que significa) estao
separados: no dia da API, troca-se o primeiro.

O que o dado real ensinou, e que dado sintetico nenhum ensinaria:

1. **A fonte nao reporta medidor acumulado.** So inicio, fim e energia. O modelo
   canonico exigia `meter_start`; era premissa nossa. Virou opcional.
2. **Todas as sessoes chegam sem dono.** O "ID do cartao" e o proprio numero de
   serie: assinatura de auto-start, partida sem cartao. Entram como sessoes
   orfas -- energia que o condominio pagou e ninguem ressarciu. E o problema
   que justifica a plataforma, medido no equipamento do proprio laboratorio.
3. **Sessao de 0 kWh existe** (#8, 37 minutos). Entra como veio.
4. **Energia com duas casas**, e nao tres. O esquema guarda tres; nada se perde.
"""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from core.models import MeasurementSource
from ingestion.gateway import CanonicalSession, SourceAdapter
from ingestion.models import IngestionRun

LOG_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data" / "semsplus_charge_log_2026-06.csv"
)


class SemsPlusLogAdapter(SourceAdapter):
    name = "semsplus_log"
    mode = IngestionRun.Mode.FILE

    def __init__(self, tz: str = "America/Sao_Paulo"):
        super().__init__()
        # A tela do SEMS+ mostra horario de parede da planta.
        self.tz = ZoneInfo(tz)

    def _parse_dt(self, value: str) -> datetime:
        return datetime.strptime(value.strip(), "%d/%m/%Y %H:%M:%S").replace(tzinfo=self.tz)

    def ref_of(self, raw: dict) -> str | None:
        # O log nao expoe id de sessao. Ponto + porta + inicio e o que o
        # proprio SEMS+ usa para distinguir duas sessoes no mesmo dia.
        return f"semsplus:{raw['sn']}:{raw['porta']}:{raw['inicio'].strip()}"

    def iter_raw(self, *, since: str | None = None, path: Path = LOG_PATH, **kwargs):
        corte = datetime.fromisoformat(since) if since else None
        maior = corte
        with Path(path).open(newline="", encoding="utf-8") as f:
            for rec in csv.DictReader(f):
                try:
                    fim = self._parse_dt(rec["fim"])
                except (KeyError, ValueError):
                    fim = None
                if corte and fim and fim <= corte:
                    continue
                if fim and (maior is None or fim > maior):
                    maior = fim
                yield rec
        self.cursor = maior.isoformat() if maior else since

    def to_canonical(self, rec: dict) -> CanonicalSession:
        sn = rec["sn"].strip()
        card = (rec.get("card_id") or "").strip()
        return CanonicalSession(
            charge_point_serial=sn,
            # Cartao == numero de serie e auto-start: ninguem se identificou. O
            # `auth_id` bruto e preservado mesmo assim -- e o que o equipamento
            # disse, e a trilha de auditoria guarda o que ele disse.
            auth_id=card,
            auth_method="rfid",
            session_start=self._parse_dt(rec["inicio"]),
            session_end=self._parse_dt(rec["fim"]),
            energy_kwh=Decimal(rec["energia_kwh"].replace(",", ".")),
            status="completed",
            stop_reason=None,
            measurement_source=MeasurementSource.CLOUD,
            source_ref=self.ref_of(rec),
        )
