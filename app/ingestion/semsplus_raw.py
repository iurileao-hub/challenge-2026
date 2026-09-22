"""Do JSON bruto do SEMS+ ao CSV versionado, sem Django.

As respostas de `chargePile/queryChargeLogList` ficam em `data/semsplus_raw/`
(fora do repo, pelo `data/*` do .gitignore). O que entra no repo e o CSV que
este modulo gera, com as colunas e os valores exatamente como a fonte os
escreveu. Para regenerar:

    cd app && uv run python -m ingestion.semsplus_raw ../data/semsplus_raw/*.json
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
#: As 72 sessoes coletadas em 22/09/2026 (colunas com os nomes do JSON).
LOG_PATH = DATA_DIR / "semsplus_charge_log.csv"
#: A transcricao da tela de 26/06/2026 (18 sessoes, colunas em portugues). Historico.
LOG_PATH_2026_06 = DATA_DIR / "semsplus_charge_log_2026-06.csv"

#: Colunas que o CSV guarda, na ordem. `mileage` (energia x 5 km/kWh), `unit` e
#: `chartUnit` ficam de fora: sao derivados ou constantes.
CSV_FIELDS = [
    "chargeSerialNumber", "chargePileSN", "chargeCardNumber", "charGun", "chargeMuzzle",
    "chargeStartTime", "chargeEndTime", "currentChargeQuantity", "chargeTimeLength",
    "greenElec", "purElec", "chargeEndCause",
]


def merge_raw_pages(paths) -> list[dict]:
    """Junta respostas brutas e tira as sessoes repetidas.

    As janelas de consulta se sobrepoem (a tela pagina de 20 em 20 e limita o
    intervalo), entao a mesma sessao pode aparecer em mais de um arquivo. A
    chave e o `chargeSerialNumber`. Numeros ficam como TEXTO, exatamente como
    vieram, para que o CSV nao passe pelo `float`.
    """
    unicas: dict[str, dict] = {}
    for p in paths:
        with Path(p).open(encoding="utf-8") as f:
            resposta = json.load(f, parse_float=str, parse_int=str)
        for rec in resposta["data"]["dataList"]:
            unicas.setdefault(rec["chargeSerialNumber"], rec)
    return sorted(unicas.values(), key=lambda r: r["chargeStartTime"])


def write_log_csv(records: list[dict], out: Path = LOG_PATH) -> None:
    with Path(out).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(records)


if __name__ == "__main__":
    registros = merge_raw_pages(sys.argv[1:])
    write_log_csv(registros)
    print(f"{len(registros)} sessoes unicas -> {LOG_PATH}")
