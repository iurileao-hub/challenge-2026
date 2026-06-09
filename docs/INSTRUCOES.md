# Enterprise Challenge 2026 — EV ChargeOps (FIAP × GoodWe)

> Instruções oficiais do projeto. Documento de referência para a equipe.

## 1. Divisão do Projeto

O Enterprise Challenge 2026 será desenvolvido em duas sprints:

- **Sprint 01 — Pesquisa e documentação**: a equipe investiga o problema, mapeia o contexto técnico e regulatório, define a arquitetura da solução e documenta as decisões que guiarão o desenvolvimento. **Prazo: 21/06/2026.**
- **Sprint 02 — Desenvolvimento e prototipação**: a equipe implementa a solução com base no que foi definido na sprint 01. **Prazo: 20/09/2026.**

> **Importante:** no 2º semestre de 2026, durante a prova presencial obrigatória que você agendará, cada aluno deverá gravar um **vídeo pitch de 3 minutos** do seu projeto. Esse será o momento de validar o desenvolvimento técnico do desafio e habilitar o lançamento das notas. As notas das sprints só aparecerão no boletim após a validação técnica do vídeo pitch.

## 2. Contexto do Desafio

A **GoodWe** é uma das maiores fabricantes globais de inversores e sistemas de armazenamento de energia, com presença em mais de 100 países e capacidade instalada acumulada superior a 100 GW. No Brasil, a empresa mantém parceria com a FIAP por meio do **Energy Innovation Lab** — Unidade 2, Aclimação — onde opera um carregador de veículos elétricos (modelo **HCA G2**) instalado no estacionamento L1.

O crescimento acelerado de veículos elétricos impõe um problema operacional concreto: infraestruturas de recarga compartilhadas, em condomínios residenciais, edifícios corporativos e campus universitários, não dispõem de mecanismos integrados para estruturar sessões por usuário, calcular consumo individual, aplicar regras de rateio justas e oferecer uma experiência digital clara para moradores e gestores.

Cada sessão de recarga produz dados úteis: duração, volume de energia entregue (kWh), horário de uso, frequência, picos e intervalos de ociosidade. Quando organizados, esses dados deixam de ser simples registros e passam a funcionar como base de inteligência operacional. O **EV ChargeOps** propõe exatamente essa transformação, com inteligência artificial como motor lógico da solução.

**Pergunta central:**

> Como transformar sessões de recarga de veículos elétricos em uma infraestrutura compartilhada em dados estruturados, rateio justo e inteligência acionável?

## 3. O Que a Equipe Deve Fazer?

Sua missão agora é desenvolver a primeira sprint, que é composta por **três frentes de pesquisa**. Em cada uma, a equipe escolhe ao menos uma opção de aprofundamento, pesquisa com afinco e documenta os resultados com análise própria.

**Prioridade da sprint 1: pesquisa e documentação.** Essa sprint não exige entrega de código funcional. O foco é compreender o problema, mapear o ecossistema técnico e regulatório e documentar as decisões que vão guiar o desenvolvimento na sprint 02. Grupos que queiram iniciar implementações ou experimentos de código podem fazê-lo, desde que isso não substitua a documentação, que é o entregável obrigatório dessa etapa.

## 4. Frente 1 — Contexto e Problema

Pesquise e documente:

- O que são infraestruturas de recarga compartilhada e quais são os principais desafios operacionais enfrentados por gestores de condomínios, edifícios corporativos ou campus universitários;
- Como funciona uma sessão de recarga do ponto de vista técnico: o que acontece entre o momento em que o veículo é conectado e o encerramento da sessão, quais dados são gerados e como podem ser capturados;
- Quais modelos de negócio existem para recarga compartilhada no Brasil e no mundo: recarga gratuita, cobrança por kWh, cobrança por tempo, assinatura mensal ou rateio condominial.

### 4.1 Opções de aprofundamento — escolha ao menos uma

