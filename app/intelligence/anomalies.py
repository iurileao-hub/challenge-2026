"""Deteccao de anomalias em duas fases (Frente 3, Opcao B, abordagem 3).

**Fase 1 -- regras estatisticas interpretaveis.** Rodam desde o primeiro dia,
sem treino e sem historico. Cada uma produz uma explicacao que o sindico le em
voz alta na assembleia e o morador confere no proprio extrato. E deliberado:
uma flag que ninguem consegue explicar nao sustenta uma cobranca.

**Fase 2 -- Isolation Forest.** Entra quando ha historico, para pegar o que as
regras nao anteciparam: combinacoes atipicas de features que nenhuma regra
isolada cruzaria. Nao substitui a fase 1; complementa. E quando aponta, aponta
com as features que mais destoaram, para continuar explicavel.

A posicao no fluxo e o que torna esta IA estrutural em vez de decorativa: a
deteccao roda **antes do fechamento da fatura**, e a linha suspeita entra na
fatura marcada para auditoria (`invoice_line.flagged_for_audit`), levando a
fatura para `under_review`. Remover a deteccao nao apagaria um grafico -- ela
quebraria o ciclo de estados da fatura.

Nenhuma flag dispara punicao automatica. A IA produz evidencia; o humano decide.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
from django.db.models import Count, Q

from core.models import AnomalyFlag, ChargePoint, ChargingSession, TelemetryReading
from intelligence.features import SessionFeatures, extract, to_frame

# Limiares da fase 1. Ficam explicitos aqui, e nao espalhados no codigo, porque
# sao parametro de politica do condominio -- o sindico pode querer mexer.
IDLE_HOURS_THRESHOLD = 4.0
CONSUMPTION_VS_MEDIAN = 3.0
POWER_DEGRADATION_RATIO = 0.6
HEARTBEAT_GAP_HOURS = 3.0
MIN_HISTORY_FOR_MEDIAN = 5


@dataclass
class Detection:
    session_id: int | None
    charge_point_id: int | None
    category: str
    explanation: str
    detector: str = "rule"
    score: float | None = None


# --------------------------------------------------------------------------
# Fase 1 -- regras
# --------------------------------------------------------------------------

def _rule_impossible_energy(f: SessionFeatures) -> Detection | None:
    """Energia acima da capacidade da bateria. Nao e consumo alto: e
    impossivel -- logo, medicao errada ou desvio."""
    if f.battery_capacity_kwh > 0 and f.energy_over_battery > 1.0:
        return Detection(
            session_id=f.session_id, charge_point_id=None, category="consumption",
            explanation=(
                f"Sessao registrou {f.energy_kwh:.1f} kWh, {f.energy_over_battery:.0%} "
                f"da capacidade da bateria cadastrada ({f.battery_capacity_kwh:.0f} kWh). "
                "Acima de 100% e fisicamente impossivel numa unica recarga: "
                "verificar medicao ou cadastro do veiculo."
            ),
        )
    return None


def _rule_consumption_outlier(f: SessionFeatures, median: float | None) -> Detection | None:
    """Consumo muito acima do padrao da propria credencial -- a comparacao e
    com o historico de quem carregou, nao com uma media global do predio."""
    if median and median > 0 and f.energy_kwh > median * CONSUMPTION_VS_MEDIAN:
        return Detection(
            session_id=f.session_id, charge_point_id=None, category="consumption",
            explanation=(
                f"Consumo de {f.energy_kwh:.1f} kWh e {f.energy_kwh / median:.1f}x a "
                f"mediana historica desta credencial ({median:.1f} kWh)."
            ),
        )
    return None


def _rule_idle(f: SessionFeatures) -> Detection | None:
    """Vaga ocupada sem entregar energia -- o carro-tampao da Frente 1."""
    if f.idle_hours >= IDLE_HOURS_THRESHOLD:
        return Detection(
            session_id=f.session_id, charge_point_id=None, category="idle",
            explanation=(
                f"Veiculo permaneceu {f.idle_hours:.1f} h conectado apos concluir a "
                f"recarga (carregou {f.charging_hours:.1f} h de {f.plugged_hours:.1f} h "
                "plugado). A vaga ficou indisponivel sem entregar energia."
            ),
        )
    return None


def _rule_power_degradation(f: SessionFeatures) -> Detection | None:
    """O caso Copel: o ponto entrega menos do que promete, silenciosamente."""
    if f.second_half_power_ratio < POWER_DEGRADATION_RATIO:
        return Detection(
            session_id=f.session_id, charge_point_id=None, category="power_degradation",
            explanation=(
                f"Potencia da segunda metade da sessao caiu para "
                f"{f.second_half_power_ratio:.0%} da primeira. Sinal de degradacao "
                "de cabo, conector ou contator -- manutencao preventiva antes que "
                "vire falha."
            ),
        )
    return None


def _rule_metering(f: SessionFeatures, session: ChargingSession) -> Detection | None:
    """Leitura final perdida ou medidor inconsistente."""
    if session.meter_stop is None:
        return Detection(
            session_id=f.session_id, charge_point_id=None, category="metering",
            explanation=(
                "Leitura final do medidor nao chegou. A cobranca usou a ultima "
                f"leitura periodica conhecida ({f.energy_kwh:.3f} kWh) -- sempre o "
                "valor mais conservador, nunca estimativa para cima."
            ),
        )
    if not f.meter_consistent:
        return Detection(
            session_id=f.session_id, charge_point_id=None, category="metering",
            explanation=(
                "Energia registrada na sessao nao confere com a diferenca das "
                "leituras do medidor. Divergencia acima da tolerancia de 0,05 kWh."
            ),
        )
    return None


def detect_point_health(condominium, since, until) -> list[Detection]:
    """Saude do ponto -- a anomalia que nao mora em sessao nenhuma.

    O sinal e a AUSENCIA de heartbeat. Por isso a telemetria precisa existir
    fora de sessao: um ponto morto nao gera sessao para reclamar por ele.
    """
    out = []
    for point in ChargePoint.objects.filter(condominium=condominium):
        beats = list(
            TelemetryReading.objects.filter(
                charge_point=point, kind=TelemetryReading.Kind.HEARTBEAT,
                ts__gte=since, ts__lte=until,
            ).order_by("ts").values_list("ts", flat=True)
        )
        if len(beats) < 2:
            continue
        worst, worst_at = timedelta(0), None
        for a, b in zip(beats, beats[1:]):
            gap = b - a
            if gap > worst:
                worst, worst_at = gap, a
        if worst.total_seconds() / 3600 >= HEARTBEAT_GAP_HOURS:
            from billing.competence import condo_tz
            local = worst_at.astimezone(condo_tz())
            out.append(
                Detection(
                    session_id=None, charge_point_id=point.id, category="health",
                    explanation=(
                        f"Ponto {point.serial_number} ficou "
                        f"{worst.total_seconds() / 3600:.1f} h sem comunicar a partir "
                        f"de {local:%d/%m %H:%M}. Indisponibilidade nao percebida pelo "
                        "morador ate tentar usar."
                    ),
                )
            )
    return out


# --------------------------------------------------------------------------
# Fase 2 -- Isolation Forest
# --------------------------------------------------------------------------

ISOLATION_FEATURES = [
    "energy_kwh", "plugged_hours", "charging_hours", "idle_hours",
    "kwh_per_hour", "power_ratio", "second_half_power_ratio", "start_hour",
]


def detect_isolation_forest(features: list[SessionFeatures], contamination: float = 0.05):
    """Isolation Forest sobre as features da sessao.

    Escolhido em vez de um autoencoder ou de um modelo profundo por tres
    razoes praticas, nao ideologicas: funciona bem com poucas centenas de
    amostras (que e a escala de um condominio), nao precisa de GPU, e a
    contribuicao de cada feature ao escore e inspecionavel -- o que permite
    dizer *o que* destoou, e nao apenas que algo destoou.
    """
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    if len(features) < 30:
        return []

    df = to_frame(features)
    X = df[ISOLATION_FEATURES].fillna(0.0).to_numpy(dtype=float)
    Xs = StandardScaler().fit_transform(X)

    model = IsolationForest(
        n_estimators=200, contamination=contamination, random_state=20260831, n_jobs=1
    )
    labels = model.fit_predict(Xs)
    scores = model.score_samples(Xs)

    out = []
    mean, std = Xs.mean(axis=0), Xs.std(axis=0)
    for i, label in enumerate(labels):
        if label != -1:
            continue
        # Quais features mais destoaram desta amostra -- o "porque" da flag.
        z = np.abs(Xs[i] - mean) / np.where(std > 0, std, 1)
        top = np.argsort(-z)[:2]
        motivos = ", ".join(
            f"{ISOLATION_FEATURES[j]}={df.iloc[i][ISOLATION_FEATURES[j]]:.2f} "
            f"({z[j]:.1f} desvios da media)" for j in top
        )
        out.append(
            Detection(
                session_id=int(df.iloc[i]["session_id"]),
                charge_point_id=None,
                category="consumption",
                explanation=(
                    f"Combinacao atipica de caracteristicas nesta sessao: {motivos}. "
                    "Detectada por Isolation Forest sobre o historico do condominio."
                ),
                detector="isolation_forest",
                score=float(scores[i]),
            )
        )
    return out


# --------------------------------------------------------------------------
# Orquestracao
# --------------------------------------------------------------------------

def run_detection(condominium, since, until, *, use_isolation_forest: bool = True) -> list[AnomalyFlag]:
    """Roda as duas fases sobre o periodo e persiste as flags novas.

    Idempotente: uma sessao ja sinalizada na mesma categoria nao gera flag
    duplicada, para que reprocessar o mes nao inunde a fila do sindico.
    """
    sessions = list(
        ChargingSession.objects.filter(
            charge_point__condominium=condominium,
            session_start__gte=since,
            session_start__lte=until,
        ).select_related("credential__user__unit", "charge_point")
        .prefetch_related("credential__user__vehicles")
    )
    feats = extract(sessions)
    by_id = {s.id: s for s in sessions}

    # Mediana historica por credencial -- base da regra de consumo atipico.
    medians: dict[int, float] = {}
    grouped: dict[int, list[float]] = {}
    for f in feats:
        if f.credential_id:
            grouped.setdefault(f.credential_id, []).append(f.energy_kwh)
    for cred_id, values in grouped.items():
        if len(values) >= MIN_HISTORY_FOR_MEDIAN:
            medians[cred_id] = statistics.median(values)

    detections: list[Detection] = []
    for f in feats:
        session = by_id[f.session_id]
        for det in (
            _rule_impossible_energy(f),
            _rule_consumption_outlier(f, medians.get(f.credential_id)),
            _rule_idle(f),
            _rule_power_degradation(f),
            _rule_metering(f, session),
        ):
            if det:
                detections.append(det)

    detections.extend(detect_point_health(condominium, since, until))

    if use_isolation_forest:
        ja_marcadas = {d.session_id for d in detections}
        detections.extend(
            d for d in detect_isolation_forest(feats) if d.session_id not in ja_marcadas
        )

    existentes = {
        (f.session_id, f.charge_point_id, f.category)
        for f in AnomalyFlag.objects.filter(
            Q(session__in=[s.id for s in sessions])
            | Q(charge_point__condominium=condominium)
        )
    }
    novas = [
        AnomalyFlag(
            session_id=d.session_id,
            charge_point_id=d.charge_point_id,
            category=d.category,
            explanation=d.explanation,
            detector=d.detector,
            score=d.score,
            status=AnomalyFlag.Status.OPEN,
        )
        for d in detections
        if (d.session_id, d.charge_point_id, d.category) not in existentes
    ]
    return AnomalyFlag.objects.bulk_create(novas)
