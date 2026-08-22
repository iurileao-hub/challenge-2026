"""Calibracao do gerador sintetico no dado real de Asensio et al. (2021).

Fonte: Harvard Dataverse, doi:10.7910/DVN/QF1PMO, arquivo
`ev_workplace_charging_data.tab`, versao 4, licenca CC0 1.0 -- o deposito
**primario** do dataset que o enunciado sugeriu via Kaggle. 3.395 sessoes reais
de 85 usuarios em 105 estacoes, entre 18/11/2014 e 04/10/2015.

O que este modulo extrai do dado real, e o que deliberadamente NAO extrai:

**Vem do dado real** (e o que ha de transferivel entre um estacionamento de
trabalho americano e uma garagem de condominio brasileiro -- comportamento
humano, nao hardware):

- a *forma* da distribuicao de duracao de sessao (lognormal, ajustada por
  maxima verossimilhanca sobre o log);
- a *forma* da distribuicao de hora de inicio, espelhada em 12 horas: o
  workplace tem pico diurno (11h-13h, 16h-18h) porque as pessoas chegam ao
  trabalho; o condominio tem pico noturno pela razao simetrica. O espelhamento
  foi a decisao registrada na estrategia de dados da Sprint 1;
- a frequencia de sessoes por usuario e a dispersao entre usuarios.

**NAO vem do dado real, e o porque:** a energia por sessao. O dataset foi
coletado em carregadores cuja potencia media *implicita* e de 2,13 kW
(mediana), contra os 7 kW nominais do HCA G2 da FIAP; e as baterias de 2014-15
sao metade das atuais. Importar o kWh direto produziria sessoes de ~6 kWh, que
descrevem mal uma recarga noturna de condominio -- e mal o proprio mes ficticio
do dossie (18 a 40 kWh).

Por isso a energia e **derivada por fisica**, nao por amostragem: duracao
(forma real) x potencia efetiva do ponto (hardware real, com dispersao),
truncada pela capacidade da bateria do veiculo. E a composicao honesta: o dado
real responde "quanto tempo o carro fica plugado", o equipamento responde
"quanta energia entra nesse tempo".
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

DATASET_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "asensio_ev_workplace_charging.tab"
PARAMS_PATH = Path(__file__).resolve().parent / "calibration_params.json"

SOURCE = {
    "dataset": "High-resolution electric vehicle charging data from a workplace setting",
    "authors": "Asensio, O. I.; Lawson, M. C.; Apablaza, C. Z.",
    "doi": "10.7910/DVN/QF1PMO",
    "paper_doi": "10.1038/s41597-021-00956-1",
    "repository": "Harvard Dataverse (deposito primario)",
    "file": "ev_workplace_charging_data.tab (v4)",
    "license": "CC0 1.0",
}

#: Deslocamento do eixo horario: workplace diurno -> condominio noturno.
#:
#: A estrategia de dados da Sprint 1 pedia o eixo "espelhado". Ao derivar os
#: parametros, o espelho literal (+12 h) revelou um artefato: o dataset tem DOIS
#: picos -- 11h-13h (chegada ao trabalho) e 16h-18h (a saida, com troca de vaga
#: e sessoes curtas de topo). Deslocar tudo em 12 h joga o segundo pico para
#: 4h-6h da manha, e ninguem pluga o carro na garagem de casa as 5h.
#:
#: O espelhamento correto nao e do relogio, e do *evento*: o que o dataset
#: registra e "cheguei e pluguei", que no trabalho acontece as ~11h e em
#: condominio acontece na chegada em casa, ~20h. Alinhar os eventos da um
#: deslocamento de +9 h -- e ai o segundo pico cai em 1h-3h, que descreve bem
#: quem chega tarde. E a mesma transformacao, ancorada no comportamento em vez
#: de na aritmetica do relogio.
HOUR_SHIFT = 9


@dataclass
class CalibrationParams:
    """Parametros derivados do dado real, com a proveniencia junto."""

    n_sessions: int
    n_users: int
    period: str
    duration_log_mu: float
    duration_log_sigma: float
    duration_p05_hours: float
    duration_p95_hours: float
    hour_weights: list[float]
    sessions_per_user_month_mean: float
    sessions_per_user_month_sd: float
    weekday_weights: list[float]
    hour_shift: int = HOUR_SHIFT
    source: dict = field(default_factory=lambda: dict(SOURCE))
    note: str = (
        "Energia NAO e calibrada neste dataset (potencia media implicita de "
        "2,13 kW contra 7 kW do HCA G2): e derivada por fisica no gerador."
    )

    def save(self, path: Path = PARAMS_PATH) -> Path:
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n")
        return path

    @classmethod
    def load(cls, path: Path = PARAMS_PATH) -> "CalibrationParams":
        data = json.loads(path.read_text())
        data.pop("source", None)
        data.pop("note", None)
        return cls(**data)


def derive(dataset_path: Path = DATASET_PATH) -> CalibrationParams:
    """Le o dataset primario e devolve os parametros de calibracao."""
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"dataset nao encontrado em {dataset_path}. Reproduza com:\n"
            "  curl -sSL -o data/asensio_ev_workplace_charging.tab "
            "https://dataverse.harvard.edu/api/access/datafile/4491950"
        )

    df = pd.read_csv(dataset_path, sep="\t")
    df["created"] = pd.to_datetime(df["created"])

    # Sessoes de duracao implausivel saem da calibracao da forma: o maximo de
    # 55 h e cabo esquecido no fim de semana, nao recarga. Corte em 24 h.
    dur = df.loc[(df.chargeTimeHrs > 0.05) & (df.chargeTimeHrs <= 24), "chargeTimeHrs"]
    logd = np.log(dur.to_numpy())

    hours = df.created.dt.hour.to_numpy()
    counts = np.bincount(hours, minlength=24).astype(float)
    # A massa da hora h do workplace vai para (h + HOUR_SHIFT) % 24.
    mirrored = np.roll(counts, HOUR_SHIFT)
    hour_weights = (mirrored / mirrored.sum()).tolist()

    weekday = df.created.dt.weekday.to_numpy()
    wcounts = np.bincount(weekday, minlength=7).astype(float)
    weekday_weights = (wcounts / wcounts.sum()).tolist()

    per_user_month = (
        df.groupby([df.userId, df.created.dt.to_period("M")]).size().astype(float)
    )

    return CalibrationParams(
        n_sessions=int(len(df)),
        n_users=int(df.userId.nunique()),
        period=f"{df.created.min():%Y-%m-%d} a {df.created.max():%Y-%m-%d}",
        duration_log_mu=float(logd.mean()),
        duration_log_sigma=float(logd.std(ddof=1)),
        duration_p05_hours=float(np.percentile(dur, 5)),
        duration_p95_hours=float(np.percentile(dur, 95)),
        hour_weights=hour_weights,
        sessions_per_user_month_mean=float(per_user_month.mean()),
        sessions_per_user_month_sd=float(per_user_month.std(ddof=1)),
        weekday_weights=weekday_weights,
        hour_shift=HOUR_SHIFT,
    )


if __name__ == "__main__":
    params = derive()
    path = params.save()
    print(f"parametros derivados de {params.n_sessions} sessoes reais -> {path}")
    print(f"  duracao: lognormal(mu={params.duration_log_mu:.4f}, "
          f"sigma={params.duration_log_sigma:.4f}) "
          f"=> mediana {math.exp(params.duration_log_mu):.2f} h")
    print(f"  p05-p95: {params.duration_p05_hours:.2f} h a {params.duration_p95_hours:.2f} h")
    top = sorted(range(24), key=lambda h: -params.hour_weights[h])[:6]
    print(f"  horas de pico (ja espelhadas): {sorted(top)}")
    print(f"  sessoes/usuario/mes: {params.sessions_per_user_month_mean:.1f} "
          f"(dp {params.sessions_per_user_month_sd:.1f})")
