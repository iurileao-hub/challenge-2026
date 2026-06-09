# Frente 2 — Base Regulatória e Técnica

## Resolução Normativa ANEEL nº 1.000/2021

> **Método.** Tudo o que esta seção afirma sobre a norma foi lido no texto oficial: o texto integral original publicado no DOU de 20/12/2021 (ed. 238, seção 1, p. 206) e a versão consolidada oficial da ANEEL (captura de 29/09/2025). Ambos estão preservados em [`docs/normas/`](normas/README.md), com os números de artigo conferidos arquivo em mãos.

A REN ANEEL nº 1.000, de 7 de dezembro de 2021, é a norma que consolida as **Regras de Prestação do Serviço Público de Distribuição de Energia Elétrica** — direitos e deveres de consumidores e distribuidoras. Ela revogou dezenas de resoluções anteriores, entre elas a **REN nº 819/2018** (art. 677, LII), cuja ementa diz: *"Estabelece os procedimentos e as condições para a realização de atividades de recarga de veículos elétricos"* — era a norma específica de recarga (texto oficial do DOU de 05/07/2018 preservado em [`docs/normas/`](normas/README.md)). A linhagem importa: desde 2018 a ANEEL já liberava a recarga de veículos de terceiros, *"inclusive para fins de exploração comercial a preços livremente negociados"* (REN 819/2018, art. 9º), e a REN 1.000 absorveu e manteve esse regime — o art. 554 reproduz a permissão do art. 9º, e os arts. 550, 552 e 555 descendem dos arts. 3º, 6º e 10 da norma revogada.

### Onde a recarga vive na norma

- **Definição** — art. 2º, XV: *"estação de recarga: conjunto de softwares e equipamentos utilizados para o fornecimento de corrente alternada ou contínua ao veículo elétrico, instalado em um ou mais invólucros, com funções especiais de controle e de comunicação, e localizados fora do veículo"*. Repare: a definição regulatória já inclui **software, controle e comunicação** — a camada que o EV ChargeOps ocupa faz parte do próprio conceito de estação de recarga.
- **Capítulo dedicado** — Título II (Parte Especial), **Capítulo V — *"Das Instalações de Recarga de Veículos Elétricos"*, arts. 550 a 560**, organizado em quatro seções: instalação (550–551), equipamentos (552–553), funcionamento (554–556) e prestação de recarga pela própria distribuidora (557–560).

### Os artigos que governam o projeto

| Art. | O que diz (síntese fiel ao texto) |
|---|---|
| **550** | A instalação de estação de recarga **deve ser comunicada previamente à distribuidora** em caso de necessidade de: I – conexão nova; II – aumento ou redução de carga; ou III – alteração do nível de tensão. |
| **551** | Custos de adequação da rede e do sistema de medição seguem os critérios gerais da própria Resolução. |
| **552** | Equipamentos de recarga **que não sejam exclusivos para uso privado** devem ser **compatíveis com protocolos abertos de domínio público** para: I – comunicação; e II – supervisão e controle remotos. |
| **553** | Na unidade consumidora com estação de recarga, devem ser observadas as normas e padrões da distribuidora e as normas dos órgãos oficiais competentes, no que for aplicável e não contrariar a regulação da ANEEL. |
| **554** | **É permitida a recarga de veículos que não sejam do titular da unidade consumidora, inclusive para fins de exploração comercial a preços livremente negociados.** |
| **555** | É **vedada a injeção de energia na rede** a partir dos veículos (e a participação no SCEE de micro/minigeração). Parágrafo único: a vedação não se aplica ao fluxo bidirecional restrito à mesma unidade consumidora — ou seja, V2G "para a rua" não; V2B dentro da própria instalação, sim. |
| **556** | A distribuidora deve ressarcir danos elétricos em veículo elétrico, nas condições da Resolução. |
| **557–560** | A distribuidora **pode** prestar atividade de recarga na sua área (como atividade acessória — cf. art. 629, § 2º, I, "j"), com preços livres, mas os ativos de recarga ficam fora da base de remuneração tarifária. |

### Estado de consolidação (verificado em 2026-06-09)

No texto consolidado oficial da ANEEL capturado em **29/09/2025**, o Capítulo V do Título II (arts. 550–560) **não tem nenhuma anotação de alteração** — o texto é idêntico ao original do DOU, embora a mesma captura registre mais de 600 anotações de alteração em outros pontos da norma. Regulação em movimento, porém: a **Consulta Pública ANEEL nº 42/2025** (contribuições de 11/12/2025 a 10/03/2026, conforme a notícia oficial da ANEEL de 09/12/2025, preservada em [`docs/normas/`](normas/README.md)) discute mudanças nas regras de conexão de carregadores — item de radar para o Sprint 2, ainda sem resolução publicada que altere os artigos acima.

## Carregador GoodWe HCA G2

> **Método.** Tudo o que esta seção afirma sobre o equipamento vem de documentação oficial da GoodWe efetivamente acessada em 2026-06-09: o datasheet brasileiro (br.goodwe.com), o datasheet global (en.goodwe.com) e o manual do usuário específico da geração G2 (*User Manual AC Charger HCA Series (7-22kW) G2*, V1.5-2025-11-11). O que é leitura ou inferência da equipe está marcado como tal. O modelo exato instalado no campus FIAP Aclimação (7, 11 ou 22 kW) não consta dos materiais do desafio — confirmar na visita ao Energy Innovation Lab (roteiro de entrevistas).

