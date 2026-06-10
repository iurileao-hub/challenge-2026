# EV ChargeOps — Enterprise Challenge 2026 (FIAP × GoodWe)

Sprint 1 do Enterprise Challenge 2026: pesquisa e documentação do **EV ChargeOps**, plataforma que transforma sessões de recarga de veículos elétricos em infraestrutura compartilhada (condomínios, edifícios corporativos, campi) em dados estruturados, rateio justo e inteligência acionável.

Este README é a síntese do trabalho da equipe. Cada frente de pesquisa tem um dossiê completo em `docs/`, com método declarado, fontes verificadas e análise própria — aqui apresentamos as conclusões e decisões; o detalhe, a evidência e a justificativa estendida estão nos dossiês linkados.

## Equipe

**Equipe GoodNóis**

| Integrante | RM |
|---|---|
| Gabriel Carmona Bittencourt | RM569239 |
| Iúri Leão de Almeida | RM570215 |
| Márcio Francisco dos Santos Júnior | RM570758 |
| Maria Sophia Domingues dos Santos | RM571209 |

## O problema

O Brasil emplacou 223.912 veículos eletrificados leves em 2025 — crescimento de 26% sobre 2024, dez vezes o ritmo do mercado total — e 81% deles são plug-in, ou seja, dependem de tomada. A rede pública de recarga também cresce (+42% em doze meses), mas cresce mais devagar que a frota: mesmo no melhor semestre da história da rede, a razão de veículos plug-in por ponto público **piorou** de 17,9 para 19,6 — quase o dobro da referência de 10:1 que a própria ABVE considera adequada. A consequência, que quantificamos com dados públicos no nosso notebook de análise, é que a recarga cotidiana recai sobre o lugar onde o carro dorme: a garagem do condomínio, da empresa, do campus — padrão que a IEA confirma globalmente: a recarga residencial permanece a forma mais popular de recarregar um EV (*Global EV Outlook 2025*, fonte 71; detalhe na Frente 1).

Essa garagem, porém, chega a esse papel sem nenhuma camada de gestão. A energia é da área comum, mas o consumo é individual; sem atribuição de sessão a usuário, o custo da recarga de poucos é diluído na cota condominial de todos — fonte direta de conflito em assembleia. Somam-se a isso o limite físico de potência da instalação, a disputa pelo carregador compartilhado, as exigências de segurança e conformidade pelas quais o síndico responde legalmente, e um quadro normativo que acelera a adoção (a Lei paulista 18.403/2026 garante ao condômino o direito de instalar ponto de recarga) sem dizer como operá-la.

Nossa leitura do problema, construída ao longo das três frentes: **o gargalo não é o hardware, é a gestão**. Cada sessão de recarga já captura os dados necessários — quem autenticou, quanta energia foi entregue, quando, em que ponto. O que falta é a plataforma que estrutura esses dados em sessões identificadas por usuário, calcula o consumo individual, aplica um rateio justo e auditável e devolve inteligência operacional ao gestor e clareza ao morador. É isso que o EV ChargeOps propõe.

## Frente 1 — Contexto e Problema

Dossiê completo: [docs/frente-1-contexto.md](docs/frente-1-contexto.md) · Notebook de análise: [notebooks/frota_ev_brasil.ipynb](notebooks/frota_ev_brasil.ipynb)

**Opções de aprofundamento escolhidas: A (análise de mercado), B (pesquisa com usuários — em andamento) e C (análise de dados públicos).** O roteiro de entrevistas da Opção B está pronto em [docs/entrevistas/roteiro.md](docs/entrevistas/roteiro.md) e as entrevistas estão em aplicação; respostas e insights serão incorporados ao dossiê antes da entrega.

O achado central da frente: **a frota eletrificada cresce mais rápido do que a infraestrutura pública consegue acompanhar, e a diferença é empurrada para dentro da infraestrutura compartilhada privada.** A análise de dados públicos (Opção C) sustenta isso com três curvas reproduzíveis no notebook: emplacamentos 19 vezes maiores em seis anos, com a fatia plug-in saltando de 41% (2021) para 81% (2025); rede pública concentrada (SP+RJ+RS+DF somam mais da metade dos pontos; 70% dos municípios não têm nenhum); e a razão veículos/ponto piorando mesmo no período de expansão recorde da rede.

No corpo obrigatório, documentamos as cinco dores recorrentes do gestor (limite de potência, rateio justo, disputa por carregadores, conformidade técnica, vácuo de governança), a anatomia técnica de uma sessão de recarga (do Control Pilot da IEC 61851 às mensagens do protocolo OCPP — StartTransaction, MeterValues, StopTransaction) e os cinco modelos de negócio praticados no Brasil e no mundo. Duas conclusões dessa investigação moldaram o resto do projeto: o modelo de dados da plataforma já está praticamente desenhado pelo vocabulário OCPP, e o motor de tarifação precisa ser configurável, porque a regulação brasileira libera o preço e o mercado pratica todos os formatos.

