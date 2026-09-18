"""Avaliacao da deteccao contra o gabarito do gerador.

O gerador sabe quais sessoes recebeu anomalia injetada. Comparar a saida do
detector com essa lista da precisao e recall de verdade, por categoria.

**Ressalva metodologica que preferimos declarar a esconder:** o gabarito e
*parcial*. Ele marca o que foi injetado de proposito, mas o modelo fisico do
gerador produz, por conta propria, sessoes legitimamente extremas -- um carro
que enche a bateria em 2 h e fica plugado a noite inteira e ociosidade real,
nao injetada. Essas aparecem como "falso positivo" na conta sem serem erro do
detector.

Por isso lemos as duas metricas com pesos diferentes: **recall e a metrica
confiavel** (o detector achou o que sabidamente estava la?), e a precisao e
piso, nao valor exato -- a precisao real e maior que a medida.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.models import AnomalyFlag


@dataclass
class CategoryScore:
    category: str
    injected: int = 0
    detected: int = 0
    true_positives: int = 0
    extra: int = 0

    @property
    def recall(self) -> float:
        return self.true_positives / self.injected if self.injected else float("nan")

    @property
    def precision_floor(self) -> float:
        return self.true_positives / self.detected if self.detected else float("nan")


@dataclass
class EvaluationReport:
    by_category: dict = field(default_factory=dict)
    total_injected: int = 0
    total_detected: int = 0
    total_true_positives: int = 0

    @property
    def overall_recall(self) -> float:
        return self.total_true_positives / self.total_injected if self.total_injected else float("nan")

    def render(self) -> str:
        linhas = [
            f"{'categoria':<20} {'injetadas':>10} {'detectadas':>11} {'acertos':>8} {'recall':>8} {'prec.piso':>10}",
            "-" * 70,
        ]
        for cat in sorted(self.by_category):
            s = self.by_category[cat]
            linhas.append(
                f"{cat:<20} {s.injected:>10} {s.detected:>11} {s.true_positives:>8} "
                f"{s.recall:>7.0%} {s.precision_floor:>10.0%}"
            )
        linhas.append("-" * 70)
        linhas.append(
            f"{'TOTAL':<20} {self.total_injected:>10} {self.total_detected:>11} "
            f"{self.total_true_positives:>8} {self.overall_recall:>7.0%}"
        )
        return "\n".join(linhas)


def evaluate(ground_truth, condominium) -> EvaluationReport:
    """Compara o gabarito do gerador com as flags persistidas."""
    report = EvaluationReport()

    flags = AnomalyFlag.objects.filter(
        session__charge_point__condominium=condominium
    ) | AnomalyFlag.objects.filter(charge_point__condominium=condominium)
    flags = flags.distinct()

    detected_pairs = {(f.session_id, f.charge_point_id, f.category) for f in flags}
    detected_by_cat: dict[str, int] = {}
    for _, _, cat in detected_pairs:
        detected_by_cat[cat] = detected_by_cat.get(cat, 0) + 1

    truth_by_cat: dict[str, list] = {}
    for g in ground_truth:
        truth_by_cat.setdefault(g.category, []).append(g)

    for cat in sorted(set(truth_by_cat) | set(detected_by_cat)):
        score = CategoryScore(category=cat)
        # Pares unicos dos dois lados. Contar ocorrencias em vez de pares deixava
        # varios gabaritos colapsarem na mesma chave e produzia precisao > 100%
        # -- um numero impossivel, que foi justamente o que denunciou o defeito.
        truth_pairs = {(g.session_id, g.charge_point_id, cat) for g in truth_by_cat.get(cat, [])}
        det_pairs = {p for p in detected_pairs if p[2] == cat}
        score.injected = len(truth_pairs)
        score.detected = len(det_pairs)
        score.true_positives = len(truth_pairs & det_pairs)
        score.extra = max(score.detected - score.true_positives, 0)
        report.by_category[cat] = score
        report.total_injected += score.injected
        report.total_detected += score.detected
        report.total_true_positives += score.true_positives

    return report


#: Faixas de intensidade, por categoria, na unidade do limiar da regra.
#: (rotulo, minimo inclusivo, maximo exclusivo, "a politica manda sinalizar?")
SENSITIVITY_BINS = {
    "idle": [
        ("menos de 3 h ociosas", 0.0, 3.0, False),
        ("3 a 4 h (logo abaixo do limiar)", 3.0, 4.0, False),
        ("4 a 5 h (logo acima do limiar)", 4.0, 5.0, True),
        ("5 h ou mais", 5.0, 99.0, True),
    ],
    "power_degradation": [
        ("potencia cai a menos de 50%", 0.0, 0.50, True),
        ("cai a 50-60% (logo alem do limiar)", 0.50, 0.60, True),
        ("cai a 60-75% (aquem do limiar)", 0.60, 0.75, False),
        ("cai a 75% ou mais", 0.75, 9.0, False),
    ],
}


def sensitivity(ground_truth, condominium) -> dict[str, list[dict]]:
    """Taxa de deteccao por faixa de intensidade -- ONDE o detector opera.

    Recall de 100% sobre anomalias injetadas sempre acima do limiar e
    tautologia: a regra dispara acima de 4 h, o gerador injeta de 5 a 11 h.
    O numero que informa e o formato da curva. Espera-se ~0% abaixo do limiar
    (la nao e anomalia, por POLITICA do condominio, nao por falha) e ~100%
    acima; o que acontece no entorno do limiar mede o erro da propria
    estimativa de ociosidade, que vem de telemetria amostrada a cada 15 min.
    """
    por_detector: dict[str, set] = {"rule": set(), "isolation_forest": set()}
    for sid, cat, det in AnomalyFlag.objects.filter(
        session__charge_point__condominium=condominium
    ).values_list("session_id", "category", "detector"):
        por_detector.setdefault(det, set()).add((sid, cat))

    out: dict[str, list[dict]] = {}
    for cat, bins in SENSITIVITY_BINS.items():
        linhas = []
        for rotulo, lo, hi, esperado in bins:
            casos = [
                g for g in ground_truth
                if g.category == cat and g.magnitude is not None and lo <= g.magnitude < hi
            ]
            regra = sum(1 for g in casos if (g.session_id, cat) in por_detector["rule"])
            # A fase 2 so olha o que a fase 1 deixou passar; e pode classificar
            # a sessao em outra categoria. Conta qualquer flag dela na sessao.
            ids_if = {sid for sid, _ in por_detector["isolation_forest"]}
            floresta = sum(1 for g in casos if g.session_id in ids_if)
            linhas.append({"faixa": rotulo, "injetadas": len(casos), "regra": regra,
                           "floresta": floresta, "deve_sinalizar": esperado})
        out[cat] = linhas
    return out