O HCA G2 é a geração atual ("G2") da linha HCA de carregadores CA da GoodWe — um wallbox (carregador fixo de parede) que o fabricante posiciona como extensão do ecossistema solar dele: o manual o descreve como *"an AC household charger mainly for EV charging"* que pode *"communicate with an inverter to use PV energy for EV charging"* e *"communicate with a MID meter (MID certificated smart meter) to provide reimbursable bills"* (MID: Measuring Instruments Directive — certificação metrológica europeia que habilita o medidor para cobrança). Essa última frase importa para o EV ChargeOps: a própria GoodWe enxerga o cenário de **medição certificada para reembolso de energia** — exatamente o caso de uso de rateio do desafio.

### Especificações básicas (datasheet BR)

| Item | GW7K-HCA-20 | GW11K-HCA-20 | GW22K-HCA-20 |
|---|---|---|---|
| Potência nominal de saída | 7 kW | 11 kW | 22 kW |
| Tensão nominal de entrada | 220 V (L/N/PE), monofásico | 380 V (3L/N/PE), trifásico | 380 V (3L/N/PE), trifásico |
| Corrente nominal de saída | 32 A | 16 A | 32 A |

Comuns aos três modelos (datasheet BR): conector **IEC Tipo 2** com cabo fixo de 6 m (7,5 m opcional), método de partida **"APP, RFID, Início Automático"**, comunicação **"Bluetooth, Wi-Fi, RS485 (×2), LAN"** e protocolo de comunicação **Modbus TCP**. Em proteção e construção: corrente residual **CA 30 mA + CC 6 mA** (com nota de que *"RCD tipo A externo é necessário"*), DPS Tipo III, desligamento de emergência integrado, IP66, instalação em parede ou poste e **2 cartões RFID inclusos**. Modos de operação: carregamento rápido, prioridade para solar, FV + bateria, agendamento e **controle de carga dinâmico**; certificações listadas: IEC 61851-1, IEC 62311, IEC 62955, AS/NZS 4268:2017, IEC 61008-1. (O datasheet global EN lista 230/400 V — valores de rede europeia; pela regra do projeto, citamos a versão BR.)

Duas notas de enquadramento, marcadas como **inferência da equipe** porque os documentos não usam essas palavras:

- **Modo de carga IEC.** O datasheet certifica IEC 61851-1 mas não declara "modo 3". Um wallbox CA dedicado, com cabo fixo e conector Tipo 2, é a definição prática de **modo 3** da IEC 61851-1 — enquadramento que o coloca dentro do que a IT-41 admite em áreas internas (item 5.3, *"somente modos 3 e 4"*, já mapeado na Opção A).
- **Homologação ANATEL.** O datasheet lista certificações IEC/AS-NZS, mas **não menciona homologação ANATEL** — que a IT-41 (item 5.10) exige para a comunicação sem fio das estações. Não significa que a unidade brasileira não seja homologada (datasheets globais raramente listam certificações nacionais); significa que é **item de verificação obrigatório** na visita ao campus e no checklist de onboarding de qualquer condomínio.

### Interfaces: o que cada uma permite e como a plataforma a usaria

| Interface | O que a documentação oficial diz que permite | Uso pelo EV ChargeOps |
|---|---|---|
| **RFID** (13,56 MHz; 2 cartões inclusos) | Partida da recarga por aproximação do cartão (*"For tapping card to activate charging"* — manual G2, descrição da área RFID) | **Chave de atribuição de sessão a usuário**: cada cartão vira um identificador de condômino/colaborador; o vínculo cartão → pessoa vive no cadastro da plataforma |
| **Wi-Fi** (2,4 GHz) | Conexão ao roteador local e daí ao SEMS Portal (nuvem); interface de usuário declarada é "WLAN + APP, LED" | Caminho da **telemetria em nuvem** (status, potência, energia) que a camada de ingestão consome |
| **LAN** (RJ45) | *"The LAN port is for the communication with the router"* (manual G2) | Mesmo papel do Wi-Fi com cabo — preferível em garagem de subsolo, onde Wi-Fi é precário; reduz sessão perdida por queda de rede |
| **Bluetooth** (BLE) | Conexão local do celular ao equipamento para comissionamento e configuração via app SolarGo (manual G2, procedimento de configuração) | Ferramenta de instalação/manutenção; sem papel na operação contínua da plataforma |
| **RS-485** (×2) | *"The RS485 port is for the communication with PV inverters or MID meters"* (manual G2): integração com inversor (recarga solar, dados do medidor inteligente p/ controle de carga dinâmico) e com medidor MID para contas reembolsáveis | **Integração local com medição certificada**: o medidor MID no RS-485 é a fonte de kWh com lastro metrológico para o rateio — mais defensável juridicamente que o kWh reportado pela nuvem |
| **Modbus TCP** (protocolo, sobre a rede local) | Único protocolo de comunicação declarado no datasheet | Alternativa de **telemetria local sem nuvem** — leitura direta na LAN, candidata a caminho primário de ingestão na Sprint 2 e além |

### O achado que define a arquitetura: nenhuma menção a OCPP