Na análise de mercado (Opção A), mapeamos quatro soluções em quadrantes diferentes — Zaptec (hardware premium europeu), ChargePoint (plataforma global), NeoCharge (player nacional de condomínios) e Copel EV (rede pública de concessionária) — com tabela comparativa de problema, funcionalidades, modelo de negócio e limitações. A leitura conjunta revela a lacuna que o EV ChargeOps ataca: **nenhuma das quatro oferece, ao mesmo tempo, rateio condominial nativo do contexto brasileiro, neutralidade de hardware via protocolo aberto e IA operacional sobre a telemetria.** O contraexemplo da Copel (eletropostos inativos sem sinalização, app mal avaliado) ainda nos deu um requisito de primeira classe: monitoramento de saúde dos pontos.

## Frente 2 — Base Regulatória e Técnica

Dossiê completo: [docs/frente-2-regulatorio.md](docs/frente-2-regulatorio.md) · Textos oficiais preservados: [docs/normas/](docs/normas/)

**Opções de aprofundamento escolhidas: A (mapeamento regulatório completo) e C (APIs complementares).** A GoodWe comunicou que não disponibilizará acesso à API SEMS; a Opção B (exploração da API) ficou inviabilizada e virou decisão arquitetural. A API foi coberta no nível obrigatório por levantamento documental (ver "Estratégia de dados").

O achado que define a arquitetura: **o carregador GoodWe HCA G2 não documenta OCPP (o único protocolo declarado é Modbus TCP) e a API SEMS é fechada — e a documentação oficial dela sequer menciona carregadores.** Lemos na íntegra os três documentos oficiais do equipamento (dois datasheets e o manual G2 de 69 páginas) e os dois documentos públicos da API; o contrato real usado pela comunidade vem de engenharia reversa do app SEMS+, sem os dois dados de que o rateio mais precisa (sessões encerradas e identidade do cartão RFID). Conclusão de engenharia: ancorar a plataforma nessa API seria construir sobre areia; a resposta é uma camada de ingestão plugável que normaliza qualquer fonte para um modelo interno OCPP-compatível. Documentamos também o que cada interface do HCA G2 permite (RFID como chave de atribuição de sessão, LAN/Wi-Fi para telemetria, RS-485 para medidor MID certificado, Bluetooth para comissionamento) e o achado positivo: a medição certificada via RS-485 é a fonte de kWh com lastro metrológico que um rateio contestável em assembleia exige.

No mapeamento regulatório (Opção A), seguimos uma regra inegociável: **toda afirmação sobre norma vem do texto oficial, baixado do site do órgão e preservado no repositório** — sínteses de terceiros serviram apenas para descobrir que uma norma existe. Quatro camadas incidem sobre a operação: a REN ANEEL 1.000/2021 (arts. 550–560: comunicação prévia à distribuidora, protocolos abertos para equipamentos de uso não exclusivamente privado, permissão expressa de exploração comercial a preços livres, vedação de V2G); a Lei estadual 18.403/2026 (direito do condômino à recarga na vaga privativa); a IT-41 do Corpo de Bombeiros de SP, atualizada pela Portaria CCB-003/970/2026 (somente modos 3 e 4 em áreas internas, circuito exclusivo com DR individual, desligamento de emergência interligado ao alarme de incêndio, homologação ANATEL da comunicação sem fio); e a Lei municipal paulistana 17.336/2020 — que exige, em novos edifícios, recarga com *medição individualizada e cobrança*, ou seja, a especificação legal do núcleo do nosso produto. O dossiê traz o mapa norma → artigo → obrigação → impacto e a avaliação de conformidade da solução, item a item. Destaque da nossa leitura: o art. 552 (protocolos abertos) favorece a arquitetura OCPP-compatível mesmo sem acesso à API do fabricante — conformidade de espírito, não só de letra.

Nas APIs complementares (Opção C), testamos por chamada real (respostas brutas preservadas em `data/`): a Open Charge Map, que dá o contexto competitivo público ao redor de cada condomínio, e a ANEEL Dados Abertos, de onde extraímos a tarifa homologada vigente da Enel SP (R$ 0,7252/kWh, grupo B3 convencional, sem tributos, REH 3.477/2025) — a âncora auditável do motor de rateio. As chamadas reais renderam quatro pegadinhas de engenharia que nenhum manual documenta (o agente se chama "ELETROPAULO", valores em string com vírgula em R$/MWh, base tarifária correta, exclusão das linhas SCEE) — cada uma seria um bug silencioso na Sprint 2.

## Frente 3 — Arquitetura e IA

Dossiê completo: [docs/frente-3-arquitetura.md](docs/frente-3-arquitetura.md)

**Opções de aprofundamento escolhidas: A (benchmark de modelos de rateio), B (papel da IA) e C (esquema da base de dados) — todas.**

