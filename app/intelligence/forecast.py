"""Previsao de demanda e ocupacao (Frente 3, Opcao B, abordagem 1).

Produz a curva de 7 dias e dois alertas operacionais. O que a torna estrutural
e o que ela habilita, nao o grafico: janela de reserva antes do conflito,
proposta de segundo ponto com payback derivado da propria curva, e o anexo de
curva de carga que a IT-41 exige na renovacao do AVCB.

**Escolha de modelo, e por que nao algo maior.** Gradient boosting sobre
features de calendario, treinado sobre agregados diarios. Um condominio gera
algumas centenas de sessoes por ano: e regime de dado pequeno e tabular, onde
arvores batem rede neural com folga e sem GPU. E ha um criterio que nao e
tecnico e pesa igual: previsao que o sindico nao consegue explicar em
assembleia nao embasa decisao nenhuma. Por isso o modelo vem acompanhado de
**backtest declarado** -- a curva sai com o erro medio que ela teve no passado
recente, e nao como numero sem procedencia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd
from django.db.models import Max

from billing.competence import condo_tz
from core.models import ChargingSession, TelemetryReading

HORIZON_DAYS = 7
MIN_DAYS_TO_TRAIN = 30
BACKTEST_DAYS = 14


@dataclass
class DayForecast:
    day: date
    predicted_kwh: float
    predicted_sessions: float


@dataclass
class Alert:
    kind: str          # 'saturation' | 'power_limit'
    severity: str      # 'info' | 'warning' | 'critical'
    message: str
    day: date | None = None


@dataclass
class ForecastResult:
    days: list[DayForecast] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    backtest_mae_kwh: float | None = None
    baseline_mae_kwh: float | None = None
    trained_on_days: int = 0
    method: str = ""
    chosen_model: str = ""

    @property
    def total_predicted_kwh(self) -> float:
        return sum(d.predicted_kwh for d in self.days)

    @property
    def beats_baseline(self) -> bool | None:
        """O modelo ganha da media por dia da semana?

        Vale a pena declarar: se um gradient boosting nao bate a media simples,
        ele nao esta ganhando nada e so adiciona opacidade.
        """
        if self.backtest_mae_kwh is None or self.baseline_mae_kwh is None:
            return None
        return self.backtest_mae_kwh < self.baseline_mae_kwh


def daily_series(condominium, until: date) -> pd.DataFrame:
    """Serie diaria de kWh e sessoes, no fuso do condominio."""
    tz = condo_tz()
    sessions = ChargingSession.objects.filter(
        charge_point__condominium=condominium,
        session_start__lte=datetime.combine(until, time.max, tzinfo=tz),
    ).values_list("session_start", "energy_kwh")

    rows = [
        {"day": s.astimezone(tz).date(), "kwh": float(e)}
        for s, e in sessions
    ]
    if not rows:
        return pd.DataFrame(columns=["day", "kwh", "sessions"])

    df = pd.DataFrame(rows)
    agg = df.groupby("day").agg(kwh=("kwh", "sum"), sessions=("kwh", "size")).reset_index()
    # Dias sem sessao sao zeros, nao lacunas: a ausencia de recarga e informacao.
    full = pd.DataFrame({"day": pd.date_range(agg.day.min(), until, freq="D").date})
    return full.merge(agg, on="day", how="left").fillna({"kwh": 0.0, "sessions": 0})


def _calendar_features(days: pd.Series, origin: date) -> np.ndarray:
    d = pd.to_datetime(pd.Series(list(days)))
    return np.column_stack([
        d.dt.weekday.to_numpy(),
        d.dt.day.to_numpy(),
        (d.dt.weekday >= 5).astype(int).to_numpy(),
        np.array([(x.date() - origin).days for x in d]),   # tendencia
    ])


def forecast(condominium, *, today: date, horizon: int = HORIZON_DAYS) -> ForecastResult:
    """Curva de `horizon` dias a frente, com backtest e alertas."""
    from sklearn.ensemble import GradientBoostingRegressor

    series = daily_series(condominium, today)
    result = ForecastResult(trained_on_days=len(series))

    if len(series) < MIN_DAYS_TO_TRAIN:
        # Sem historico, media simples e declarada como tal -- o cold start que
        # a Opcao B previu, resolvido por honestidade e nao por extrapolacao.
        media = float(series.kwh.mean()) if len(series) else 0.0
        result.method = f"media historica ({len(series)} dias -- insuficiente para treinar)"
        result.days = [
            DayForecast(today + timedelta(days=i + 1), media, 0.0) for i in range(horizon)
        ]
        return result

    origin = series.day.min()
    X = _calendar_features(series.day, origin)
    y = series.kwh.to_numpy(dtype=float)

    # Backtest: treina no passado, mede nos ultimos BACKTEST_DAYS dias.
    if len(series) > MIN_DAYS_TO_TRAIN + BACKTEST_DAYS:
        cut = len(series) - BACKTEST_DAYS
        model_bt = GradientBoostingRegressor(random_state=20260831, n_estimators=200, max_depth=3)
        model_bt.fit(X[:cut], y[:cut])
        pred = model_bt.predict(X[cut:])
        result.backtest_mae_kwh = float(np.mean(np.abs(pred - y[cut:])))

        # Baseline: media por dia da semana, calculada so com o passado.
        train = series.iloc[:cut]
        by_wd = train.assign(wd=pd.to_datetime(train.day).dt.weekday).groupby("wd").kwh.mean()
        base_pred = np.array([
            by_wd.get(pd.Timestamp(d).weekday(), train.kwh.mean()) for d in series.day[cut:]
        ])
        result.baseline_mae_kwh = float(np.mean(np.abs(base_pred - y[cut:])))

    future_days = [today + timedelta(days=i + 1) for i in range(horizon)]
    Xf = _calendar_features(pd.Series(future_days), origin)

    # A escolha do modelo e feita por medicao, nao por preferencia.
    #
    # Se o gradient boosting nao bate a media por dia da semana no backtest, ele
    # nao esta agregando nada -- so opacidade. Nesse caso a plataforma serve o
    # baseline e DIZ que serviu o baseline. Um sindico que pergunta "de onde vem
    # esse numero?" merece uma resposta melhor que "o modelo disse".
    use_gb = result.beats_baseline is not False

    if use_gb:
        model = GradientBoostingRegressor(random_state=20260831, n_estimators=200, max_depth=3)
        model.fit(X, y)
        preds = np.clip(model.predict(Xf), 0.0, None)

        sessions_model = GradientBoostingRegressor(random_state=20260831, n_estimators=120, max_depth=3)
        sessions_model.fit(X, series.sessions.to_numpy(dtype=float))
        sess_preds = np.clip(sessions_model.predict(Xf), 0.0, None)

        result.chosen_model = "gradient_boosting"
        result.method = (
            "gradient boosting sobre features de calendario (dia da semana, dia do "
            "mes, fim de semana, tendencia)"
        )
    else:
        wd = pd.to_datetime(series.day).dt.weekday
        media_kwh = series.assign(wd=wd).groupby("wd").kwh.mean()
        media_sess = series.assign(wd=wd).groupby("wd").sessions.mean()
        preds = np.array([media_kwh.get(d.weekday(), float(series.kwh.mean())) for d in future_days])
        sess_preds = np.array([media_sess.get(d.weekday(), float(series.sessions.mean())) for d in future_days])

        result.chosen_model = "baseline_sazonal"
        result.method = (
            "media historica por dia da semana -- o gradient boosting foi treinado "
            "e REPROVADO no backtest (erro maior que o da media), entao nao e usado"
        )
    result.days = [
        DayForecast(d, float(k), float(s)) for d, k, s in zip(future_days, preds, sess_preds)
    ]
    result.alerts = build_alerts(condominium, result, series)
    return result


def build_alerts(condominium, result: ForecastResult, series: pd.DataFrame) -> list[Alert]:
    """Os dois alertas da Opcao B: saturacao e limite de potencia."""
    alerts: list[Alert] = []
    points = list(condominium.charge_points.all())
    if not points:
        return alerts

    # --- saturacao: horas-ponto disponiveis por dia vs. horas demandadas ---
    capacity_kwh_day = sum(float(p.rated_power_kw) for p in points) * 24 * 0.8
    for d in result.days:
        if capacity_kwh_day and d.predicted_kwh > capacity_kwh_day * 0.85:
            alerts.append(Alert(
                kind="saturation", severity="critical", day=d.day,
                message=(
                    f"Demanda prevista para {d.day:%d/%m} ({d.predicted_kwh:.0f} kWh) "
                    f"chega a {d.predicted_kwh / capacity_kwh_day:.0%} da capacidade "
                    f"pratica do(s) {len(points)} ponto(s). Conflito de fila provavel: "
                    "abrir janelas de reserva ou avaliar segundo ponto."
                ),
            ))
        elif capacity_kwh_day and d.predicted_kwh > capacity_kwh_day * 0.65:
            alerts.append(Alert(
                kind="saturation", severity="warning", day=d.day,
                message=(
                    f"Demanda prevista para {d.day:%d/%m} ({d.predicted_kwh:.0f} kWh) "
                    f"em {d.predicted_kwh / capacity_kwh_day:.0%} da capacidade pratica."
                ),
            ))

    # --- limite de potencia declarada (Lei 18.403 / IT-41) ---
    declared = float(condominium.declared_power_kw or 0)
    if declared > 0:
        observed_peak = (
            TelemetryReading.objects.filter(charge_point__condominium=condominium)
            .aggregate(peak=Max("power_kw"))["peak"]
        )
        peak = float(observed_peak or 0)
        installed = sum(float(p.rated_power_kw) for p in points)
        if installed > declared:
            alerts.append(Alert(
                kind="power_limit", severity="critical",
                message=(
                    f"Potencia instalada ({installed:.1f} kW) excede a declarada na "
                    f"instalacao ({declared:.1f} kW). Regularizar antes da renovacao do "
                    "AVCB -- a IT-41 exige estudo de demanda por profissional habilitado."
                ),
            ))
        elif peak > declared * 0.85:
            alerts.append(Alert(
                kind="power_limit", severity="warning",
                message=(
                    f"Pico de potencia observado ({peak:.1f} kW) em "
                    f"{peak / declared:.0%} da potencia declarada ({declared:.1f} kW). "
                    "Um ponto adicional exigiria revisao do estudo de demanda."
                ),
            ))
    return alerts