Nos três documentos oficiais consultados na íntegra (datasheet PT, datasheet EN e manual G2 V1.5, 69 páginas), **a palavra OCPP não aparece uma única vez** — o único protocolo declarado é Modbus TCP. Registramos isso como verificação documental da equipe (busca no texto integral dos três arquivos), não como prova de que o equipamento não possa vir a suportar OCPP por firmware; mas, para fins de projeto, o HCA G2 deve ser tratado como **carregador sem OCPP nativo documentado**.

### Análise da equipe

O HCA G2 é um carregador *solar-first* de nicho residencial, não um produto de recarga comercial multiusuário — e isso tem três consequências para o projeto. **Primeira:** a atribuição de sessão a usuário é viável com o que o equipamento já tem (RFID na partida + 2 cartões de fábrica + cartões adicionais), mas a inteligência de "quem é o dono do cartão" é toda nossa — o carregador autentica o cartão, a plataforma autentica a pessoa. **Segunda:** a ausência de OCPP nativo documentado conversa diretamente com o art. 552 da REN 1.000 (equipamento de uso não exclusivamente privado deve ser compatível com *"protocolos abertos de domínio público"* para comunicação e supervisão/controle remotos — discutido na Opção A): Modbus TCP é um protocolo aberto de especificação pública, o que dá um argumento de conformidade literal, mas é um protocolo de telemetria de equipamento, não de gestão de recarga (não modela sessão, usuário, autorização, tarifa). A leitura da equipe é que a arquitetura correta é um **gateway de ingestão que traduza o que o HCA G2 oferece (Modbus TCP local e/ou nuvem SEMS) para o modelo de dados OCPP internamente** — conformidade de espírito, não só de letra, e portabilidade para qualquer carregador aberto no futuro. **Terceira:** o RS-485 com medidor MID é a resposta do próprio fabricante à pergunta "que kWh vale para cobrança?" — num rateio condominial contestável em assembleia, medição certificada vale mais que número de API; o desenho da Sprint 2 deve manter o campo "fonte da medição" no esquema de dados desde o primeiro dia.

## API GoodWe SEMS Portal (documentação pública)

> **Método e restrição central.** A GoodWe informou que **não disponibilizará acesso à API SEMS para as equipes do desafio**, por limitação técnica do lado dela. Esta seção é, portanto, um levantamento **exclusivamente documental**: nenhum endpoint foi chamado, nem mesmo o de login. O objetivo muda de "integrar" para "especificar": o que se documenta aqui é o **contrato de dados que a camada de ingestão plugável da arquitetura (Frente 3) espelha** — e que a Sprint 2 alimentará com **dados sintéticos + dataset público (Kaggle) no mesmo esquema**, de modo que uma integração real futura seja um adaptador a plugar, não uma refatoração. Cada afirmação abaixo carrega seu nível de confiabilidade: **[A]** documentação oficial GoodWe; **[B]** código-fonte de integrações open-source amplamente usadas (engenharia reversa estável, mas não contratual); **[C]** documentação de terceiros.

### O que a documentação oficial diz [A]

A GoodWe publica no portal técnico dela (community.goodwe.com) dois documentos públicos sobre o serviço de API: *API Introduction* (SA-E-20221031-001) e *GoodWe API Technical Document* (SA-B-20240814-001, marcado "PUBLIC"). Deles extrai-se o desenho geral do serviço:

| Modalidade | Para quem | Transporte | O que oferece |
|---|---|---|---|
| **OpenAPI** | Exclusiva para contas de organização SEMS (*"exclusively accessible to SEMS organization account users"*) | HTTPS (JSON) | Dados de negócio processados pelo SEMS: lista e detalhes de plantas e dispositivos, geração diária/mensal/anual, controle remoto, dados de datalogger; limite padrão de **3.600 chamadas/hora** |
| **Real-time Data Monitoring API** | Terceiros, mediante credenciamento: *"apply for API access credentials and establish a licensing agreement"*, whitelist de dispositivos e autorização do usuário final | HTTPS (JSON) | Dados brutos em tempo real **de inversores** (operação, alarmes, produção, BMS, status de rede); sem controle remoto |
| **Batch Remote Control Interface** | Terceiros credenciados (mesmas condições) | **Kafka** (tópicos de comando/resultado) | Controle remoto em lote — caso de uso citado: gestão dinâmica de rede por concessionárias |

O acesso é sempre **mediado e fechado**: os documentos terminam com *"anyone who is interested in this service could contact the GoodWe service team"*, e a documentação de um integrador comercial (Solytic) descreve o rito na prática — pedido via representante de vendas, **assinatura de NDA** e só então habilitação da permissão de API na conta SEMS [C]. Isso é coerente com a restrição comunicada às equipes do desafio: não existe autosserviço de desenvolvedor (chave pública, sandbox, portal de developer) para o SEMS.

**O achado central do levantamento:** nos dois documentos oficiais, as funções descritas falam de inversores, dataloggers, BMS, estações meteorológicas e HomeKit — **carregadores de veículos elétricos não aparecem uma única vez**. O produto principal do SEMS é monitoramento solar; o suporte da API a carregadores **não tem documentação oficial pública**. Toda a especificação de contrato da subseção seguinte vem, portanto, de fonte comunitária — e essa lacuna, por si só, já justifica a decisão de não ancorar a plataforma nessa API.

### O contrato observado pela comunidade [B]