O corpo obrigatório organiza a plataforma nas quatro camadas do enunciado (física, conectividade, aplicação, apresentação) e descreve o fluxo de dados completo, em dez passos numerados, da conexão do cabo à prestação de contas em assembleia — incluindo o laço de reconciliação quando a fatura real da distribuidora chega. A assimetria do desenho é deliberada: a camada de conectividade, que numa arquitetura típica seria a mais fina, é aqui a mais carregada de decisão, porque é onde mora a dupla restrição real do projeto (carregador sem OCPP documentado + API do fabricante inacessível) — e a ingestão plugável é essa restrição transformada em arquitetura.

No benchmark de rateio (Opção A), comparamos quatro arranjos com praticantes reais — kWh medido no boleto condominial (WEG WEMOB, NeoCharge), cobrança direta com reembolso (ChargePoint), concessão interna com tarifa de operador (EZVolt) e taxa fixa por unidade — e duas convergências orientaram a decisão: todo modelo com medição usa o kWh como base da cobrança variável, e os custos fixos são o ponto cego do kWh puro. Daí o nosso modelo híbrido (detalhado em "Modelo de rateio" abaixo).

No papel da IA (Opção B), impusemos a nós mesmos um teste objetivo contra IA decorativa: cada abordagem declara que campos do esquema consome, que saída produz e que decisão concreta habilita. Três abordagens passaram (previsão de demanda, clustering de perfis, detecção de anomalias); duas vão para a Sprint 2; o clustering fica especificado mas adiado por honestidade estatística; e a interface conversacional (NLP) foi explicitamente rejeitada do núcleo. Detalhe em "Papel da IA" abaixo.

No esquema de dados (Opção C), derivamos de trás para frente — das exigências da fórmula de rateio, dos casos excepcionais e das abordagens de IA — um esquema de **14 entidades** (o enunciado pedia 4; cada uma das 10 a mais nasceu de exigência já escrita no dossiê), com dicionário completo, diagrama entidade–relacionamento, registros simulados de cada entidade e um mês fictício inteiro fechado com aritmética decimal conferida por script: 10 sessões, 3 unidades (incluindo o casal com dois veículos, a sessão interrompida e a sessão que atravessa a virada do mês), faturas linha a linha e a reconciliação tarifária do mês seguinte demonstrada com números.

Com as três frentes fechadas, o desenho consolidado da plataforma é o que segue.

## Arquitetura da solução

![Diagrama de arquitetura](assets/arquitetura.png)

A plataforma se organiza em quatro camadas. Na **física**, o carregador GoodWe HCA G2 (7–22 kW, RFID na partida, medição embarcada e medidor MID opcional no RS-485), instalado sob o quadro normativo da IT-41 e das NBRs aplicáveis. Na **conectividade**, a decisão central do projeto: um gateway de ingestão plugável que normaliza três fontes intercambiáveis (stub do contrato SEMS, gerador sintético e dataset público Kaggle — futuramente, Modbus TCP local) para um modelo interno OCPP-compatível, de modo que trocar de fonte seja trocar de adaptador, não refatorar. Na **aplicação**, o pipeline de seis estágios: ingestão, validação e atribuição de sessão a unidade, persistência no esquema de 14 entidades, motor de rateio, módulos de IA (que leem das mesmas tabelas que o faturamento escreve) e geração de fatura. Na **apresentação**, duas interfaces: o painel do gestor (ocupação e saúde dos pontos, curva prevista com alertas, fila de auditoria de anomalias, relatórios exportáveis para assembleia) e o portal do morador (extrato sessão a sessão, fatura explicada linha a linha, melhor janela de recarga, contestação informada). O diagrama editável está em [assets/arquitetura.mmd](assets/arquitetura.mmd).

## Estratégia de dados

A GoodWe comunicou que **não disponibilizará acesso à API SEMS** para as equipes do desafio. Tratamos essa restrição não como obstáculo a contornar, mas como decisão arquitetural de primeira classe — até porque nosso levantamento mostrou que, mesmo com acesso, o contrato seria frágil: API privada de aplicativo, sem documentação oficial para carregadores e sem os dados de sessão encerrada e identidade RFID de que o rateio depende. A estratégia é um tripé:

1. **Contrato SEMS por documentação** — especificamos o contrato de dados a partir da documentação pública oficial e do código aberto da comunidade (com nível de confiabilidade declarado afirmação a afirmação), e o congelamos como um adaptador stub da camada de ingestão: se o acesso um dia existir, é um adaptador a plugar, não uma refatoração.
2. **Dataset público real** — as 3.395 sessões reais de recarga de Asensio et al. (2021), publicadas na Scientific Data e reempacotadas no Kaggle (o dataset sugerido pelo enunciado), mapeadas campo a campo no nosso esquema; é a base empírica que impede que as distribuições dos nossos dados sejam invenção.
3. **Gerador de dados sintéticos** — produz sessões e telemetria diretamente no esquema da Frente 3-C, calibrado nas distribuições do dataset real (com o eixo horário espelhado do padrão diurno de trabalho para o noturno de condomínio) e capaz de injetar anomalias com gabarito conhecido, o que torna a detecção avaliável com métrica objetiva.

