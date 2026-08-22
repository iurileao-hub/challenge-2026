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
