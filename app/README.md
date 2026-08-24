# EV ChargeOps: aplicação (Sprint 2)

Implementação da arquitetura definida na Sprint 1. O contrato está em
[`../docs/frente-3-arquitetura.md`](../docs/frente-3-arquitetura.md); este diretório é a execução dele.
A visão de produto, a pesquisa e as fontes estão no [README da raiz](../README.md).

**Sumário**

1. [Pré-requisitos](#1-pré-requisitos)
2. [Como rodar](#2-como-rodar)
3. [Configuração por ambiente](#3-configuração-por-ambiente)
4. [Usuários de demonstração](#4-usuários-de-demonstração)
5. [Roteiro de exploração](#5-roteiro-de-exploração)
6. [Como o sistema funciona por dentro](#6-como-o-sistema-funciona-por-dentro)
7. [Mapa de rotas](#7-mapa-de-rotas)
8. [Estrutura do código](#8-estrutura-do-código)
9. [Comandos de gestão](#9-comandos-de-gestão)
10. [Verificação](#10-verificação)
11. [Decisões que valem explicação](#11-decisões-que-valem-explicação)
12. [Solução de problemas](#12-solução-de-problemas)

---

## 1. Pré-requisitos

| Requisito | Versão | Por que essa versão |
|---|---|---|
| Python | 3.12 ou superior | Fixado em `.python-version` e `pyproject.toml` |
| PostgreSQL | **13 ou superior** (testado em 16) | A migração `0002` usa `EXCLUSION CONSTRAINT` com a extensão `btree_gist`. A partir do PG 13 essa extensão é *trusted*, o que permite ao dono do banco instalá-la sem ser superusuário. Em versões anteriores o `migrate` falha pedindo superusuário |
| [uv](https://docs.astral.sh/uv/) | qualquer recente | Gerenciador de dependências e de ambiente virtual. O `uv.lock` versionado garante que todo mundo instale exatamente as mesmas versões |

**Python não precisa ser instalado à mão.** O `uv` lê o `.python-version`, baixa a
versão 3.12 se ela não existir na máquina e cria o ambiente virtual sozinho. Basta
instalar o `uv` e o PostgreSQL.

<details open>
<summary><strong>Linux (Ubuntu/Debian)</strong></summary>

```bash
# uv (instala em ~/.local/bin)
curl -LsSf https://astral.sh/uv/install.sh | sh

# PostgreSQL e os contribs, que trazem o btree_gist
sudo apt install postgresql postgresql-contrib

# o serviço sobe sozinho; se não subiu:
sudo systemctl start postgresql
```
</details>

<details>
<summary><strong>macOS</strong></summary>

Com [Homebrew](https://brew.sh/):

```bash
brew install uv
brew install postgresql@16
brew services start postgresql@16

# o Homebrew não põe os binários do postgres no PATH por padrão:
echo 'export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Em Mac com processador Intel, o prefixo é `/usr/local` no lugar de `/opt/homebrew`.

O Homebrew cria o papel do PostgreSQL com o **seu nome de usuário**, e não `postgres`.
Por isso os comandos de criação do banco no passo 1 mudam de forma: use os da aba
correspondente na seção seguinte.
</details>

<details>
<summary><strong>Windows</strong></summary>

Duas rotas. A primeira é a recomendada.

**Rota A: WSL2 (recomendada).** Dá o ambiente Linux inteiro, e todos os comandos deste
README funcionam sem tradução.

```powershell
wsl --install -d Ubuntu
```

Reinicie, abra o Ubuntu no menu Iniciar e siga as instruções de Linux acima. O projeto
deve ficar dentro do sistema de arquivos do WSL (`~/`, não `/mnt/c/`): em `/mnt/c` o
acesso a disco é ordens de grandeza mais lento e o `uv sync` demora minutos.

**Rota B: Windows nativo.** No PowerShell:

```powershell
# uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# PostgreSQL: instalador oficial (marque "Add to PATH" no instalador)
winget install PostgreSQL.PostgreSQL.16
```

O instalador pede uma senha para o superusuário `postgres`. Guarde: ela é pedida em todo
comando `psql -U postgres`. O serviço sobe como serviço do Windows, sem `systemctl`.

Duas diferenças que aparecem ao seguir os passos: o `uv run` funciona igual, mas o
`sudo -u postgres` não existe no Windows nativo, e a ativação do ambiente virtual, se
você precisar dela, é `.venv\Scripts\activate` no lugar de `source .venv/bin/activate`.
</details>

Nenhuma GPU é necessária, em nenhum dos três sistemas. Os modelos de IA são clássicos
(scikit-learn e statsmodels) e rodam em segundos numa máquina modesta: a escolha está
justificada na Frente 3-B.

## 2. Como rodar

Cada passo abaixo é independente e pode ser repetido. Os tempos são de uma VM de 2 vCPU.

**Passo 1: criar o papel e o banco.** Roda uma vez só, e é o único passo que muda de
sistema para sistema, porque muda quem é o administrador do PostgreSQL.

<details open>
<summary><strong>Linux</strong></summary>

```bash
sudo -u postgres psql -c "CREATE ROLE chargeops LOGIN PASSWORD 'chargeops_dev' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE chargeops OWNER chargeops;"
```
</details>

<details>
<summary><strong>macOS (Homebrew)</strong></summary>

O Homebrew não cria o papel `postgres`: quem administra é o seu próprio usuário, e o
banco de mesmo nome já existe. Por isso não há `sudo -u postgres`, e sim conexão direta:

```bash
psql -d postgres -c "CREATE ROLE chargeops LOGIN PASSWORD 'chargeops_dev' CREATEDB;"
psql -d postgres -c "CREATE DATABASE chargeops OWNER chargeops;"
```
</details>

<details>
<summary><strong>Windows (nativo)</strong></summary>

No PowerShell. A senha pedida é a do superusuário, definida no instalador:

```powershell
psql -U postgres -c "CREATE ROLE chargeops LOGIN PASSWORD 'chargeops_dev' CREATEDB;"
psql -U postgres -c "CREATE DATABASE chargeops OWNER chargeops;"
```

Se `psql` não for reconhecido, o instalador não o pôs no PATH. O caminho costuma ser
`C:\Program Files\PostgreSQL\16\bin`. No WSL2, use os comandos da aba Linux.
</details>

**Passos 2 a 5: iguais nos três sistemas.** O `uv` cuida das diferenças de ambiente.

```bash
# 2. dependências e esquema (~1 min na primeira vez, pelo download dos pacotes)
cd app
uv sync
uv run python manage.py migrate

# 3. dados de demonstração: mês fictício do dossiê + 6 meses sintéticos (~4 s)
uv run python manage.py seed_demo --months 6 --reset

# 4. pipeline completo: detecção -> rateio -> previsão -> reconciliação (~5 s)
uv run python manage.py pipeline --reconciliar

# 5. interface
uv run python manage.py runserver
```

Abra `http://127.0.0.1:8000/entrar/`.

O passo 4 imprime no terminal o ciclo inteiro da plataforma, e é a forma mais rápida de
ver o produto funcionando sem abrir o navegador. A saída esperada termina com as três
faturas do dossiê (R$ 53,21, R$ 66,76 e R$ 72,33) e os R$ 37,54 de ajuste de
reconciliação. Se esses números aparecerem, a instalação está correta.

> **Ordem importa.** O passo 4 depende do 3, que depende do 2. Rodar o `pipeline` num
> banco vazio não dá erro: ele simplesmente não encontra sessões e fecha zero faturas.

## 3. Configuração por ambiente

A aplicação lê configuração de variáveis de ambiente, com defaults de desenvolvimento
embutidos em `chargeops/settings.py`. **Por isso ela sobe sem nenhuma configuração**:
os defaults são exatamente os valores do passo 1 acima.

Para mudar qualquer coisa, copie o modelo versionado e edite:

```bash
cp .env.example .env
```

| Variável | Default | Para que serve |
|---|---|---|
| `DJANGO_SECRET_KEY` | chave de desenvolvimento | Assinatura de sessões e tokens. Trocar obrigatoriamente fora de desenvolvimento |
| `DJANGO_DEBUG` | `1` | Páginas de erro detalhadas. `0` em produção |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hosts autorizados, separados por vírgula |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `chargeops` / `chargeops` / `chargeops_dev` | Credenciais do PostgreSQL |
| `DB_HOST` / `DB_PORT` | `127.0.0.1` / `5432` | Endereço do PostgreSQL |
| `CONDOMINIUM_TIME_ZONE` | `America/Sao_Paulo` | Fuso civil em que a competência da fatura é decidida. Ver a decisão sobre virada de mês na seção 11 |

## 4. Usuários de demonstração

Senha `chargeops` para todos, criados pelo `seed_demo`:

| Usuário | Papel | O que vê |
|---|---|---|
| `sindica` | gestora (Sônia Duarte) | painel, fila de auditoria, relatório da assembleia |
| `ana` | moradora, unidade 72 | extrato da própria unidade e contestação. Divide a unidade com Bruno, que tem carro e credencial próprios mas não tem login: a fatura dos dois é uma só |
| `carla` | moradora, unidade 34 | idem, com a fatura retida em auditoria |
| `davi` | morador, unidade 105 | idem, unidade de um morador só |

Carla é a que tem a sessão interrompida com leitura perdida, e por isso a fatura dela
fica retida em auditoria. É o caso mais interessante do sistema, e o ponto de partida
sugerido para explorar.

> **A demonstração roda com a data fixa em 30/06/2026** (`DEMO_TODAY`, em
> `portal/views.py`). As telas mostram sempre a competência de junho/2026, que é o mês
> fictício do dossiê, independentemente da data real da máquina. Sem isso a interface
> abriria num mês vazio e não haveria o que demonstrar.

## 5. Roteiro de exploração

A ordem abaixo percorre a tese do produto em cerca de cinco minutos. Cada passo mostra
uma decisão de projeto, não apenas uma tela.

1. **Entre como `sindica` e abra o painel.** A faixa do topo responde "está tudo bem?"
   antes de qualquer número. Abaixo da curva de previsão há um bloco *De onde vem esse
   número*, que declara em português de assembleia o que o modelo usou, com quantos dias
   de histórico aprendeu e quanto errou no teste dos últimos 14 dias, contra o erro de um
   chute pela média simples. Quando o gradient boosting perde dessa média, a plataforma
   serve a média e a tela diz que serviu. A honestidade do modelo é parte da interface,
   e nenhum jargão aparece: o síndico precisa conseguir repetir isso em voz alta.

2. **Desça até a fila de auditoria.** Há uma anomalia esperando decisão humana: a
   sessão da unidade 34 cuja leitura final do medidor não chegou. Note que a fatura da
   unidade está no estado *Em auditoria*, e não *Fechada*. A detecção rodou **antes** do
   fechamento, não depois.

3. **Confirme ou descarte a anomalia.** O estado da fatura muda; o valor, não. Nenhuma
   saída de IA altera cobrança. A plataforma produz evidência, e quem responde pela
   decisão decide.

4. **Abra o relatório da assembleia** (`/painel/relatorio/`) e exporte o CSV. É o
   artefato que o síndico leva para a reunião, e o motivo de o rateio precisar ser
   auditável linha a linha.

5. **Saia e entre como `carla`.** O extrato mostra a mesma sessão pelo outro lado. A
   fatura vem com o aviso *Em revisão*, que promete o essencial: "o valor pode diminuir,
   nunca aumentar; você não precisa fazer nada". A linha de 12/06 traz a explicação
   legível do que aconteceu (sessão interrompida por queda de energia, cobrada a última
   leitura confirmada) e o botão de contestação. O morador contesta olhando a mesma
   evidência que o síndico viu.

6. **Entre como `ana`** (unidade 72, o casal com dois veículos). Ana dirige um BYD
   Dolphin e autentica por RFID; Bruno dirige um Volvo EX30 e autentica pelo app. São
   duas pessoas, dois carros e duas credenciais, e o extrato traz as três recargas de
   junho numa fatura só, com uma única taxa de disponibilidade. A recarga de 10/06 é do
   Bruno, que não tem login. O caso excepcional do enunciado se resolve pela modelagem,
   sem regra ad hoc: a fatura é por unidade, não por pessoa.

   > Hoje o extrato não rotula qual credencial iniciou cada recarga. O dado existe
   > (`InvoiceLine.session.credential`) e a agregação está correta; o que falta é a
   > exibição.

7. **Volte ao terminal e rode `pipeline --reconciliar` de novo.** A reconciliação
   tarifária em dois tempos aparece no fim: a conta real da distribuidora chegou mais
   cara que a tarifa provisória, e a diferença vira linha de ajuste na competência
   seguinte. Junho permanece intacto, porque fatura fechada não se reescreve.

## 6. Como o sistema funciona por dentro

O caminho que um evento de recarga percorre, do carregador à assembleia:

```
   fonte de dados            (1) INGESTÃO
   ┌──────────────┐          ingestion/gateway.py
   │ stub SEMS    │─┐        normaliza qualquer fonte para um
   │ dataset real │─┼──────▶ modelo interno compatível com OCPP
   │ gerador      │─┘        ingestion/adapters/*.py
   └──────────────┘                    │
                                       ▼
                              (2) PERSISTÊNCIA
                              core/models.py
                              14 entidades, nomes idênticos aos
                              do dicionário do dossiê
                                       │
                                       ▼
                              (3) DETECÇÃO DE ANOMALIAS
                              intelligence/anomalies.py
                              fase 1: regras estatísticas
                              fase 2: Isolation Forest
                                       │
                     ┌─────────────────┴─────────────────┐
                     │ sessão limpa          sessão suspeita
                     ▼                                   ▼
              (4) MOTOR DE RATEIO                 linha marcada,
              billing/engine.py                   fatura vai para
              energia medida + disponibilidade    "Em auditoria"
              aritmética decimal, half-up                │
                     └─────────────────┬─────────────────┘
                                       ▼
                              (5) FATURA + PREVISÃO
                              billing/  ·  intelligence/forecast.py
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼                                   ▼
              painel do gestor                   portal do morador
              portal/views.py:painel             portal/views.py:extrato
```

O ponto que sustenta a tese sobre IA não decorativa é o estágio (3) estar **entre** a
sessão e o fechamento, e não depois dele. Remover a detecção não apaga um gráfico:
quebra o ciclo de estados da fatura, e há um teste cujo único propósito é falhar nesse
caso (`intelligence/tests/test_deteccao.py`).

O laço de reconciliação fecha por fora desse fluxo: quando a fatura real da
distribuidora chega, `billing/reconciliation.py` compara a tarifa efetiva com a
provisória e lança a diferença como linha de ajuste na competência seguinte, sem tocar
no mês já fechado.

## 7. Mapa de rotas

| Rota | Quem acessa | O que faz |
|---|---|---|
| `/entrar/` | público | Autenticação |
| `/` | autenticado | Encaminha cada pessoa para a interface que é dela (gestor para o painel, morador para o extrato) |
| `/painel/` | gestor | Ocupação, saúde dos pontos, curva prevista com o método declarado, fila de auditoria |
| `/painel/anomalia/<id>/revisar/` | gestor (POST) | Confirma ou descarta uma anomalia. Muda o estado da fatura, nunca o valor |
| `/painel/relatorio/` | gestor | Relatório mensal da assembleia, com exportação CSV |
| `/extrato/` | morador | Fatura explicada linha a linha, sessões que a formaram, melhor janela de recarga |
| `/extrato/linha/<id>/contestar/` | morador (POST) | Contestação informada: a evidência antes da discordância |
| `/admin/` | superusuário | Admin do Django, útil para inspecionar as 14 entidades cruas |
| `/sair/` | autenticado | Encerra a sessão |

Para usar o `/admin/`, crie um superusuário: `uv run python manage.py createsuperuser`.

## 8. Estrutura do código

```
chargeops/                     configuração do projeto Django
  settings.py                  variáveis de ambiente, banco, fuso civil
  urls.py                      rotas de topo (login, admin, portal)

core/                          o modelo de domínio, e só ele
  models.py                    as 14 entidades da Frente 3-C
  scenarios/jardim_aurora.py   o condomínio do dossiê, montado em código
  management/commands/         seed_demo, pipeline, evaluate_ai, forecast_demo

ingestion/                     como o dado entra
  gateway.py                   normaliza qualquer fonte para o modelo interno
  adapters/sems.py             stub do contrato SEMS, espelhado da documentação
  adapters/dataset.py          leitor do TSV acadêmico de Asensio et al. (2021)
  generator.py                 gerador sintético com gabarito de anomalias
  calibration.py               distribuições extraídas do dataset real

billing/                       o coração auditável
  engine.py                    o motor de rateio: energia medida + disponibilidade
  money.py                     aritmética decimal com arredondamento half-up
  competence.py                a que mês pertence uma sessão, em fuso civil
  reconciliation.py            o ajuste de dois tempos quando a conta real chega

intelligence/                  a IA que precisa passar em métrica
  features.py                  agregados por dia, ponto e credencial
  anomalies.py                 detecção em duas fases (regras, Isolation Forest)
  forecast.py                  previsão de 7 dias com backtest contra baseline
  evaluation.py                precisão e recall contra o gabarito do gerador

portal/                        as duas interfaces
  views.py                     painel do gestor e portal do morador
  urls.py                      rotas do portal
  context.py                   dados comuns aos templates

templates/portal/              HTML das telas
static/                        CSS e imagens
```

Só `core` define modelos: nenhuma FK atravessa fronteira de app. A regra é o que
permite ler cada módulo isoladamente, e o que torna a troca de um adaptador de ingestão
uma mudança local.

## 9. Comandos de gestão

Todos com `uv run python manage.py <comando>`.

| Comando | O que faz | Opções |
|---|---|---|
| `seed_demo` | Popula o banco com o condomínio de demonstração: o mês fictício de junho/2026 do dossiê, mais meses sintéticos calibrados no dado real | `--months N` (meses de histórico sintético), `--reset` (apaga o cenário anterior), `--seed N` (semente determinística), `--anomaly-rate F` (fração de sessões com anomalia injetada) |
| `pipeline` | Executa o ciclo completo de uma competência: detecção, fechamento do rateio, previsão | `--competencia AAAA-MM` (default `2026-06`), `--reconciliar` (encena a chegada da conta real e lança os ajustes) |
| `evaluate_ai` | Gera dados com gabarito conhecido, roda a detecção e reporta precisão e recall por categoria de anomalia. **Substitui o cenário de demonstração**, ver o aviso na seção 10 | `--months N`, `--seed N`, `--anomaly-rate F`, `--no-isolation-forest` (mede só a fase 1) |
| `forecast_demo` | Previsão de demanda de 7 dias, isolada do resto do pipeline | `--today AAAA-MM-DD` (default `2026-05-31`) |

O `evaluate_ai` é o comando que sustenta a afirmação de que a IA não é decorativa:
ele produz um número que pode reprovar o modelo.

## 10. Verificação

```bash
uv run pytest                    # 50 testes
uv run pytest -m "not slow"      # sem os que geram meses de dados
```

Distribuição da suíte:

| Arquivo | Testes | O que garante |
|---|---|---|
| `billing/tests/test_mes_ficticio.py` | 19 | A suíte de aceitação: reproduz o mês fictício do dossiê, e fixa a convenção de arredondamento |
| `portal/tests/test_portal.py` | 16 | Interfaces, autorização por papel, contestação e revisão |
| `intelligence/tests/test_deteccao.py` | 10 | Detecção nas duas fases, e o ciclo de estados da fatura |
| `ingestion/tests/test_gateway.py` | 5 | Fontes diferentes entrando pelo mesmo caminho |

A suíte de aceitação reproduz o mês fictício de junho/2026 do dossiê: as três faturas
(R$ 53,21, R$ 66,76 e R$ 72,33), os agregados (203,120 kWh, R$ 327,30) e os ajustes de
reconciliação (R$ 37,54). **Os valores esperados foram copiados do documento da Sprint 1,
escrito antes de existir código.**

Para medir a detecção de anomalias contra o gabarito do gerador:

```bash
uv run python manage.py evaluate_ai --months 6
```

> ⚠️ **`evaluate_ai` substitui o cenário de demonstração.** Ele precisa de dados com
> gabarito conhecido, então gera um cenário novo por cima do que estava no banco. Duas
> consequências: as faturas de junho somem, e os logins do portal (`sindica`, `ana`,
> `carla`, `davi`) ficam órfãos, porque o vínculo entre a conta de acesso e a pessoa é
> feito pelo `seed_demo`. O sintoma é o portal responder 404 em todas as telas depois de
> um login bem-sucedido. Para restaurar, repita os passos 3 e 4 do "Como rodar":
>
> ```bash
> uv run python manage.py seed_demo --months 6 --reset
> uv run python manage.py pipeline --reconciliar
> ```
>
> Rode o `evaluate_ai` antes de demonstrar o sistema, nunca durante.

## 11. Decisões que valem explicação

**Dinheiro nunca passa por `float`.** O dossiê fixou arredondamento half-up por linha,
e a convenção só decide o valor quando o produto cai **exatamente** na metade de um
centavo. Com a tarifa de R$ 0,7252, o consumo que faz isso é 12,500 kWh: dá 9,06500
exato, que é R$ 9,07 em half-up e R$ 9,06 em half-even (o padrão do IEEE-754). O mesmo
caso mostra por que o tipo importa: 0,7252 não tem representação binária exata, o produto
em ponto flutuante fica um fio abaixo do empate e `round(12.5 * 0.7252, 2)` devolve 9,06.
Há teste para os três resultados.

> Correção de uma afirmação anterior: até 24/08/2026, este README, o `billing/money.py` e
> o dossiê da Frente 3 usavam a sessão 1006 (11,250 × 0,7252 = 8,1585) como o caso que
> separaria as convenções. Não separa: a fração descartada ali é 0,85 do centavo, não
> metade dele, e half-up, half-even e `float` concordam em R$ 8,16. A regra escolhida
> continua correta; o exemplo que a justificava, não.

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

## 12. Solução de problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `connection to server at "127.0.0.1", port 5432 failed` | PostgreSQL não está rodando | Linux: `sudo systemctl start postgresql`. macOS: `brew services start postgresql@16`. Windows: iniciar o serviço `postgresql-x64-16` em `services.msc` |
| `FATAL: role "chargeops" does not exist` | O passo 1 não foi executado | Rodar os dois comandos `psql` do passo 1, na variante do seu sistema |
| Portal responde **404 em todas as telas** logo após um login bem-sucedido | `evaluate_ai` substituiu o cenário e deixou os logins órfãos | `seed_demo --months 6 --reset` e `pipeline --reconciliar`. Ver o aviso na seção 10 |
| `psql: command not found` (macOS) | O Homebrew não põe o PostgreSQL 16 no PATH | `export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"` (Intel: `/usr/local/opt/...`) |
| `role "postgres" does not exist` (macOS) | O Homebrew usa o seu usuário como administrador | Usar `psql -d postgres -c ...`, sem `sudo -u postgres` |
| `psql` não reconhecido (Windows) | O instalador não adicionou ao PATH | Adicionar `C:\Program Files\PostgreSQL\16\bin` ao PATH, ou usar o "SQL Shell (psql)" do menu Iniciar |
| `uv sync` demora muitos minutos (WSL2) | O projeto está em `/mnt/c/` | Mover o repositório para dentro do sistema de arquivos do WSL (`~/`) |
| `permission denied to create extension "btree_gist"` | PostgreSQL 12 ou anterior | A extensão só é *trusted* a partir do PG 13. Atualizar o PostgreSQL, ou instalar a extensão como superusuário antes do `migrate`: `sudo -u postgres psql -d chargeops -c "CREATE EXTENSION btree_gist;"` |
| `Error: That port is already in use.` | Já existe um servidor na 8000 | Usar outra porta: `uv run python manage.py runserver 8001` |
| `uv: command not found` | O instalador não está no PATH | `export PATH="$HOME/.local/bin:$PATH"` |
| `pipeline` não fecha fatura nenhuma | Banco sem dados na competência pedida | Rodar `seed_demo --months 6 --reset` antes, ou passar a competência certa em `--competencia` |
| Testes falham em massa logo após `uv sync` | Banco de teste não pode ser criado | O papel `chargeops` precisa de `CREATEDB`. Conferir com `sudo -u postgres psql -c "\du chargeops"` |
