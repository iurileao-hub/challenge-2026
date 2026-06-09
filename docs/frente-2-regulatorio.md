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
<!-- a preencher -->

## API GoodWe SEMS Portal (documentação pública)
<!-- a preencher -->

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