Na ausência de documentação oficial, a melhor fonte é código aberto que funciona em produção nas casas de usuários reais: a integração Home Assistant `goodwe-sems-home-assistant` (TimSoethout, mantida desde 2019) e seu derivado específico para wallboxes G2 `goodwe-wallbox-sems-gen2-fixed` (WolfrageTV), cujo `sems_api.py` foi lido na íntegra. O que esse código revela do contrato:

| Endpoint (POST, JSON) | Função | Corpo / retorno observado |
|---|---|---|
| `/api/v3/Common/CrossLogin` | Autenticação | Envia conta e senha; retorna no campo `data` um token (uid, timestamp, token) que vai **serializado num header `token`** nas chamadas seguintes; expira e exige novo login (`"authorization has expired"`) |
| `/api/v3/EvCharger/GetCurrentChargeinfo` | Estado atual do carregador | Corpo `{"sn": <série do wallbox>}`; retorna `power` (kW), `current` (A), `chargeEnergy` (kWh da carga corrente), `status`, `workstate` (chaves i18n `EVDetail_Status_Waiting_Stat00/01/02` = desconectado / conectado / carga concluída), `model`, versão de firmware |
| `/api/v4/EvCharger/GetEvChargerMoreView` | Visão ampliada (v4) | Mesmo corpo; a integração usa v4 com *fallback* para v3 quando o endpoint retorna 404 — sinal de API em mudança |
| `/api/v3/EvCharger/Charging` | Comando iniciar/parar | Corpo `{"sn", "status"}` |
| `/api/v3/EvCharger/SetChargeMode` | Modo e potência | Corpo `{"sn", "type", "charge_power"}` — modos Fast / PV priority / PV+battery, limite de potência |

Três características desse contrato merecem registro. (i) O header de login identifica o cliente como `semsPlusAndroid` — ou seja, a comunidade está usando a **API privada do aplicativo SEMS+**, não nenhuma das três modalidades oficiais da tabela anterior; pode mudar sem aviso, como a própria convivência v3/v4 com fallback sugere. (ii) O envelope de resposta é JSON com `msg` + `data`, e a expiração de token é sinalizada por mensagem, não por código HTTP — idiossincrasia que um adaptador real precisaria tratar. (iii) **O que não está documentado em lugar nenhum (lacuna):** histórico de sessões encerradas, eventos de início/fim de sessão e — crítico para o EV ChargeOps — **a identificação de qual cartão RFID iniciou a carga**. Os campos observados descrevem a carga *corrente*; se a API do app expõe sessões por usuário, nenhuma fonte pública consultada mostra como.

### O esquema que a ingestão plugável espelha

Do levantamento acima, o contrato mínimo de sessão que a camada de ingestão da arquitetura (Frente 3) adota — e que os dados sintéticos e o dataset Kaggle da Sprint 2 preencherão com a mesma estrutura:

| Campo | Tipo | Origem no SEMS observado | Origem na Sprint 2 |
|---|---|---|---|
| `charge_point_id` | texto (nº de série) | `sn` | gerador sintético / mapeamento do dataset |
| `session_start` / `session_end` | timestamp | **não exposto** — teria de ser derivado por amostragem de `workstate` | gerado diretamente |
| `energy_kwh` | decimal | `chargeEnergy` | gerado / coluna do dataset |
| `power_kw` | decimal (série temporal) | `power` (amostrado por polling) | curva sintética |
| `state` | enum (desconectado/conectado/carregando/concluído/offline) | `workstate` + `status` | gerado |
| `auth_id` (cartão RFID/usuário) | texto | **não exposto publicamente** | gerado — é a chave do rateio |
| `measurement_source` | enum (nuvem/Modbus local/medidor MID) | implícito (nuvem) | declarado pelo gerador |

### Análise da equipe

A restrição de acesso à API — que poderia parecer um golpe no projeto — é, bem lida, uma **decisão arquitetural tomada pela realidade**. Primeiro, porque o levantamento mostra que mesmo com acesso o contrato seria frágil: API privada de aplicativo, sem documentação oficial para carregadores, com versões convivendo (v3/v4) e sem os dois dados de que o rateio mais precisa (sessões encerradas e identidade RFID). Ancorar a plataforma nela seria construir sobre areia. Segundo, porque a resposta de engenharia — **camada de ingestão plugável que espelha o contrato documentado, alimentada na Sprint 2 por dados sintéticos e dataset público com o mesmo esquema** — não é um remendo: é o mesmo desenho que o art. 552 da REN 1.000 induz (protocolos abertos para comunicação e supervisão, discutido na Opção A) e que a ausência de OCPP nativo do HCA G2 já recomendava. O adaptador SEMS fica especificado e adiável; o adaptador Modbus TCP local vira candidato a caminho real de telemetria numa instalação própria; e o modelo de dados interno nasce OCPP-compatível, pronto para qualquer carregador aberto. Terceiro, porque a lacuna de atribuição RFID na API confirma que **a associação sessão → usuário é o coração do produto, não uma feature do fabricante**: nenhum componente do ecossistema GoodWe resolve isso hoje — é exatamente o espaço onde o EV ChargeOps existe. O risco residual que registramos honestamente: sem nenhum acesso real, nossa especificação do contrato SEMS pode conter erros que só uma chamada autenticada revelaria; mitigamos mantendo o adaptador isolado atrás de interface e tratando os campos da tabela como hipótese documentada, com fonte e nível de confiabilidade, revisável sem custo estrutural.