Honestidade declarada: **nenhum evento real de um HCA G2 atravessou este pipeline até aqui.** Dado real do carregador do campus só será possível na visita ao Energy Innovation Lab, na Sprint 2, se viável — e o desenho inteiro aposta que, quando ele chegar, entra pelo mesmo gateway sem mover nenhuma outra caixa da arquitetura. Essa aposta é verificável e será cobrada.

## Modelo de rateio

Modelo híbrido em duas parcelas, faturado mensalmente **por unidade condominial**: energia medida por sessão ao custo de repasse, mais uma taxa de disponibilidade rateada entre as unidades aderentes ao programa (não entre todas as do condomínio). A fatura da unidade `u` no mês `M`:

```
fatura_u = sum(round2(kwh_s × tarifa_s) for s in S_u) + round2(C_disp / N_aderentes)
```

onde `S_u` são as sessões do mês atribuídas às credenciais da unidade, `kwh_s` a energia medida da sessão, `tarifa_s` o snapshot da tarifa de repasse vigente no início da sessão (ancorada na tarifa homologada ANEEL da distribuidora, com reconciliação contra a fatura real no mês seguinte), `C_disp` a taxa de disponibilidade mensal aprovada em assembleia e `N_aderentes` o número de unidades aderentes. Os três casos excepcionais do enunciado se resolvem por construção, sem regra ad hoc:

- **Sessão interrompida** — cobra-se exatamente o kWh medido até a interrupção, com o motivo do encerramento registrado na linha da fatura; se a leitura final se perder, vale a última leitura periódica (sempre o valor mais conservador) e a sessão é sinalizada para auditoria.
- **Usuário que não carregou no mês** — paga apenas a parcela de disponibilidade, que remunera a infraestrutura mantida à disposição, não o uso; unidade que nunca aderiu não paga nada.
- **Dois veículos da mesma unidade** — a fatura é por unidade: as sessões de todas as credenciais da unidade agregam numa fatura só, com o extrato discriminando qual credencial iniciou cada sessão; a taxa de disponibilidade é única por unidade.

A justificativa completa (benchmark, três decisões embutidas na fórmula, tratamento de visitante, pro rata de adesão, virada de mês, inadimplência e o mecanismo de reconciliação tarifária em dois tempos) está na Frente 3, Opções A e C — incluindo um mês fictício inteiro calculado linha a linha.

## Papel da IA

Aplicamos a nós mesmos o critério da rubrica como teste de engenharia: **decorativo é o que se remove sem ninguém notar.** Cada abordagem precisa declarar quais campos do esquema consome, que saída produz e que decisão concreta — do gestor ou do morador — essa saída habilita. O que passou no teste:

- **Previsão de demanda e ocupação** (Sprint 2) — regressão com features de calendário e gradient boosting sobre os agregados das sessões; produz a curva prevista de 7 dias e dois alertas (saturação e aproximação do limite de potência declarada da instalação). Habilita: janelas de reserva antes do conflito, proposta de segundo carregador com estimativa de payback derivada da própria curva, e o anexo de curva de carga que a IT-41 exige na renovação do AVCB.
- **Detecção de anomalias** (Sprint 2) — fase 1 com regras estatísticas interpretáveis desde o primeiro dia, fase 2 com Isolation Forest; cada sessão encerrada é avaliada **antes do fechamento da fatura**, e a linha flagrada entra na fatura marcada para auditoria, com explicação legível. Habilita: manutenção preditiva (a resposta ao caso Copel), auditoria pré-fechamento que protege a confiança no rateio e contestação informada pelo morador. Nenhuma saída dispara punição automática — a IA produz evidência, o humano decide.
- **Clustering de perfis de uso** (especificado, implementação adiada) — k-means sobre features por credencial, com precedente de domínio forte (Helmus et al., 2020). Adiado por um motivo estatístico que preferimos declarar a maquiar: clusterizar as 10–20 unidades de um único condomínio no primeiro ano é numerologia, não aprendizado. Na Sprint 2, os perfis entram como segmentos definidos por regra dentro do simulador tarifário.

Rejeitamos do núcleo a interface conversacional (NLP), citada pelo enunciado como exemplo: não consome a telemetria, não habilita decisão que um painel bem desenhado não habilite e seu custo briga com a nossa restrição de infraestrutura — é a definição prática de IA decorativa neste produto. A posição estrutural da IA no fluxo é o traço que defendemos: ela não é um dashboard que comenta o passado, é uma **interceptação entre a sessão e o fechamento da fatura** — removê-la quebraria o próprio ciclo de estados da fatura. A escolha por métodos clássicos e interpretáveis (scikit-learn, statsmodels) é coerência com a tese do rateio: em condomínio, previsão que o síndico não consegue explicar em assembleia não embasa decisão nenhuma.

## Plano para a Sprint 2

O que será desenvolvido, na ordem em que será desenvolvido — cada etapa entrega algo testável e a seguinte constrói sobre ela. As estimativas são em **dias ativos de trabalho assistido por IA** (equipe + agentes de código), modelo que já praticamos em projetos anteriores; o prazo da Sprint 2 (20/09/2026) comporta o total com folga para as pendências externas.

