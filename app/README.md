# EV ChargeOps: aplicação (Sprint 2)

Implementação da arquitetura definida na Sprint 1. O contrato está em
[`../docs/frente-3-arquitetura.md`](../docs/frente-3-arquitetura.md); este diretório é a execução dele.

## Como rodar

Requisitos: Python 3.12+, PostgreSQL 16, [uv](https://docs.astral.sh/uv/).

```bash
# 1. banco
sudo -u postgres psql -c "CREATE ROLE chargeops LOGIN PASSWORD 'chargeops_dev' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE chargeops OWNER chargeops;"

# 2. dependências e esquema
cd app
uv sync
uv run python manage.py migrate

# 3. dados de demonstração (mês fictício do dossiê + 6 meses sintéticos)
uv run python manage.py seed_demo --months 6 --reset

# 4. pipeline completo: detecção → rateio → previsão → reconciliação
uv run python manage.py pipeline --reconciliar

# 5. interface
uv run python manage.py runserver
```

Acesso em `http://127.0.0.1:8000/entrar/`, senha `chargeops` para todos:

| Usuário | Papel | O que vê |
|---|---|---|
| `sindica` | gestora | painel, fila de auditoria, relatório da assembleia |
| `ana`, `carla`, `davi` | moradores | extrato da própria unidade, contestação |

Carla (unidade 34) é a que tem a sessão interrompida com leitura perdida, e por isso a
fatura dela fica retida em auditoria.

## Estrutura

```
core/          14 entidades da Frente 3-C, cenário do dossiê, comandos de gestão
billing/       motor de rateio, competência em fuso civil, reconciliação
ingestion/     gateway plugável, adaptadores (SEMS stub, dataset real), gerador, calibração
intelligence/  detecção de anomalias (2 fases), previsão com backtest, avaliação
portal/        painel do gestor e portal do morador
```

Só `core` define modelos: nenhuma FK atravessa fronteira de app.

## Verificação

```bash
uv run pytest                    # 47 testes
uv run pytest -m "not slow"      # sem os que geram meses de dados
```

A suíte de aceitação (`billing/tests/test_mes_ficticio.py`) reproduz o mês fictício de
junho/2026 do dossiê: as três faturas (R$ 53,21, R$ 66,76 e R$ 72,33), os agregados
(203,120 kWh, R$ 327,30) e os ajustes de reconciliação (R$ 37,54). **Os valores esperados
foram copiados do documento da Sprint 1, escrito antes de existir código.**

Para medir a detecção de anomalias contra o gabarito do gerador:

```bash
uv run python manage.py evaluate_ai --months 6
```

## Decisões que valem explicação

**Dinheiro nunca passa por `float`.** O dossiê fixou arredondamento half-up por linha e
escolheu de propósito um caso que separa as convenções: 11,250 × 0,7252 = 8,1585, que é
R$ 8,16 em half-up e R$ 8,15 em half-even (o padrão do IEEE-754). Há teste para isso.

**Competência é calculada em fuso civil, sobre timestamps persistidos em UTC.** A sessão
1010 começa 30/06 23:40 BRT, que em UTC já é 01/07. Decidir a competência pelo timestamp
armazenado jogaria a sessão para julho e erraria a fatura em R$ 20,16.

**Vigências sem sobreposição são garantidas pelo banco**, com `EXCLUSION CONSTRAINT` e
`btree_gist`. Um `CHECK` não daria conta: a regra fala de pares de linhas, e `CHECK` só
enxerga a linha corrente.

**O modelo de previsão é escolhido por medição, não por preferência.** O gradient boosting
é treinado e comparado com a média por dia da semana num backtest de 14 dias. Se perder, a
plataforma serve o baseline e diz na tela que serviu o baseline.

**A calibração declara o que é dado e o que é premissa.** A forma da duração e do horário
vem das 3.395 sessões reais de Asensio et al. (2021); a energia por sessão, não. Aqueles
carregadores entregavam 2,13 kW medianos contra os 7 kW do HCA G2, e por isso ela é
derivada por física.
O perfil semanal residencial é premissa declarada da equipe: o dataset é de local de
trabalho e nunca observou um condomínio.