## Opção A — Mapeamento regulatório completo

> **Método (regra inegociável do projeto).** Toda afirmação sobre conteúdo, número de artigo ou data de norma nesta seção vem do **texto oficial baixado do site do órgão** e preservado em [`docs/normas/`](normas/README.md) (índice com URLs de origem e datas de download). Sínteses de terceiros foram usadas apenas para *descobrir* que uma norma existe. Normas cujo texto oficial não pôde ser obtido (NBRs da ABNT, que são pagas) estão marcadas como **identificadas, texto não obtido** — sobre elas o dossiê não afirma conteúdo interno, apenas o que outras normas exigem delas.

O carregador de referência fica em São Paulo (campus FIAP Aclimação) e o caso de uso central é o condomínio/edifício paulistano. Quatro camadas normativas incidem sobre a operação:

| Camada | Norma | O que governa |
|---|---|---|
| Federal — setor elétrico | REN ANEEL 1.000/2021, arts. 550–560 | Relação com a distribuidora, equipamentos, exploração comercial |
| Estadual — civil/condominial | Lei (SP) nº 18.403, de 18/02/2026 | Direito do condômino à recarga individual; capacidade mínima em novos empreendimentos |
| Estadual — segurança contra incêndio | IT nº 41 do CBPMESP, itens 5.2–5.12 (incluídos pela Portaria nº CCB-003/970/2026, de 17/03/2026) | Requisitos de instalação e segurança dos SAVE em edificações |
| Municipal — urbanística (São Paulo) | Lei nº 17.336, de 30/03/2020 | Obrigatoriedade de solução de recarga em novos edifícios, com medição individualizada |

### Mapa norma → artigo → obrigação → impacto no EV ChargeOps

| Norma | Artigo/item | Obrigação ou permissão | Impacto no EV ChargeOps |
|---|---|---|---|
| REN 1.000/2021 | art. 550 | Comunicação prévia à distribuidora se a estação exigir conexão nova, aumento/redução de carga ou alteração de tensão | A plataforma deve guardar, por ponto de recarga, o registro da comunicação à distribuidora (campo de cadastro + documento anexo) — evidência de conformidade para o síndico |
| REN 1.000/2021 | art. 552 | Equipamento de uso não exclusivamente privado deve ser compatível com **protocolos abertos** de comunicação e de supervisão/controle remotos | Pilar arquitetural: favorece desenho OCPP-compatível (ver Análise da equipe) |
| REN 1.000/2021 | art. 553 | Observar normas e padrões da distribuidora local (Enel Distribuição São Paulo, no caso de referência) e dos órgãos competentes | Checklist de implantação por condomínio deve incluir a norma técnica da distribuidora local |
| REN 1.000/2021 | art. 554 | **Permite** recarga de veículos de terceiros, inclusive exploração comercial a preços livres | Base que legitima o modelo de rateio/cobrança da plataforma (ver Análise da equipe) |
| REN 1.000/2021 | art. 555 | **Veda** injeção de energia do veículo na rede (V2G); permite fluxo bidirecional dentro da mesma unidade consumidora | Funcionalidades V2G ficam fora do escopo; V2B (veículo alimentando o prédio) é juridicamente possível, mas fora do MVP |
| Lei SP 18.403/2026 | art. 1º, caput e § 1º | Direito do condômino de instalar estação **individual** na vaga privativa, às suas expensas; exige compatibilidade de carga, conformidade com normas da distribuidora e ABNT, profissional habilitado com ART/RRT e comunicação prévia à administração | Acelera a demanda; a plataforma pode operar também como registro central dos pontos individuais (ART, comunicações, responsável técnico) |
| Lei SP 18.403/2026 | art. 1º, § 2º | Convenção condominial pode disciplinar comunicação, padrões técnicos e responsabilização por danos ou consumo, mas não pode proibir sem justificativa técnica/de segurança fundamentada e documentada | O relatório de capacidade elétrica gerado pela plataforma é exatamente o tipo de "justificativa técnica documentada" que uma negativa legítima exige |
| Lei SP 18.403/2026 | art. 2º | Novos empreendimentos aprovados após a lei devem prever capacidade elétrica mínima para instalação futura de estações (regulamentação por ato do Executivo, ainda pendente) | Mercado futuro garantido por lei; acompanhar o decreto regulamentador (radar Sprint 2) |
| Lei SP 17.336/2020 | art. 1º, I–II | Novos edifícios residenciais e comerciais no município de São Paulo devem prever solução de recarga com modo conforme normas técnicas brasileiras **e medição individualizada e cobrança da energia consumida** | A exigência municipal de *"medição individualizada e cobrança"* é, na prática, a especificação legal do núcleo do EV ChargeOps |
| Lei SP 17.336/2020 | art. 6º, I | Vigência 12 meses após publicação, para projetos protocolados a partir de então | Todo prédio paulistano com projeto novo desde ~abril/2021 já nasce com essa obrigação |
| IT-41 CBPMESP (red. Portaria CCB-003/970/2026) | item 3.1.1 | Edificações existentes devem atender os itens 5.2 a 5.12 na **renovação do AVCB** | O gatilho de adequação é a renovação do AVCB — momento natural de venda/implantação da solução |
| IT-41 | itens 5.2–5.2.3 | Responsável técnico/instaladora respondem integralmente; instalação conforme **NBR 5410, NBR 17019 e NBR IEC 61851-1** | Plataforma deve cadastrar o responsável técnico e o documento de responsabilidade por SAVE |
| IT-41 | item 5.3 | Em áreas internas, **somente modos 3 e 4** (NBR IEC 61851-1) | Exclui carregadores portáteis/tomada (modos 1 e 2) em garagens internas — só wallbox/estação dedicada entra no parque gerenciável |
| IT-41 | itens 5.4–5.5 | Chaves de desligamento de emergência (de pavimento e local) e **interligação com alarme/detecção de incêndio, com desligamento automático** dos SAVE | O monitoramento de status da plataforma deve tratar o desligamento por emergência como evento de primeira classe (diferenciar "queda por emergência" de "falha do equipamento") |
| IT-41 | itens 5.6–5.6.5 | Circuito exclusivo por SAVE com disjuntor + DR 30 mA individual, DPS no quadro, vedada conexão no padrão de entrada, proteção física, **proibidas tomadas comuns, adaptadores e extensões** | Requisitos de instalação que entram no checklist de onboarding de cada condomínio |
| IT-41 | item 5.9 (5.9.1–5.9.4) | Documento de responsabilidade técnica obrigatório, com **estudo de demanda e curva de carga** ratificando a viabilidade da infraestrutura | A telemetria da plataforma (curva de carga real por ponto) é o complemento operacional do estudo exigido — e o insumo da renovação seguinte |
| IT-41 | item 5.10 | Comunicação sem fio das estações (RFID, Bluetooth, Wi-Fi e similares) deve ter **homologação ANATEL** | Critério de seleção de hardware: exigir certificado ANATEL do carregador |
| IT-41 | item 5.12 | Para residências unifamiliares, as medidas são **recomendação** (boas práticas), não exigência | O peso regulatório recai sobre edificações coletivas — exatamente o nicho da plataforma |
| ABNT NBR 5410 / NBR 17019 / NBR IEC 61851-1 | — | **Identificadas, texto não obtido** (normas ABNT são pagas) | Referenciadas aqui apenas pelo que a IT-41 e a Lei 18.403 exigem delas; a conformidade fica a cargo do responsável técnico da instalação |