| # | Etapa | O que entrega | Estimativa |
|---|---|---|---|
| 1 | Gerador de dados sintéticos | Sessões e telemetria no esquema da Frente 3-C, calibradas no dataset Kaggle/Asensio, com injeção de anomalias com gabarito | 2–3 dias |
| 2 | Ingestão + banco | Esquema de 14 entidades migrado no Postgres; gateway de ingestão com os adaptadores gerador/dataset (stub SEMS especificado) | 2 dias |
| 3 | Motor de rateio com testes | Fórmula, casos excepcionais, reconciliação em dois tempos; suíte de testes que reproduz o mês fictício do dossiê como caso de aceitação | 2–3 dias |
| 4 | Painel do gestor | Ocupação e saúde dos pontos, fila de auditoria, relatório mensal exportável | 2–3 dias |
| 5 | Módulo de IA | Previsão de demanda (curva 7 dias + alertas) e detecção de anomalias (fases 1 e 2), avaliadas contra o gabarito do gerador (erro de previsão; precisão/recall das anomalias) | 3–4 dias |
| 6 | Portal do usuário / fatura | Extrato sessão a sessão, fatura com linhas explicadas (incluindo ajuste de reconciliação), contestação | 2 dias |

Total estimado: 13–17 dias ativos. A ordem é deliberada: dados antes de tudo (nada se testa sem o gerador), o motor de rateio antes de qualquer interface (é o coração auditável do produto, e o mês fictício do dossiê já é seu teste de aceitação pronto) e a IA depois do banco populado, porque lê das mesmas tabelas que o faturamento escreve.

**Tecnologias.** Python 3.12 como linguagem única (gerador, back-end e IA no mesmo ecossistema); **PostgreSQL** como banco (o esquema da Frente 3-C já foi escrito com tipos e constraints dele); **pandas + scikit-learn + statsmodels** para o módulo de IA — métodos clássicos e interpretáveis, adequados a dados tabulares e infraestrutura modesta sem GPU, decisão justificada na Frente 3-B. Para o framework web, duas candidatas que a equipe decidirá no início da Sprint 2: **Django** (admin pronto, autenticação e ORM com migrações maduras — acelera painel e portal, e a equipe tem experiência) ou **FastAPI** (mais leve, tipagem nativa do contrato de ingestão — atraente se optarmos por separar o serviço de ingestão do app). A inclinação atual é Django pela velocidade nas etapas 4 e 6, que são as mais ricas em interface; registramos a alternativa porque a escolha honesta se faz com o esqueleto do código na mão, não antes.

**Pendências e radar** (itens que não bloqueiam o início): chave gratuita da Open Charge Map (registro de conta, minutos); validação do tratamento de tributos do rateio com administradora e contador; visita ao Energy Innovation Lab para verificar o modelo exato do HCA G2 instalado e, se viável, capturar dado real; conclusão e incorporação das entrevistas da Frente 1-B; acompanhamento da Consulta Pública ANEEL 42/2025 e do decreto regulamentador da Lei 18.403/2026.

## Uso de inteligência artificial

A equipe usou assistentes de IA (Claude) como ferramenta de pesquisa e redação ao longo de toda a Sprint 1, sob direção e revisão humana. Toda fonte citada neste README e nos dossiês foi efetivamente acessada e verificada — o método de cada seção (texto oficial baixado do site do órgão, chamada real de API com resposta preservada, leitura íntegra de datasheet e manual) está declarado nos blocos "Método" no início das seções dos dossiês, e nenhuma referência entrou nas listas sem acesso confirmado.

As análises, escolhas e conclusões são da equipe: a seleção das opções de aprofundamento em cada frente, a decisão de transformar a indisponibilidade da API SEMS (Opção 2-B) em decisão arquitetural, o modelo híbrido de rateio, o adiamento do clustering por honestidade estatística e a rejeição da interface conversacional no núcleo da solução. Os artefatos de planejamento do processo (especificação de design e plano de execução da sprint) estão em [docs/superpowers/](docs/superpowers/), por transparência sobre como a colaboração entre equipe e IA funcionou na prática.

## Fontes

Todas as fontes abaixo foram efetivamente consultadas pela equipe, com acesso verificado em **2026-06-09** (salvo data indicada na própria entrada). A lista consolida, sem perdas e sem duplicatas, as fontes dos três dossiês — cada dossiê mantém a sua lista própria com o contexto de uso de cada fonte. Textos normativos oficiais estão preservados em [docs/normas/](docs/normas/); as evidências brutas das chamadas de API estão versionadas em [data/](data/README.md) (os datasets grandes ficam fora do repositório e são regeneráveis via notebook ou pelos comandos do README de `data/`).

### Normas e textos legais (fonte primária)