- **Opção A — Análise de mercado:** mapeie ao menos 3 soluções existentes que resolvem problemas similares ao EV ChargeOps. Para cada uma, destaque: o problema que resolve, as funcionalidades principais, o modelo de negócio e as limitações conhecidas. Referências: Zaptec, Wallbox Pulsar Plus, ChargePoint, Neocharge e Copel Telecom EV;
- **Opção B — Pesquisa com usuários:** elabore um roteiro de perguntas e aplique com ao menos 3 pessoas que sejam ou possam ser usuárias da solução (moradores de condomínio, gestores de estacionamento ou motoristas de EV). Documente as respostas e extraia ao menos 5 insights que influenciem o design da solução;
- **Opção C — Análise de dados públicos:** pesquise e analise dados sobre o crescimento da frota de veículos elétricos no Brasil, distribuição de pontos de recarga e perfis de uso.

## 5. Frente 2 — Base Regulatória e Técnica

Pesquise e documente:

- **Resolução normativa ANEEL nº 1.000/2021:** exploração comercial da recarga, comunicação prévia à distribuidora e exigência de protocolos abertos de comunicação para equipamentos não exclusivos de uso privado;
- **Carregador GoodWe HCA G2:** interfaces RS-485, LAN, Wi-Fi, Bluetooth e RFID — o que cada uma permite fazer e como podem ser utilizadas pela plataforma;
- **API GoodWe (SEMS Portal):** quais dados ela expõe sobre o carregador, como status, potência, energia entregue e eventos de sessão.

### 5.1 Opções de aprofundamento — escolha ao menos uma

- **Opção A — Mapeamento regulatório completo:** além da RN 1.000/2021, verifique se existem normas estaduais, municipais ou resoluções complementares da ANEEL que impactem a operação de carregadores compartilhados em São Paulo. Avalie se a solução proposta estaria em conformidade;
- **Opção B — Exploração da API GoodWe:** acesse a documentação pública da API SEMS e documente os endpoints disponíveis, os campos retornados para dados de carregamento, o formato dos dados (JSON) e como eles poderiam alimentar a plataforma EV ChargeOps;
- **Opção C — Mapeamento de APIs complementares:** pesquise e documente ao menos duas APIs externas que poderiam enriquecer a plataforma. Sugestões: Open Charge Map API, Google Places API (campo `evChargeOptions`), ANEEL Open Data e IBGE.

## 6. Frente 3 — Arquitetura e IA

Pesquise e documente:

- Quais são as **camadas da plataforma EV ChargeOps**: física (carregador), conectividade (rede e protocolos), aplicação (back-end, regras de negócio e IA) e apresentação (interfaces do gestor e do usuário);
- Como os **dados fluem** da sessão de recarga até a fatura do usuário: qual é o caminho completo, quais transformações ocorrem e onde a IA entra nesse fluxo;
- Qual é o **modelo de rateio** que a equipe propõe: quais variáveis serão usadas, como a fatura individual será calculada e como o modelo lida com casos excepcionais (sessão interrompida, usuário que não carregou no mês ou dois veículos da mesma unidade).

### 6.1 Opções de aprofundamento — escolha ao menos uma

- **Opção A — Benchmarking de modelos de rateio:** pesquise como condomínios que já implantaram carregadores compartilhados estruturam o rateio de energia. Identifique ao menos dois modelos distintos, compare suas vantagens e limitações e justifique qual a equipe adotará;
- **Opção B — Definição do papel da IA:** pesquise e documente ao menos duas abordagens de IA aplicáveis ao problema. Para cada uma, destaque o problema que resolve, a técnica envolvida, os dados necessários e o impacto esperado. Exemplos: regressão para previsão de consumo, clustering para perfis de uso, NLP para interface conversacional, detecção de anomalias, entre outros;
- **Opção C — Esquema da base de dados:** defina e documente o esquema de dados da plataforma, como entidades (usuário, unidade, sessão e fatura), atributos, relacionamentos e exemplos de registros simulados que serão usados na sprint 02.

## 7. Bases de Dados e Fontes Sugeridas

### 7.1 Frota e infraestrutura no Brasil

