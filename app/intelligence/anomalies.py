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
#: Quanto passado entra como CONTEXTO da janela analisada. "Consumo atipico para
#: esta credencial" so tem sentido contra o historico dela -- e um mes isolado
#: raramente tem as 5 sessoes por credencial (ou as 30 do Isolation Forest) que
#: a comparacao exige. Sem isto, no mes da demonstracao a fase 2 nunca rodava.
HISTORY_DAYS = 180


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
                f"Sessão registrou {f.energy_kwh:.1f} kWh, {f.energy_over_battery:.0%} "
                f"da capacidade da bateria cadastrada ({f.battery_capacity_kwh:.0f} kWh). "
                "Acima de 100% é fisicamente impossível numa única recarga: "
                "verificar medição ou cadastro do veículo."
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
                f"Consumo de {f.energy_kwh:.1f} kWh é {f.energy_kwh / median:.1f}x a "
                f"mediana histórica desta credencial ({median:.1f} kWh)."
            ),
        )
    return None


def _rule_idle(f: SessionFeatures) -> Detection | None:
    """Vaga ocupada sem entregar energia -- o carro-tampao da Frente 1.

    Exige telemetria. Sem MeterValues nao se sabe QUANDO a recarga terminou, e
    a regra se cala: acusar por falta de dado seria punir o morador pelo
    silencio do equipamento.
    """
    if not f.has_telemetry:
        return None
    if f.idle_hours >= IDLE_HOURS_THRESHOLD:
        return Detection(
            session_id=f.session_id, charge_point_id=None, category="idle",
            explanation=(
                f"Veículo permaneceu {f.idle_hours:.1f} h conectado após concluir a "
                f"recarga (carregou {f.charging_hours:.1f} h de {f.plugged_hours:.1f} h "
                "plugado). A vaga ficou indisponível sem entregar energia."
            ),
        )
    return None


def _rule_power_degradation(f: SessionFeatures) -> Detection | None:
    """O caso Copel: o ponto entrega menos do que promete, silenciosamente."""
    if f.second_half_power_ratio < POWER_DEGRADATION_RATIO:
        return Detection(
            session_id=f.session_id, charge_point_id=None, category="power_degradation",
            explanation=(
                f"Potência da segunda metade da sessão caiu para "
                f"{f.second_half_power_ratio:.0%} da primeira. Sinal de degradação "
                "de cabo, conector ou contator — manutenção preventiva antes que "
                "vire falha."
            ),
        )
    return None


def _rule_metering(f: SessionFeatures, session: ChargingSession) -> Detection | None:
    """Leitura final perdida ou medidor inconsistente."""
    if session.final_reading_lost:
        return Detection(
            session_id=f.session_id, charge_point_id=None, category="metering",
            explanation=(
                "Leitura final do medidor não chegou. A cobrança usou a última "
                f"leitura periódica conhecida ({f.energy_kwh:.3f} kWh) — sempre o "
                "valor mais conservador, nunca estimativa para cima."
            ),
        )
    if not f.meter_consistent:
        return Detection(
            session_id=f.session_id, charge_point_id=None, category="metering",
            explanation=(
                "Energia registrada na sessão não confere com a diferença das "
                "leituras do medidor. Divergência acima da tolerância de 0,05 kWh."
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
                        f"de {local:%d/%m %H:%M}. Indisponibilidade não percebida pelo "
                        "morador até tentar usar."
                    ),
                )
            )
    return out


# --------------------------------------------------------------------------
# Fase 2 -- Isolation Forest
# --------------------------------------------------------------------------

ISOLATION_FEATURES = [
    "energy_kwh", "plugged_hours", "charging_hours", "idle_hours",
    "kwh_per_hour", "power_ratio", "second_half_power_ratio",
    "start_hour_sin", "start_hour_cos",
]

#: Como cada caracteristica aparece para quem le a fila: (rotulo, unidade,
#: categoria da anomalia). Nome de coluna na tela do sindico e codigo vazando.
FEATURE_LEGIVEL = {
    "energy_kwh": ("energia da recarga", "kWh", "consumption"),
    "plugged_hours": ("tempo conectado", "h", "idle"),
    "charging_hours": ("tempo carregando", "h", "consumption"),
    "idle_hours": ("tempo conectado sem carregar", "h", "idle"),
    "kwh_per_hour": ("energia por hora conectado", "kWh/h", "consumption"),
    "power_ratio": ("potência em relação à nominal do ponto", "×", "power_degradation"),
    "second_half_power_ratio": ("potência da 2ª metade em relação à 1ª", "×", "power_degradation"),
    "start_hour_sin": ("horário de início", "", "consumption"),
    "start_hour_cos": ("horário de início", "", "consumption"),
}