1. ANEEL — Resolução Normativa nº 1.000, de 7/12/2021, texto integral original. DOU 20/12/2021. https://www.in.gov.br/en/web/dou/-/resolucao-normativa-aneel-n-1.000-de-7-de-dezembro-de-2021-368359651
2. ANEEL — REN 1.000/2021, texto consolidado oficial (captura de 29/09/2025). https://www2.aneel.gov.br/cedoc/ren20211000.html
3. ANEEL — Resolução Normativa nº 819, de 19/06/2018 (revogada pela REN 1.000/2021), texto integral original. DOU 05/07/2018. https://www.in.gov.br/materia/-/asset_publisher/Kujrw0TZC2Mb/content/id/28737289/do1-2018-07-05-resolucao-normativa-n-819-de-19-de-junho-de-2018-28737273
4. ANEEL — notícia oficial sobre a Consulta Pública nº 42/2025 (regras de conexão de eletromobilidade), 09/12/2025. https://www.gov.br/aneel/pt-br/assuntos/noticias/2025/aneel-abre-consulta-publica-para-aprimorar-regras-de-conexao-de-eletromobilidade-a-rede-eletrica
5. ANEEL — página oficial "Veículos Elétricos" (REN 819/2018 e REN 1.000/2021, preços livremente negociados). https://www.gov.br/aneel/pt-br/assuntos/veiculos-eletricos
6. ALESP — Lei nº 18.403, de 18/02/2026 (texto retificado em 20/02/2026). https://www.al.sp.gov.br/repositorio/legislacao/lei/2026/lei-18403-18.02.2026.html
7. Prefeitura de São Paulo — Lei nº 17.336, de 30/03/2020. https://legislacao.prefeitura.sp.gov.br/leis/lei-17336-de-30-de-marco-de-2020
8. CBPMESP — Portaria nº CCB-008/800/2025, de 12/11/2025 (consulta pública da alteração da IT-41). https://cbaplang.corpodebombeiros.sp.gov.br/Midias/638986232326891879.pdf
9. CBPMESP — Portaria nº CCB-009/800/2025, de 12/11/2025 (Parecer Técnico nº CCB-001/800/25 sobre SAVE). https://cbaplang.corpodebombeiros.sp.gov.br/Midias/638986232512702533.pdf
10. CBPMESP / DOE-SP — Portaria nº CCB-003/970/2026, de 17/03/2026 (atualiza a IT-41, itens 5.2–5.12). https://doe.sp.gov.br/executivo/secretaria-da-seguranca-publica/portaria-n-003-970-2026-de-17-de-marco-de-2026-20260316113816712141709068

### Dados públicos e APIs oficiais

11. ABVE — "Eletrificados crescem dez vezes mais do que o conjunto do mercado, e vendas chegam a 224 mil veículos em 2025". https://abve.org.br/eletrificados-crescem-dez-vezes-mais-do-que-conjunto-do-mercado-em-2025-com-224-mil-veiculos-vendidos/
12. ABVE — "Eletrificados batem todas as previsões em 2021". https://abve.org.br/eletrificados-batem-todas-as-previsoes-em-2021/
13. ABVE — "Recarga pública rápida cresce 167% em um ano e chega a 31% dos 21 mil eletropostos da rede". https://abve.org.br/recarga-publica-rapida-cresce-167-em-12-meses-e-ja-atinge-31-dos-21-mil-eletropostos-da-rede/
14. ANEEL Dados Abertos (CKAN) — API `package_search` e `datastore_search`, chamadas reais sobre o recurso de tarifas. https://dadosabertos.aneel.gov.br/api/3/action/package_search?q=tarifa
15. ANEEL Dados Abertos — dataset "Tarifas de aplicação das distribuidoras de energia elétrica". https://dadosabertos.aneel.gov.br/dataset/tarifas-distribuidoras-energia-eletrica
16. IBGE — API de localidades, lista oficial dos 5.571 municípios. https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado
17. Open Charge Map — API `GET /v3/poi` (chamada real sem chave, HTTP 403 documentado). https://api.openchargemap.io/v3/poi
18. Open Charge Map — especificação OpenAPI oficial da API v3. https://raw.githubusercontent.com/openchargemap/ocm-docs/master/Model/schema/ocm-openapi-spec.yaml
19. Open Charge Map — espelho oficial de dados `ocm-export` (1.298 pontos no Brasil). https://github.com/openchargemap/ocm-export
20. Google — Places API (New), referência REST do recurso `Place` (campo `evChargeOptions`; somente documental). https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places
21. CKAN — documentação oficial da Datastore API. https://docs.ckan.org/en/latest/maintaining/datastore.html

### Fabricantes, equipamentos e documentação técnica