Registro de linhagem e contexto: a atualização da IT-41 decorre do **Decreto Estadual nº 69.118/2024** (novo Regulamento de Segurança contra Incêndio de SP) e de Diretriz Nacional do CNCGBM/LIGABOM sobre garagens com SAVE, conforme os "considerandos" das próprias portarias. O Parecer Técnico nº CCB-001/800/25 (Portaria CCB-009/800/2025) anuncia ainda adequações futuras nas IT 08, 15, 23 e 43 — que podem trazer exigências estruturais (detecção, chuveiros automáticos, controle de fumaça) para garagens, dependentes de reedição do decreto, com vacatio mínima de 180 dias. Radar para o Sprint 2.

### Avaliação de conformidade da solução proposta

| Requisito regulatório | Como o EV ChargeOps atende |
|---|---|
| Comunicação prévia à distribuidora (REN 1.000, art. 550) | Não é obrigação da plataforma, e sim do condomínio/instalador — mas a plataforma registra a comunicação por ponto (data, protocolo, documento) e alerta quando um ponto novo é cadastrado sem esse registro |
| Protocolo aberto para comunicação e supervisão (REN 1.000, art. 552) | Arquitetura desenhada para OCPP (protocolo aberto de domínio público para exatamente as duas funções citadas pelo artigo); integração proprietária (API SEMS) tratada como adaptador, não como fundação — ver Análise da equipe |
| Exploração comercial / cobrança permitida (REN 1.000, art. 554) | O modelo de rateio por kWh medido opera dentro da permissão expressa de preços livremente negociados; transparência de preço por assembleia |
| Medição individualizada e cobrança (Lei municipal 17.336, art. 1º, II) | Núcleo do produto: sessão identificada por usuário, kWh por sessão, rateio automático e auditável |
| Compatibilidade de carga e capacidade elétrica (Lei 18.403, art. 1º, § 1º, 1, e art. 2º) | Monitoramento da curva de carga agregada vs. capacidade declarada; relatório de capacidade para subsidiar decisões de assembleia e novas instalações |
| Registro de responsável técnico, ART/RRT (Lei 18.403, art. 1º, § 1º, 3; IT-41, item 5.9) | Cadastro de ponto exige responsável técnico e documento de responsabilidade anexado |
| Estudo de demanda e curva de carga (IT-41, item 5.9.4) | A plataforma não substitui o estudo do profissional habilitado, mas fornece a curva de carga real medida — insumo para o estudo e para auditorias futuras |
| Evento de desligamento de emergência (IT-41, itens 5.4–5.5) | Telemetria de status distingue indisponibilidade por emergência/desligamento manual de falha técnica; log auditável para o síndico e para vistoria |
| Somente modos 3 e 4 em áreas internas (IT-41, item 5.3) | A plataforma só gerencia estações dedicadas (wallbox AC em modo 3 ou estação DC em modo 4) — carregadores portáteis ficam fora do parque por desenho; o enquadramento do HCA G2 nos modos da NBR IEC 61851-1 é verificado na seção do carregador |
| Homologação ANATEL do rádio (IT-41, item 5.10) | Checklist de homologação no cadastro de modelo de carregador |
| Vedação V2G (REN 1.000, art. 555) | Escopo do produto não inclui injeção na rede; nada a remediar |

