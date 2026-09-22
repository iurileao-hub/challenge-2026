"""Adaptador do historico de sessoes do SEMS+ -- o primeiro dado REAL.

Ate aqui o projeto declarava um limite: nenhum evento de um HCA G2 de verdade
tinha atravessado o pipeline. Este adaptador o fecha, com o que a equipe tem.

O que e o dado. Em 26/06/2026 a GoodWe concedeu acesso de monitoramento a planta
"LAB FIAP Eco Smart Home". A tela "Registo de carregamento" do SEMS+ le o
endpoint `chargePile/queryChargeLogList`. Houve duas coletas:

- **26/06/2026, transcricao da tela.** 18 sessoes encerradas do carregador
  SN 57000HPA247L0002, de 31/05 a 25/06/2026, registradas em
  `docs/frente-2-sems-plus-acesso.md` e geradas em CSV por script
  (`data/semsplus_charge_log_2026-06.csv`, 136,66 kWh). Fica no repo como
  historico; este adaptador ainda o le, se receber o caminho.
- **22/09/2026, o JSON que a propria tela recebe.** 72 sessoes unicas, de
  27/05 a 22/09/2026, 570,17 kWh (`data/semsplus_charge_log.csv`, o padrao).
  As 18 da transcricao estao ali, sem nenhuma divergencia.

Honestidade sobre o nivel de evidencia: e a resposta do cliente web logado,
lida pela equipe, e nao chamada autenticada a API de desenvolvedor -- que segue
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
3. **Sessao de 0 kWh existe** (4 em 72 com 0,00 kWh, mais uma com 0,01; a da
   transcricao durou 37 minutos). Entra como veio.
4. **Energia com duas casas**, e nao tres. O esquema guarda tres; nada se perde.
5. **A fonte tem id de sessao** (`chargeSerialNumber`, o SN seguido de um
   carimbo de tempo). E a chave natural de idempotencia: reentregar a mesma
   pagina, ou paginas que se sobrepoem, nao duplica recarga.

O que o JSON traz e o adaptador NAO interpreta: `chargeEndCause` vale
"abnormal_stop" em todas as sessoes, inclusive recargas completas de horas, e
por isso nao distingue nada hoje; `greenElec` e `purElec` tem semantica
desconhecida (pergunta aberta a GoodWe, registrada na Frente 2). Ficam no
registro bruto, que o gateway guarda inteiro.
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
from ingestion.semsplus_raw import LOG_PATH, LOG_PATH_2026_06  # noqa: F401


class SemsPlusLogAdapter(SourceAdapter):
    name = "semsplus_log"
    mode = IngestionRun.Mode.FILE

    def __init__(self, tz: str = "America/Sao_Paulo"):
        super().__init__()
        # O SEMS+ escreve horario de parede da planta, sem fuso declarado.
        self.tz = ZoneInfo(tz)

    # O registro bruto chega em um de dois formatos: o do JSON (22/09) ou o da
    # transcricao da tela (26/06). O gateway guarda o bruto e o replay o
    # retraduz, entao os dois continuam legiveis.

    @staticmethod
    def _is_json_format(rec: dict) -> bool:
        return "chargeSerialNumber" in rec

    def _parse_dt(self, value: str) -> datetime:
        value = value.strip()
        fmt = "%Y-%m-%d %H:%M:%S.%f" if "-" in value else "%d/%m/%Y %H:%M:%S"
        return datetime.strptime(value, fmt).replace(tzinfo=self.tz)

    def _end_of(self, rec: dict) -> str:
        return rec["chargeEndTime"] if self._is_json_format(rec) else rec["fim"]

    def ref_of(self, raw: dict) -> str | None:
        if self._is_json_format(raw) and str(raw["chargeSerialNumber"]).strip():
            # Id de sessao da propria fonte.
            return f"semsplus:{str(raw['chargeSerialNumber']).strip()}"
        # A transcricao nao tinha id. Ponto + porta + inicio e o que o proprio
        # SEMS+ usa para distinguir duas sessoes no mesmo dia.
        return f"semsplus:{raw['sn']}:{raw['porta']}:{raw['inicio'].strip()}"

    def iter_raw(self, *, since: str | None = None, path: Path = LOG_PATH, **kwargs):
        corte = datetime.fromisoformat(since) if since else None
        maior = corte
        vistos: set[str] = set()
        with Path(path).open(newline="", encoding="utf-8") as f:
            for rec in csv.DictReader(f):
                ref = self._safe_ref(rec)
                if ref is not None:
                    if ref in vistos:
                        continue
                    vistos.add(ref)
                try:
                    fim = self._parse_dt(self._end_of(rec))
                except (KeyError, ValueError):
                    fim = None
                if corte and fim and fim <= corte:
                    continue
                if fim and (maior is None or fim > maior):
                    maior = fim
                yield rec
        self.cursor = maior.isoformat() if maior else since

    def to_canonical(self, rec: dict) -> CanonicalSession:
        if self._is_json_format(rec):
            # `str()`: do CSV tudo chega como texto; do JSON direto, numero.
            sn = str(rec["chargePileSN"]).strip()
            card = str(rec.get("chargeCardNumber") or "").strip()
            inicio, fim = str(rec["chargeStartTime"]), str(rec["chargeEndTime"])
            energia = str(rec["currentChargeQuantity"]).strip()
        else:
            sn = rec["sn"].strip()
            card = (rec.get("card_id") or "").strip()
            inicio, fim = rec["inicio"], rec["fim"]
            energia = rec["energia_kwh"].replace(",", ".").strip()
        return CanonicalSession(
            charge_point_serial=sn,
            # Cartao == numero de serie e auto-start: ninguem se identificou. O
            # `auth_id` bruto e preservado mesmo assim -- e o que o equipamento
            # disse, e a trilha de auditoria guarda o que ele disse.
            auth_id=card,
            auth_method="rfid",
            session_start=self._parse_dt(inicio),
            session_end=self._parse_dt(fim),
            energy_kwh=Decimal(energia),
            status="completed",
            # `chargeEndCause` nao entra: "abnormal_stop" em 100% das sessoes
            # nao e informacao, e traduzi-lo seria afirmar o que nao sabemos.
            stop_reason=None,
            measurement_source=MeasurementSource.CLOUD,
            source_ref=self.ref_of(rec),
        )