22. GoodWe Brasil — Datasheet "Linha HCA G2 — Carregador CA" (PT, 20241121-V2.1). https://br.goodwe.com/Ftp/Downloads/Datasheet/PT/GW_HCA-G2_Datasheet-PT.pdf
23. GoodWe — Datasheet "HCA G2 Series EV Charger" (EN). https://en.goodwe.com/Ftp/EN/Downloads/Datasheet/GW_HCA-G2_Datasheet-EN.pdf
24. GoodWe — "User Manual AC Charger HCA Series (7-22kW) G2", V1.5-2025-11-11 (69 p.). https://en.goodwe.com/download-hca-g2-series
25. GoodWe — página de produto "HCA G2 Series AC Charger". https://en.goodwe.com/hca-g2
26. GoodWe Solar Academy — "GoodWe API Technical Document", SA-B-20240814-001 (PUBLIC). https://community.goodwe.com/static/images/2024-08-20597794.pdf
27. GoodWe Solar Academy — "API Introduction", SA-E-20221031-001. https://community.goodwe.com/static/images/2022-11-08281223.pdf
28. TimSoethout — `goodwe-sems-home-assistant` (integração comunitária com o SEMS API). https://github.com/TimSoethout/goodwe-sems-home-assistant
29. WolfrageTV — `goodwe-wallbox-sems-gen2-fixed` (integração comunitária específica para wallboxes HCA G2). https://github.com/WolfrageTV/goodwe-wallbox-sems-gen2-fixed
30. Solytic — "Set up API access – GoodWe SEMS API" (rito de credenciamento). https://solytic.com/knowledge/set-up-api-access-goodwe-sems-api/
31. Zaptec — "Zaptec Pro". https://www.zaptec.com/charging-solutions/business-and-commercial/zaptec-pro
32. Zaptec Docs — "OCPP within Zaptec". https://docs.zaptec.com/docs/ocpp-within-zaptec
33. ChargePoint — "EV Charging Solutions for Condo Managers and HOAs". https://www.chargepoint.com/solutions/condos
34. NeoCharge — "Plataforma de Gestão de Recarga". https://www.neocharge.com.br/plataforma-gestao-recarga
35. NeoCharge — "Carregador para Carro Elétrico em Prédios e Condomínios". https://www.neocharge.com.br/tudo-sobre/carregador-carro-eletrico-predio-condominio-instalacao
36. WEG — "WEMOB | Eletrifique o seu condomínio" (rateio na plataforma, cobrança no boleto). https://materiais.wegdigital.weg.net/weg-digital-wemob-condominios-canais
37. EZVolt — "Condomínios Residenciais" (modelo turn-key). https://ezvolt.com.br/solucao/condominios-residenciais/
38. Governo do Paraná (AEN) — "Copel coloca em operação seu primeiro eletroposto com carregador ultrarrápido". https://www.parana.pr.gov.br/aen/Noticia/Copel-coloca-em-operacao-seu-primeiro-eletroposto-com-carregador-ultrarrapido
39. App Store — "Eletroposto Fácil" (Copel). https://apps.apple.com/br/app/eletroposto-f%C3%A1cil/id1610189111
40. OCPP.md — "OCPP 1.6J — Open Charge Point Protocol (JSON over WebSocket)". https://ocpp.md/ocpp-1.6j/
41. Monta — "IEC 61851: Definition, scope, and role in EV charging". https://monta.com/en/blog/iec-61851/
42. HDT Electronic — "How does EVSE work? What are control pilot and proximity contact signals?" (estados A/B/C e PWM do Control Pilot). https://www.hdt-electronic.com/en/faq/how-does-evse-work-what-are-control-pilot-and-proximity-contact-signals/
43. Typhoon HIL — "Electric vehicle charging according to standard IEC 62196 – mode 3" (duty cycle → corrente máxima). https://www.typhoon-hil.com/documentation/typhoon-hil-application-notes/References/electric_vehicle_ac_charging.html
44. Monta — "ISO 15118: Definition, key features, benefits, adoption, and compliance" (Plug & Charge, V2G). https://monta.com/en/blog/iso-15118/

### Acadêmicas, datasets e bibliotecas

45. Kaggle — "Electric Vehicle Charging Dataset" (Michael Bryant; reempacotamento do dado de Asensio et al.). https://www.kaggle.com/datasets/michaelbryantds/electric-vehicle-charging-dataset
46. Asensio, O. I.; Lawson, M. C.; Apablaza, C. Z. — "Electric vehicle charging stations in the workplace with high-resolution data from casual and habitual users". Scientific Data, v. 8, art. 168, 2021. https://pmc.ncbi.nlm.nih.gov/articles/PMC8263557/ — DOI: https://doi.org/10.1038/s41597-021-00956-1
47. Harvard Dataverse — depósito primário do dataset de Asensio et al. https://doi.org/10.7910/DVN/QF1PMO
48. Helmus, J. R.; Lees, M. H.; van den Hoed, R. — "A data driven typology of electric vehicle user types and charging sessions". Transportation Research Part C, v. 115, 2020. https://research.hva.nl/en/publications/a-data-driven-typology-of-electric-vehicle-user-types-and-chargin/ — DOI: https://doi.org/10.1016/j.trc.2020.102637
49. scikit-learn — exemplo oficial "Time-related feature engineering". https://scikit-learn.org/stable/auto_examples/applications/plot_cyclical_feature_engineering.html
50. scikit-learn — guia do usuário "Clustering". https://scikit-learn.org/stable/modules/clustering.html
51. scikit-learn — referência da API `sklearn.ensemble.IsolationForest`. https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html
52. scikit-learn — guia do usuário "Novelty and Outlier Detection". https://scikit-learn.org/stable/modules/outlier_detection.html
53. statsmodels — documentação oficial do módulo de séries temporais `statsmodels.tsa`. https://www.statsmodels.org/stable/tsa.html