### Análise da equipe

Três perguntas de fronteira, com a leitura da equipe explicitamente separada do texto legal:

1. **Rateio condominial é "exploração comercial"?** O art. 554 permite a recarga de veículos de terceiros *"inclusive para fins de exploração comercial a preços livremente negociados"*. O rateio de custo entre condôminos (repassar o kWh medido sem margem) é um caso **mais brando** do que o teto permitido — se até a venda com lucro é livre, o repasse de custo está, a fortiori, dentro do regime. *Interpretação da equipe:* o modelo de negócio não depende de autorização adicional da ANEEL; o que não pode é o condomínio **revender energia como se fosse distribuidora** fora do contexto da recarga — o art. 554 cobre especificamente o serviço de recarga. Recomendação pragmática: validar o enquadramento tributário (ISS vs. ICMS sobre o serviço de recarga é discussão viva e **não** está resolvida na REN 1.000) com contador/jurídico antes de qualquer cobrança com margem.

2. **A comunicação prévia à distribuidora se aplica ao nosso caso?** O art. 550 condiciona a comunicação a três hipóteses: conexão nova, aumento/redução de carga ou alteração de tensão. *Interpretação da equipe:* um wallbox de 7–22 kW num condomínio quase sempre configura **aumento de carga** relevante (inciso II) — a postura segura é tratar a comunicação como regra, não exceção, e o art. 553 ainda manda observar a norma técnica da própria distribuidora (Enel SP tem padrão próprio para estações de recarga). Recomendação pragmática: confirmar com a distribuidora local o rito exato antes da implantação; somos estudantes, não advogados, e o custo de comunicar é baixo.

3. **O HCA G2 + plataforma atendem "protocolos abertos"?** O art. 552 alcança equipamentos *"que não sejam exclusivos para uso privado"* — um carregador compartilhado de condomínio, usado por vários condôminos, na nossa leitura **se enquadra** (uso coletivo ≠ uso exclusivamente privado). A consequência arquitetural é a mais importante do dossiê: **a exigência de protocolo aberto favorece a arquitetura OCPP-compatível mesmo sem acesso à API proprietária do fabricante.** Construir a plataforma sobre OCPP (e tratar a API SEMS/GoodWe como um adaptador entre vários) não é só boa engenharia anti-lock-in — é alinhamento direto com o texto regulatório. A verificação de se o HCA G2 expõe OCPP nativamente é objeto da seção do carregador (corpo obrigatório desta Frente); se não expuser, o desenho correto é um gateway que traduza a integração proprietária para o modelo de dados OCPP internamente, deixando a plataforma pronta para qualquer carregador aberto. *Interpretação da equipe* — o artigo não cita OCPP nominalmente; ele exige *"protocolos abertos de domínio público"* para comunicação e supervisão/controle remotos, e OCPP é o padrão aberto consolidado que cumpre exatamente essas duas funções.

**Divergências encontradas em relação à Frente 1** (citadas lá a partir de fontes secundárias; corrigir na revisão final — Task 13):

- A Frente 1 afirma que o Corpo de Bombeiros "atualizou a IT-41 em novembro de 2025". **Impreciso.** Em 12/11/2025 a Portaria nº CCB-008/800/2025 apenas **abriu consulta pública** (30 dias) sobre a proposta de alteração; a atualização efetiva da IT-41 veio com a **Portaria nº CCB-003/970/2026, de 17/03/2026**, que incorporou os itens 5.2 a 5.12 — com diferenças de conteúdo em relação à minuta de novembro (ex.: DR 30 mA tipos A/F/B e homologação ANATEL só aparecem no texto final).
- A Frente 1 diz que, pela Lei 18.403/2026, "a negativa agora exige laudo técnico fundamentado". O texto legal (art. 1º, § 2º) fala em *"justificativa técnica ou de segurança devidamente fundamentada e documentada"* — não exige formalmente um "laudo". Paráfrase próxima, mas vale ajustar para a expressão legal.
- Confirmado em fonte primária (sem divergência): a Lei 18.403/2026 é **estadual** (ALESP, 18/02/2026, com retificação em 20/02/2026), como a Frente 1 corretamente classificou; e as três NBRs citadas (5410, 17019, NBR IEC 61851-1) existem com esses números e títulos, confirmados verbatim nos itens 5.2.1–5.2.3 da IT-41.

## Opção C — APIs complementares
<!-- a preencher -->

## Fontes
<!-- a preencher (demais seções) -->

### Frente 2 — corpo obrigatório (HCA G2 e API SEMS)

Documentação oficial GoodWe (todas acessadas em 2026-06-09; nenhum endpoint de API foi chamado):

1. GoodWe Brasil — Datasheet *Linha HCA G2 — Carregador CA* (PT, versão 20241121-V2.1). https://br.goodwe.com/Ftp/Downloads/Datasheet/PT/GW_HCA-G2_Datasheet-PT.pdf
2. GoodWe — Datasheet *HCA G2 Series EV Charger* (EN). https://en.goodwe.com/Ftp/EN/Downloads/Datasheet/GW_HCA-G2_Datasheet-EN.pdf
3. GoodWe — *User Manual AC Charger HCA Series (7-22kW) G2*, V1.5-2025-11-11 (69 p.), obtido pela página oficial de downloads do produto (arquivo "GW_HCA G2_User Manual-EN"); íntegra também conferida em espelho de distribuidor (solarmarkt.ch). https://en.goodwe.com/download-hca-g2-series
4. GoodWe — página de produto *HCA G2 Series AC Charger*. https://en.goodwe.com/hca-g2
5. GoodWe Solar Academy — *GoodWe API Technical Document*, SA-B-20240814-001 (PUBLIC). https://community.goodwe.com/static/images/2024-08-20597794.pdf
6. GoodWe Solar Academy — *API Introduction*, SA-E-20221031-001. https://community.goodwe.com/static/images/2022-11-08281223.pdf