- **ABVE** — Estatísticas de emplacamentos de veículos elétricos: [abve.org.br](https://abve.org.br)
- **ANEEL Open Data** — Dados de concessão e infraestrutura elétrica: [dadosabertos.aneel.gov.br](https://dadosabertos.aneel.gov.br)
- **SENATRAN / DENATRAN** — Frota nacional por categoria e combustível
- **IBGE** — Dados de domicílios e distribuição geográfica

### 7.2 Localização de pontos de recarga

- **Open Charge Map**: [openchargemap.org/site/develop](https://openchargemap.org/site/develop)
- **PlugShare** — Avaliações e uso de pontos de recarga
- **ANEEL** — Mapa de pontos cadastrados no Brasil

### 7.3 APIs técnicas

- **GoodWe SEMS Portal API**: [semsplus.goodwe.com](https://semsplus.goodwe.com/)
- **Google Places API** — Campo `evChargeOptions`: [developers.google.com/maps/documentation/places](https://developers.google.com/maps/documentation/places)
- **Open Charge Map API** — Endpoints REST com dados de estações

### 7.4 Sugestões de datasets para modelagem

- **Kaggle** — "Electric Vehicle Charging Sessions": dataset com registros reais de sessões de recarga de frota corporativa nos EUA
- **UCI Machine Learning Repository** — Datasets de consumo energético residencial e industrial

## 8. Sobre o Uso de Inteligência Artificial

O uso de ferramentas de IA para apoiar a pesquisa, organizar ideias e redigir partes do documento é **permitido e incentivado**. Ferramentas como ChatGPT, Claude, Gemini e similares podem ser aliadas na estruturação do raciocínio, na sugestão de fontes e na revisão da escrita.

No entanto, o trabalho entregue deve ser **autoral**. Isso significa que:

- A análise, as escolhas e as conclusões devem refletir o pensamento da equipe, não respostas copiadas de um modelo;
- Toda fonte citada deve ter sido efetivamente consultada. Referências geradas por IA sem verificação não são aceitas;
- A solução proposta — arquitetura, modelo de rateio e papel da IA — deve ser uma construção da equipe, não um template genérico.

> Um trabalho que usa IA com inteligência é diferente de um trabalho que foi gerado por IA sem leitura crítica. A avaliação reconhece essa diferença.

## 9. Entregável

O entregável dessa sprint deve ser um arquivo **.TXT contendo o link do repositório do grupo**. O repositório deve conter um **README.md bem elaborado**, que funcione como o documento central de pesquisa e proposta da equipe.

### 9.1 O que o README deve conter

- Nome da equipe e RMs dos integrantes;
- Descrição do problema e do contexto do desafio;
- Resultado das três frentes de pesquisa, com as opções de aprofundamento escolhidas documentadas;
- Diagrama de arquitetura da solução proposta;
- Modelo de rateio definido, com critérios e variáveis;
- Papel da IA na solução;
- Plano para a sprint 02: o que será desenvolvido, em qual ordem e com quais tecnologias.

### 9.2 Orientações para o README

- Escreva em português claro e direto;
- Use títulos, subtítulos e listas apenas onde é necessário para ajudar a organizar a leitura;
- Evite o uso excessivo de emojis, pois um README técnico não precisa deles;
- Inclua o diagrama de arquitetura como imagem no repositório e referencie-o no README;
- Cite todas as fontes consultadas ao final do documento.

## 10. Rubrica de Avaliação

| Critério | Nota |
|---|---|
| O problema é descrito com clareza e embasado em pesquisa. | 0 – 2,0 |
| As três frentes de pesquisa estão documentadas com análise própria. | 0 – 3,0 |
| A arquitetura e o modelo de rateio estão definidos e justificados. | 0 – 2,0 |
| O papel da IA na solução está claro e é estrutural, não decorativo. | 0 – 1,5 |
| O README é bem-organizado, claro e reflete autoria da equipe. | 0 – 1,5 |
| **Total** | **0 – 10,0** |

*Tabela 1 — Critérios de avaliação. Fonte: Elaborada pelo autor (2026).*