def detect_isolation_forest(features: list[SessionFeatures], only_ids: set[int] | None = None):
    """Isolation Forest sobre as features da sessao.

    Escolhido em vez de um autoencoder ou de um modelo profundo por tres
    razoes praticas, nao ideologicas: funciona bem com poucas centenas de
    amostras (que e a escala de um condominio), nao precisa de GPU, e a
    contribuicao de cada feature ao escore e inspecionavel -- o que permite
    dizer *o que* destoou, e nao apenas que algo destoou.

    Tres decisoes que a primeira versao errava:

    - **Limiar por escore, nao por cota.** `contamination=0.05` manda o modelo
      rotular os 5% mais estranhos, EXISTAM ou nao anomalias: com 30 sessoes no
      mes, sempre havia fatura retida, por construcao. `"auto"` usa o limiar do
      artigo original (escore < -0,5): so sinaliza o que de fato se isola.
    - **Hora do dia e circular.** 23h e 0h sao vizinhas; como numero, sao os
      extremos. Entra como seno e cosseno.
    - **Treina no historico, sinaliza a janela.** `only_ids` restringe a SAIDA;
      o ajuste usa tudo o que foi passado.
    """
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    # Sem telemetria, cinco das nove caracteristicas sao DESCONHECIDAS -- e
    # desconhecido nao e zero. A primeira rodada com dado real mostrou o custo
    # de confundir os dois: o historico do SEMS+ nao traz potencia, o codigo
    # preenchia 0,0, e 17 das 18 recargas reais foram acusadas de "potencia
    # zero". Vale aqui o que ja valia para a regra de ociosidade: sem base, o
    # detector se abstem. Nao treina nessas sessoes nem as julga.
    features = [f for f in features if f.has_telemetry]
    if len(features) < 30:
        return []

    df = to_frame(features)
    ang = 2 * np.pi * df["start_hour"].astype(float) / 24.0
    df["start_hour_sin"], df["start_hour_cos"] = np.sin(ang), np.cos(ang)
    # Lacuna pontual (ex.: potencia maxima nao informada) entra como a MEDIANA
    # da coluna: valor neutro, que nao puxa a amostra para longe das outras.
    base = df[ISOLATION_FEATURES].astype(float)
    X = base.fillna(base.median()).fillna(0.0).to_numpy(dtype=float)
    Xs = StandardScaler().fit_transform(X)

    model = IsolationForest(
        n_estimators=200, contamination="auto", random_state=20260831, n_jobs=1
    )
    labels = model.fit_predict(Xs)
    scores = model.score_samples(Xs)

    out = []
    for i, label in enumerate(labels):
        sid = int(df.iloc[i]["session_id"])
        if label != -1 or (only_ids is not None and sid not in only_ids):
            continue
        # Quais caracteristicas mais destoaram -- o "porque" da flag. `Xs` ja
        # esta padronizado: o valor absoluto E o numero de desvios da media.
        z = np.abs(Xs[i])
        vistos, motivos, categoria = set(), [], None
        for j in np.argsort(-z):
            rotulo, unidade, cat = FEATURE_LEGIVEL[ISOLATION_FEATURES[j]]
            if rotulo in vistos:
                continue
            vistos.add(rotulo)
            # "Degradacao" e "ociosidade" tem SENTIDO: potencia abaixo do
            # habitual, tempo parado acima. Um desvio para o outro lado
            # (potencia acima da media) destoa, mas nao e degradacao.
            if cat == "power_degradation" and Xs[i][j] > 0:
                cat = "consumption"
            if cat == "idle" and Xs[i][j] < 0:
                cat = "consumption"
            categoria = categoria or cat
            if rotulo == "horário de início":
                valor = f"{int(df.iloc[i]['start_hour'])}h"
            else:
                valor = f"{df.iloc[i][ISOLATION_FEATURES[j]]:.1f} {unidade}".strip()
            motivos.append(f"{rotulo} de {valor} ({z[j]:.1f} desvios do habitual)")
            if len(motivos) == 2:
                break
        out.append(
            Detection(
                session_id=sid,
                charge_point_id=None,
                category=categoria or "consumption",
                explanation=(
                    "Recarga fora do padrão do condomínio: " + "; ".join(motivos) + ". "
                    "Nenhuma regra isolada foi violada; é a combinação que destoa."
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
    # Historico como CONTEXTO, janela como ALVO. Sessao em andamento fica de
    # fora: ela ainda nao tem leitura final nem duracao, e julga-la agora era
    # acusar de "leitura perdida" toda recarga que so nao terminou.
    todas = list(
        ChargingSession.objects.filter(
            charge_point__condominium=condominium,
            session_start__gte=since - timedelta(days=HISTORY_DAYS),
            session_start__lte=until,
        ).exclude(status=ChargingSession.Status.IN_PROGRESS)
        .select_related("credential__user__unit", "charge_point")
        .prefetch_related("credential__user__vehicles")
    )
    sessions = [s for s in todas if s.session_start >= since]
    alvo = {s.id for s in sessions}
    feats_todas = extract(todas)
    feats = [f for f in feats_todas if f.session_id in alvo]
    by_id = {s.id: s for s in sessions}

    # Mediana historica por credencial -- base da regra de consumo atipico.
    medians: dict[int, float] = {}
    grouped: dict[int, list[float]] = {}
    for f in feats_todas:
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
            d for d in detect_isolation_forest(feats_todas, only_ids=alvo)
            if d.session_id not in ja_marcadas
        )

    existentes = {
        (f.session_id, f.charge_point_id, f.category)
        for f in AnomalyFlag.objects.filter(
            Q(session__in=[s.id for s in sessions])
            | Q(charge_point__condominium=condominium)
        )
    }
    # A chave de idempotencia vale contra o banco E dentro do proprio lote: duas
    # regras da mesma categoria (energia acima da bateria; 3x a mediana) acusam a
    # mesma sessao, e o sindico via o mesmo caso duas vezes na fila. Fica a
    # primeira, que e a mais especifica; a outra entra como complemento.
    novas: dict[tuple, AnomalyFlag] = {}
    for d in detections:
        chave = (d.session_id, d.charge_point_id, d.category)
        if chave in existentes:
            continue
        if chave in novas:
            novas[chave].explanation += " Além disso: " + d.explanation
            continue
        novas[chave] = AnomalyFlag(
            session_id=d.session_id,
            charge_point_id=d.charge_point_id,
            category=d.category,
            explanation=d.explanation,
            detector=d.detector,
            score=d.score,
            status=AnomalyFlag.Status.OPEN,
        )
    return AnomalyFlag.objects.bulk_create(list(novas.values()))