Código aberto da comunidade (nível [B] — engenharia reversa em uso real, não contratual; acesso em 2026-06-09):

7. TimSoethout — `goodwe-sems-home-assistant` (integração Home Assistant para o SEMS API, mantida desde 2019). https://github.com/TimSoethout/goodwe-sems-home-assistant
8. WolfrageTV — `goodwe-wallbox-sems-gen2-fixed` (integração Home Assistant específica para wallboxes HCA G2 via SEMS; `custom_components/sems-wallbox/sems_api.py` e `sensor.py` lidos na íntegra, branch master). https://github.com/WolfrageTV/goodwe-wallbox-sems-gen2-fixed

Documentação de terceiros (nível [C] — usada apenas para o rito de credenciamento; acesso em 2026-06-09):

9. Solytic — *Set up API access – GoodWe SEMS API* (pedido via representante, NDA, habilitação na conta SEMS). https://solytic.com/knowledge/set-up-api-access-goodwe-sems-api/

### Frente 2 — Opção A (e seção REN 1.000/2021)

Fontes primárias e oficiais (capturas preservadas em [`docs/normas/`](normas/README.md); acesso em 2026-06-09; a fonte nº 4 é notícia oficial da ANEEL, não texto de norma):

1. ANEEL — Resolução Normativa nº 1.000, de 7/12/2021, texto integral original. DOU 20/12/2021, ed. 238, seção 1, p. 206. https://www.in.gov.br/en/web/dou/-/resolucao-normativa-aneel-n-1.000-de-7-de-dezembro-de-2021-368359651
2. ANEEL — REN 1.000/2021, texto consolidado oficial (captura de 29/09/2025 da página oficial; ver nota de proveniência no README de docs/normas). https://www2.aneel.gov.br/cedoc/ren20211000.html
3. ANEEL — Resolução Normativa nº 819, de 19/06/2018 (revogada pela REN 1.000/2021, art. 677, LII), texto integral original. DOU 05/07/2018, ed. 128, seção 1, p. 70. https://www.in.gov.br/materia/-/asset_publisher/Kujrw0TZC2Mb/content/id/28737289/do1-2018-07-05-resolucao-normativa-n-819-de-19-de-junho-de-2018-28737273
4. ANEEL — notícia oficial "ANEEL abre consulta pública para aprimorar regras de conexão de eletromobilidade à rede elétrica", 09/12/2025 (datas da Consulta Pública nº 42/2025: contribuições de 11/12/2025 a 10/03/2026). https://www.gov.br/aneel/pt-br/assuntos/noticias/2025/aneel-abre-consulta-publica-para-aprimorar-regras-de-conexao-de-eletromobilidade-a-rede-eletrica
5. ALESP — Lei nº 18.403, de 18/02/2026 (texto retificado em 20/02/2026). https://www.al.sp.gov.br/repositorio/legislacao/lei/2026/lei-18403-18.02.2026.html
6. Prefeitura de São Paulo — Lei nº 17.336, de 30/03/2020. https://legislacao.prefeitura.sp.gov.br/leis/lei-17336-de-30-de-marco-de-2020
7. CBPMESP — Portaria nº CCB-008/800/2025, de 12/11/2025 (consulta pública da proposta de alteração da IT-41). https://cbaplang.corpodebombeiros.sp.gov.br/Midias/638986232326891879.pdf
8. CBPMESP — Portaria nº CCB-009/800/2025, de 12/11/2025 (Parecer Técnico nº CCB-001/800/25 sobre SAVE). https://cbaplang.corpodebombeiros.sp.gov.br/Midias/638986232512702533.pdf
9. CBPMESP / DOE-SP — Portaria nº CCB-003/970/2026, de 17/03/2026 (atualiza a IT-41, itens 5.2–5.12). https://doe.sp.gov.br/executivo/secretaria-da-seguranca-publica/portaria-n-003-970-2026-de-17-de-marco-de-2026-20260316113816712141709068

Fontes secundárias (usadas apenas para descobrir a existência de normas/processos, nunca para afirmar conteúdo):

10. Aranda/FotoVolt — "Aneel abre consulta para regras de recarga de veículos elétricos" (como fonte de descoberta da Consulta Pública ANEEL nº 42/2025; as datas estão confirmadas na fonte oficial nº 4). https://www.arandanet.com.br/revista/fotovolt/noticia/12147-Aneel-abre-consulta-para-regras-de-recarga-de-veiculos-eletricos.html
11. Agência SP — "Corpo de Bombeiros de SP divulga novas regras de segurança para recarga de carros elétricos no estado". https://www.agenciasp.sp.gov.br/corpo-de-bombeiros-de-sp-divulga-novas-regras-de-seguranca-para-recarga-de-carros-eletricos-no-estado/