### Mercado e imprensa especializada

54. Migalhas — "Lei 18.403/26 de SP: Recarga de veículos elétricos em condomínios". https://www.migalhas.com.br/coluna/migalhas-edilicias/452093/lei-18-403-26-de-sp-recarga-de-veiculos-eletricos-em-condominios
55. MyCond — "Desafios para Carregadores de Carros Elétricos em Condomínios". https://mycond.com.br/desafios-para-carregadores-de-carros-eletricos-em-condominios/
56. Lello Condomínios — "Veículos elétricos em condomínios: o que diz a legislação". https://www.lellocondominios.com.br/veiculos-eletricos-em-condominios-o-que-diz-a-legislacao-como-instalar-e-quais-cuidados-os-sindicos-precisam-ter/
57. Power2Go — "Condomínios: carregadores individuais ou compartilhados?". https://www.power2go.com.br/post/condom%C3%ADnios-carregadores-individuais-ou-compartilhados
58. Carregados — "Quanto custa para carregar um carro elétrico no Brasil?". https://carregados.com.br/quanto-custa-para-carregar-um-carro-eletrico
59. GreenV — "Eletroposto: o que é, como funciona e quanto custa abastecer". https://www.greenv.com.br/blog/eletroposto-o-que-e-como-funciona-e-quanto-custa-abastecer/
60. Zletric — "Zletric e VoltBras criam rede com mais de 2.500 eletropostos interoperáveis no Brasil". https://www.zletric.com.br/post/zletric-e-voltbras-criam-rede-com-mais-de-2500-eletropostos-interoperaveis-no-brasil
61. CanalVE — "Como funciona o protocolo OCPP na recarga de carros elétricos?". https://canalve.com.br/como-funciona-o-protocolo-ocpp-nas-recargas-de-carros-eletricos/
62. EV Connect — "New ChargePoint Fees: What's Changing and Who Pays More". https://www.evconnect.com/blog/chargepoint-raises-fees-in-2026/
63. Ambare — "Carregamento compartilhado em condomínios: como funciona e quem paga a conta?". https://ambare.com.br/carregamento-compartilhado-em-condominios-como-funciona-e-quem-paga-a-conta/
64. CondoCash — "Carregador de carro elétrico em condomínio: instalação, custos e rateio". https://condocash.com.br/carregador-de-carro-eletrico-em-condominio-instalacao-custos-e-rateio/
65. Fecombustíveis (reprodução de O Globo) — "Venda de carros eletrificados no Brasil cresce 91% em 2023". https://www.fecombustiveis.org.br/noticia/venda-de-carros-eletrificados-no-brasil-cresce-91-em-2023-e-atinge-939-mil-emplacamentos/255655
66. ClimaInfo — "Pontos de recarga de VEs crescem 59% no Brasil, mas distribuição é desigual". https://climainfo.org.br/2025/09/18/pontos-de-recarga-de-ves-crescem-59-no-brasil-mas-distribuicao-e-desigual/
67. Latam Mobility — "O Brasil alcança 16.880 pontos de recarga públicos e semipúblicos". https://latamobility.com/pt-br/o-brasil-alcanca-16-880-pontos-de-recarga-publicos-e-semipublicos-para-veiculos-eletricos/
68. AutoIndústria — "A nova geografia da recarga elétrica no Brasil". https://www.autoindustria.com.br/2026/02/24/a-nova-geografia-da-recarga-eletrica-no-brasil/
69. Aranda/FotoVolt — "Aneel abre consulta para regras de recarga de veículos elétricos". https://www.arandanet.com.br/revista/fotovolt/noticia/12147-Aneel-abre-consulta-para-regras-de-recarga-de-veiculos-eletricos.html
70. Agência SP — "Corpo de Bombeiros de SP divulga novas regras de segurança para recarga de carros elétricos no estado". https://www.agenciasp.sp.gov.br/corpo-de-bombeiros-de-sp-divulga-novas-regras-de-seguranca-para-recarga-de-carros-eletricos-no-estado/

### Organismos internacionais

71. IEA — *Global EV Outlook 2025*, cap. 6 "Electric vehicle charging" — "Home charging remains the most popular way to charge for EV owners" (p. 98); mais de 85% dos donos de EV nos EUA têm acesso a recarga residencial (p. 115). Acesso em 2026-06-10. https://www.iea.org/reports/global-ev-outlook-2025/electric-vehicle-charging · PDF íntegro: https://iea.blob.core.windows.net/assets/7ea38b60-3033-42a6-9589-71134f4229f4/GlobalEVOutlook2025.pdf
