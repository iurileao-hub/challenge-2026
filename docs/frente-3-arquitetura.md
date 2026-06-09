# Frente 3 — Arquitetura e IA

## Camadas da plataforma
<!-- a preencher -->

## Fluxo de dados: da sessão à fatura
<!-- a preencher -->

## Opção A — Benchmark e modelo de rateio

> **Método.** Esta seção responde à exigência central do enunciado: o modelo de rateio da equipe, com as variáveis usadas, o cálculo da fatura individual e o tratamento dos casos excepcionais. Antes de definir, benchmarkamos como condomínios reais estruturam a cobrança hoje — fontes acessadas em 2026-06-09, com remissão às Frentes 1 e 2 para o que já está documentado lá (modelos de negócio, REN 1.000, Lei 17.336, tarifa Enel SP).

### Benchmark — como o mercado rateia hoje

A taxonomia de cinco modelos de monetização já está na Frente 1 (Modelos de negócio); aqui o recorte é outro: **como soluções reais operam o rateio dentro de condomínios**. Quatro arranjos distintos, cada um com pelo menos um praticante identificado:

**1. kWh medido por usuário, repassado no boleto condominial (WEG WEMOB e NeoCharge, Brasil).** O morador se identifica no carregador (cartão RFID ou app), a estação mede a energia de cada recarga e a plataforma consolida o consumo do mês. Na WEMOB, *"pode ser realizado o rateio de consumo, adicionados os custos no boleto do condomínio e enviada a cobrança via cartão de crédito ou cartão RFID"* [WEG WEMOB, 2026] — ou seja, o repasse usa o trilho de cobrança que o condomínio já tem. A NeoCharge descreve o mesmo desenho: medir *"quanto cada morador utilizou de energia"* e dividir ao final do mês (detalhada na Frente 1, Opção A). É o modelo dominante entre os players brasileiros de condomínio.

**2. Cobrança direta pelo operador, com reembolso ao condomínio (ChargePoint, EUA).** O operador fatura o morador diretamente (*"bill residents directly for their energy usage"*) e devolve ao condomínio o custo da energia (*"reimburse you for your out-of-pocket electricity costs"*), com preço definido pelo gestor por grupo de usuário (morador, visitante) [ChargePoint, 2026]. O condomínio sai do fluxo financeiro — atraente para o síndico, mas a engenharia de reembolso pressupõe o sistema de pagamentos norte-americano (limitação já registrada na Frente 1, Opção A).

**3. Concessão interna: a empresa investe e cobra tarifa própria por kWh (EZVolt, Brasil).** No modelo *turn-key* da EZVolt para condomínios residenciais, *"todo o investimento é feito pela Easy Volt"*; o morador paga a recarga pelo app, com *"tarifas de carregamento personalizadas"*, e o condomínio pode até receber participação na receita [EZVolt, 2026]. O CAPEX zero tem preço: a tarifa por kWh embute o retorno do investimento da empresa e fica tipicamente bem acima do custo da energia da distribuidora — o condômino paga preço de eletroposto na própria garagem.

**4. Taxa fixa mensal por unidade aderente.** Documentado como prática corrente em material de mercado: *"todos os usuários pagam uma taxa, independentemente do uso"* [Ambare, 2026]. Aparece também na variante contratual de mensalidade fixa de manutenção do equipamento (*"é acordado um valor mensal para manutenção"*) [CondoCash, 2026]. Simples de administrar (não exige medição por usuário), mas dissociado do consumo. A primeira fonte registra a degeneração desse caminho — diluir tudo na cota condominial — como *"pouco recomendado, pois moradores que não usam o serviço acabam pagando por ele"* [Ambare, 2026]. Há ainda a cobrança **por tempo de ocupação** (totem que mede tempo conectado), registrada como alternativa para prédios sem medição individual, mas *"um método um pouco mais impreciso"* [CondoCash, 2026] — e a Frente 1 já mostrou, no caso Copel, que cobrar minuto penaliza quem carrega mais devagar.

| Modelo | Praticante real | Vantagens | Limitações |
|---|---|---|---|
| kWh medido + boleto condominial | WEG WEMOB, NeoCharge (BR) | Justiça por consumo; atende a medição individualizada da Lei 17.336; usa o trilho de cobrança existente | Exige identificação por sessão e plataforma de gestão; custos fixos ficam sem dono se não houver taxa complementar |
| Cobrança direta + reembolso | ChargePoint (EUA) | Síndico fora do fluxo financeiro; inadimplência é problema do operador | Não opera no BR; reembolso pressupõe outro sistema financeiro; taxa de serviço por sessão repassada ao morador |
| Concessão interna (kWh com margem) | EZVolt (BR) | CAPEX zero para o condomínio; operação e manutenção terceirizadas | Tarifa final muito acima do custo da energia; lock-in contratual com o operador; menos transparência de formação de preço |
| Taxa fixa por unidade | prática de mercado [Ambare, 2026; CondoCash, 2026] | Simplicidade administrativa; receita previsível | Injusta com quem usa pouco; subsidia quem usa muito; não atende ao espírito de medição individualizada da Lei 17.336 |

Duas convergências do benchmark orientam a decisão:

- (i) todos os modelos com medição tratam o **kWh como base da cobrança variável** — ninguém rateia energia por fração ideal ou por tempo quando há medição disponível;
- (ii) os custos **fixos** (manutenção, plataforma, depreciação) são o ponto cego do modelo kWh puro — ou são empurrados para a margem de um operador (modelos 2 e 3), ou ficam órfãos e acabam diluídos na cota condominial, recriando o subsídio cruzado que o rateio veio eliminar.

### O modelo do EV ChargeOps: kWh medido por sessão + taxa de disponibilidade

**Decisão da equipe**, validada pelo benchmark: modelo **híbrido em duas parcelas**, faturado mensalmente por unidade condominial.

- **Parcela variável** — a energia de cada sessão atribuída à unidade, ao preço de repasse da distribuidora. Quem carrega paga o que consumiu, ao custo, sem margem.
- **Parcela fixa** — uma taxa de disponibilidade rateada igualmente entre as unidades **aderentes** ao programa de recarga (não entre todas as unidades do condomínio), cobrindo os custos fixos de manter o serviço disponível.

A fatura mensal da unidade `u` no mês `M`:

```
fatura_u = sum(round2(kwh_s × tarifa_s) for s in S_u) + round2(C_disp / N_aderentes)
```

| Variável | Unidade | Definição | Origem do dado |
|---|---|---|---|
| `S_u` | conjunto | Sessões encerradas no mês `M` atribuídas a credenciais da unidade `u` (sessão pertence ao mês do seu **início**) | Eventos de sessão (modelo OCPP da Frente 1: StartTransaction → StopTransaction) + vínculo credencial → unidade no cadastro |
| `kwh_s` | kWh (3 casas) | Energia entregue na sessão `s` | `meterStop − meterStart` do carregador; preferência por medidor certificado quando presente (campo `measurement_source` da Frente 2) |
| `tarifa_s` | R$/kWh (4 casas) | Tarifa de repasse **vigente na data de início** de `s`, gravada na sessão no momento do encerramento (snapshot, imune a reajuste retroativo) | Tarifa homologada ANEEL da distribuidora do condomínio (dossiê da Frente 2, seção "Opção C — APIs complementares") + tratamento de tributos (decisão pendente abaixo) |
| `C_disp` | R$/mês | Taxa de disponibilidade total do mês — o orçamento fixo do serviço | Valor aprovado em assembleia, cadastrado por condomínio |
| `N_aderentes` | inteiro ≥ 1 | Unidades aderentes ao programa no mês `M` | Cadastro de adesão por unidade |
| `round2` | — | Arredondamento a centavos, meio-para-cima (half-up), aplicado **por linha da fatura** | Regra do motor de faturamento |

Três decisões da equipe embutidas na fórmula, com justificativa:

1. **O que a taxa de disponibilidade cobre.** *Decisão da equipe:* o OPEX recorrente do serviço — manutenção preventiva/corretiva, assinatura da plataforma e um fundo de reposição do equipamento (depreciação) — e **não** o CAPEX da instalação inicial, que é decisão de obra da assembleia e segue as regras condominiais gerais (a Lei 18.403/2026 silencia sobre rateio de obras coletivas, lacuna registrada na Frente 1). Racional: sem a taxa, o custo fixo migra para a parcela variável (penalizando o uso) ou para a cota de todos (recriando o subsídio cruzado); com ela, quem reserva o direito de usar a infraestrutura paga por mantê-la disponível.
2. **Tributos (decisão pendente de validação externa).** A tarifa homologada da ANEEL vem **sem tributos** — para a Enel SP, grupo B3 convencional, TUSD + TE = R$ 725,18/MWh ≈ R$ 0,7252/kWh, vigente até 03/07/2026 (verificada por chamada real no dossiê da Frente 2, seção "Opção C — APIs complementares") — enquanto a fatura que o condomínio efetivamente paga embute ICMS e PIS/COFINS. *Posição preliminar da equipe:* usar como `tarifa_s` o **R$/kWh efetivo da fatura do condomínio** (total da fatura ÷ kWh faturados), porque garante repasse exato do custo, sem lucro nem prejuízo para o condomínio — o desenho de reembolso de custo é também o que mantém o rateio fora da zona cinzenta tributária ISS×ICMS deixada em aberto na Frente 2 (Análise da equipe da Opção A): repasse sem margem não é venda de energia nem prestação onerosa de serviço de recarga. A alternativa (tarifa homologada + tributos parametrizados) é mais auditável linha a linha, mas pode divergir da fatura real (bandeiras tarifárias, por exemplo).

   > **Pendência para a Sprint 2:** validar com administradora e contador antes da Sprint 2.
3. **Arredondamento.** Half-up a centavos por linha (cada sessão e a taxa viram linhas independentes da fatura). O resíduo do rateio da taxa (`C_disp` pode não ser divisível por `N_aderentes` em centavos exatos) fica com o caixa do condomínio — diferença máxima de centavos, declarada no relatório mensal. Justiça auditável vale mais que precisão de frações de centavo.

**Demonstração curta** (o mês fictício completo, com várias unidades, é objeto da Opção C): unidade 72, mês com 3 sessões, tarifa de referência R$ 0,7252/kWh (Enel SP B3, sem tributos), `C_disp` = R$ 180,00, 12 unidades aderentes:

| Linha | Cálculo | Valor |
|---|---|---|
| Sessão 1 — 18,4 kWh | 18,4 × 0,7252 = 13,34368 | R$ 13,34 |
| Sessão 2 — 25,0 kWh | 25,0 × 0,7252 = 18,13000 | R$ 18,13 |
| Sessão 3 — 9,3 kWh | 9,3 × 0,7252 = 6,74436 | R$ 6,74 |
| Taxa de disponibilidade | 180,00 / 12 = 15,00 | R$ 15,00 |
| **Fatura da unidade 72** | | **R$ 53,21** |

### Casos excepcionais

Os três casos exigidos pelo enunciado, e como o modelo os resolve **por construção** (nenhum exige regra ad hoc):

1. **Sessão interrompida** (queda de energia, cabo desconectado, desligamento de emergência da IT-41). Cobra-se exatamente o `kwh_s` entregue até a interrupção — a fórmula opera sobre leituras de medidor, não sobre intenção de recarga. O motivo do encerramento (campo do StopTransaction, Frente 1) fica registrado na linha da fatura. Caso degenerado: se a telemetria perder a leitura final, usa-se a última leitura periódica conhecida (MeterValues) — sempre o valor medido mais conservador, nunca estimativa para cima — e a sessão é sinalizada para auditoria no relatório do síndico.
2. **Usuário que não carregou no mês.** `S_u` vazio → parcela variável zero; a unidade aderente paga apenas `C_disp / N_aderentes`. É o comportamento desejado, não um caso de borda: a taxa remunera a disponibilidade da infraestrutura (a vaga de recarga existe, mantida e à disposição), não o uso. Unidade que nunca aderiu não paga nada — o rateio alcança só quem optou pelo serviço.
3. **Dois veículos da mesma unidade.** A fatura é **por unidade, não por veículo**: cada credencial (cartão RFID ou conta no app) é vinculada a uma unidade no cadastro, e `S_u` agrega as sessões de todas as credenciais da unidade. O extrato discrimina sessão a sessão, com a credencial que a iniciou — o casal vê qual carro consumiu o quê, mas recebe uma fatura só. *Decisão da equipe:* a taxa de disponibilidade é única por unidade, independentemente do número de veículos — o rateio é da infraestrutura comum, e cobrá-la por veículo puniria a composição familiar sem lastro em custo adicional real.

Outros casos que o esquema de dados (Opção C) e o motor de faturamento precisam suportar, registrados como insumo: **visitante** (credencial avulsa fora do rateio, com tarifa própria definida pelo condomínio — o art. 554 da REN 1.000 permite); **mudança de tarifa no meio do mês** (resolvida pelo snapshot `tarifa_s` por sessão); **adesão ou saída de unidade no meio do mês** (pro rata por dias de adesão sobre a parcela fixa — parâmetro do condomínio); **inadimplência** (a suspensão de credencial é decisão de assembleia, não automatismo da plataforma — risco jurídico condominial); e **sessão atravessando a virada do mês** (pertence ao mês do início, já definido em `S_u`).

### Análise da equipe

O híbrido kWh + taxa de disponibilidade vence porque é o único desenho que responde simultaneamente às três forças mapeadas no dossiê. Primeira, a **regulatória**: a Lei municipal 17.336/2020 exige *"medição individualizada e cobrança"* (Frente 2, Opção A) — a parcela variável por kWh medido é a implementação literal disso, e a taxa fixa pura (modelo 4 do benchmark) não a atende. Segunda, a **convergência do mercado**: os praticantes brasileiros do rateio condominial (WEMOB, NeoCharge) já operam kWh medido com identificação por RFID/app — nosso modelo não inventa um arranjo exótico, refina o dominante com a peça que falta (o destino explícito dos custos fixos, que o benchmark mostrou ser o ponto cego). Terceira, a **percepção de justiça**: a dor número 2 da Frente 1 é o subsídio cruzado entre usuários e não usuários; o híbrido o elimina nas duas direções — quem não aderiu não paga nada, quem aderiu e não usou paga só a disponibilidade que de fato consome (a infraestrutura pronta), quem carregou paga o seu kWh ao custo. Essa hipótese de justiça percebida é exatamente o que o roteiro de entrevistas da Frente 1 vai testar com moradores e síndicos — se as entrevistas indicarem resistência à taxa fixa, o parâmetro `C_disp` admite zero sem quebrar o motor (degrada para kWh puro, com o custo fixo de volta à cota condominial, decisão da assembleia). Rejeitamos explicitamente: a concessão (modelo 3), porque resolve o problema do síndico criando um problema para o morador (tarifa com margem de operador) e contraria a vocação da plataforma de dar transparência de custo, não de intermediar venda; e a cobrança por tempo, pela distorção já documentada no caso Copel (Frente 1) — tempo entra no modelo apenas como candidata futura a multa de ociosidade (carro-tampão), parametrizável, fora do cálculo de energia. Por fim, o modelo é deliberadamente **simples de auditar em assembleia**: duas parcelas, uma fórmula de uma linha, tarifa ancorada em fonte pública citável (dossiê da Frente 2, seção "Opção C — APIs complementares") — porque o benchmark e a Frente 1 convergem em que o rateio fracassa menos por matemática errada e mais por desconfiança de quem paga.

## Opção B — Papel da IA

> **Método.** A rubrica do desafio dedica um critério próprio a esta seção: o papel da IA deve ser *"estrutural, não decorativo"*. Tratamos isso como exigência de engenharia, não de retórica, com um teste objetivo que cada abordagem precisa passar: declarar (i) **quais campos do esquema de dados consome**, (ii) **que saída produz** e (iii) **qual decisão concreta — do gestor ou do morador — essa saída habilita**. Abordagem que não passa no teste fica fora do núcleo. Fontes acessadas em 2026-06-09; o dataset público sugerido pelo enunciado foi identificado no Kaggle e verificado na sua fonte acadêmica de origem.

### O que as três abordagens têm em comum: o mesmo dado, nenhuma instrumentação extra

A matéria-prima é o contrato de sessão já especificado na Frente 2 (corpo obrigatório) e que a Opção C detalha como esquema: `charge_point_id`, `session_start`/`session_end`, `energy_kwh`, `power_kw` (série temporal), `state`, `auth_id`, `measurement_source` — mais o cadastro (credencial → unidade, adesão) e a tarifa vigente que o motor de rateio (Opção A) já usa. A Frente 1 já havia registrado que os `MeterValues` periódicos do OCPP são o insumo natural dessa camada, *"sem custo adicional de instrumentação, pois o protocolo já entrega a telemetria"*. A consequência arquitetural: **a IA não tem pipeline paralelo de coleta** — lê das mesmas tabelas que o motor de faturamento escreve, devolve saídas para o painel do gestor e, no caso das anomalias, devolve flags para a própria fatura.

**Decisão da equipe — a restrição de infraestrutura como critério técnico, não desculpa:** a Sprint 2 roda em máquina modesta, sem GPU. Para dados tabulares de sessões — milhares de linhas, dezenas de features — esse é exatamente o território onde métodos clássicos e interpretáveis (scikit-learn, statsmodels) vencem deep learning em custo, robustez com pouco dado e, decisivo no nosso contexto, **explicabilidade**. A Opção A concluiu que o rateio fracassa menos por matemática errada e mais por desconfiança de quem paga; a mesma régua vale aqui: previsão que o síndico não consegue explicar em assembleia não embasa decisão nenhuma.

### Abordagem 1 — Previsão de demanda e ocupação

| | |
|---|---|
| **Problema que resolve** | As dores 1 e 3 da Frente 1: fila e disputa pelo carregador compartilhado, e a aproximação do limite de potência da instalação. Também alimenta uma obrigação regulatória: a IT-41 (item 5.9.4) exige estudo de demanda e curva de carga ratificando a viabilidade da infraestrutura — e a Frente 2 já apontou que a curva real medida é o complemento operacional desse estudo. |
| **Técnica** | Baseline: regressão com features de calendário (hora do dia em codificação cíclica, dia da semana, feriado), na linha do exemplo oficial do scikit-learn de previsão de demanda horária com features temporais [scikit-learn, 2026a]. Evolução: gradient boosting (`HistGradientBoostingRegressor`) com lags de 24 h e 168 h; alternativa estatística com sazonalidade semanal explícita via statsmodels (SARIMAX) [statsmodels, 2026]. |
| **Dados necessários** | Sessões agregadas em grade dia × hora por ponto: contagem de sessões ativas e kWh entregues, derivados de `session_start`/`session_end`/`energy_kwh`; potência horária de `power_kw`. Mínimo prático: 8–12 semanas de histórico para capturar o ciclo semanal. |
| **Impacto esperado** | Gestor deixa de descobrir a saturação na reclamação do morador e passa a vê-la com 7 dias de antecedência; a decisão de ampliar a infraestrutura sai do achismo para uma estimativa de demanda reprimida calculada da própria curva. |

**No fluxo sessão → fatura → decisão:** entrada = agregados dia × hora das sessões encerradas; saída = curva prevista de ocupação e de potência para os próximos 7 dias, por ponto e agregada, mais dois alertas no painel — saturação (ocupação prevista no pico acima de limiar configurado, ex.: > 90% em 3 ou mais dias da semana) e potência (pico previsto se aproximando da capacidade declarada da instalação, o dado que a Lei 18.403 faz o condomínio declarar). Decisões habilitadas: **do gestor** — abrir janela de reserva ou ajustar a política de tempo máximo antes do conflito; levar à assembleia a proposta de segundo carregador com estimativa de payback derivada da própria curva (sessões não atendidas previstas × kWh médio × tarifa, contra o acréscimo de `C_disp`); anexar a curva real + prevista ao documento de responsabilidade técnica na renovação do AVCB (IT-41, item 5.9.4). **Do morador** — ver no app os horários previstos de menor disputa antes de descer com o carro.

### Abordagem 2 — Clustering de perfis de uso

| | |
|---|---|
| **Problema que resolve** | Política de janelas, incentivos e tarifas diferenciadas hoje se decide no palpite. A Frente 1 identificou como lacuna de mercado a simulação de quanto cada modelo tarifário arrecadaria antes de adotá-lo — simulação que só é honesta se respeitar os perfis reais de uso, não um usuário médio fictício. |
| **Técnica** | k-means sobre features padronizadas por usuário, com escolha de k por coeficiente de silhueta; DBSCAN como alternativa que isola perfis raros como ruído em vez de forçá-los num cluster [scikit-learn, 2026b]. O precedente de domínio é forte: Helmus et al. (2020) derivaram 13 tipos estáveis de sessão e uma tipologia de usuários clusterizando 4,9 milhões de transações de recarga públicas holandesas a partir de exatamente as variáveis que temos (hora de início da conexão, duração, intervalo entre sessões) [Helmus et al., 2020]. |
| **Dados necessários** | Features por credencial/unidade derivadas do histórico: kWh médio por sessão, hora típica de início (codificação cíclica), frequência semanal, duração média conectada, razão tempo carregando / tempo conectado. Exige base com dezenas de usuários ativos — ver decisão de escopo abaixo. |
| **Impacto esperado** | O simulador tarifário passa a responder por segmento ("a tarifa noturna reduzida desloca os perfis de rotina sem mexer na receita dos esporádicos"); o morador recebe recomendação de janela compatível com o perfil dele, não um aviso genérico. |

**No fluxo sessão → fatura → decisão:** entrada = features agregadas por credencial sobre as mesmas sessões que geram a fatura; saída = rótulo de perfil por unidade (ex.: rotina noturna, esporádico de fim de semana, alto consumo concentrado) gravado no cadastro e re-estimado mensalmente. Decisões habilitadas: **do gestor** — desenhar janelas de reserva que separem perfis concorrentes e simular, antes da assembleia, o efeito de uma tarifa diferenciada sobre cada segmento (a funcionalidade de decisão que a análise de mercado da Frente 1 mostrou que nenhum player oferece); **do morador** — recomendação de janela de recarga com menor disputa para o perfil dele.

### Abordagem 3 — Detecção de anomalias

| | |
|---|---|
| **Problema que resolve** | Três riscos distintos com a mesma assinatura nos dados: saúde do equipamento (o caso Copel da Frente 1 — eletropostos fora de operação sem sinalização — fez a equipe promover monitoramento de saúde a funcionalidade de primeira classe), integridade da fatura (sessão com medição inconsistente contamina o rateio) e uso fora de política (ociosidade do carro-tampão, credencial usada em padrão atípico). |
| **Técnica** | Fase 1, desde o primeiro dia: regras estatísticas interpretáveis por usuário e por ponto (z-score/IQR sobre o histórico próprio). Fase 2, quando houver volume: Isolation Forest sobre o vetor de features da sessão — método de conjunto que isola observações raras sem precisar de exemplos rotulados de fraude/falha, adequado a base pequena e CPU [scikit-learn, 2026c; scikit-learn, 2026d]. |
| **Dados necessários** | A sessão individual e seu contexto: `energy_kwh` contra o histórico da credencial, duração, razão kWh/hora contra a potência nominal do ponto (7–22 kW no HCA G2), tempo em `state` conectado sem corrente, horário contra o padrão da credencial; na camada de saúde, heartbeats perdidos e taxa de sessões falhas por ponto. |
| **Impacto esperado** | Manutenção sai do modo reativo (morador reclama que não carrega) para o preditivo (razão kWh/hora caindo semana a semana = degradação antes da falha); a fatura ganha uma fila de auditoria que protege a confiança no rateio; a política de ociosidade ganha base de evidência em vez de denúncia de vizinho. |

**No fluxo sessão → fatura → decisão:** entrada = cada sessão encerrada + telemetria de status do ponto; saída = flag por sessão com categoria e explicação legível (consumo 4× o padrão da credencial; 6 h conectado com 0 kWh; potência média 30% abaixo da nominal) numa fila de revisão do painel, e a sessão flagrada **entra na fatura marcada para auditoria** — o mesmo mecanismo que a Opção A já definiu para sessão interrompida com telemetria perdida. Decisões habilitadas: **do gestor** — abrir chamado de manutenção antes da falha total; aceitar ou contestar a linha flagrada antes de fechar a fatura do mês; aplicar (ou propor em assembleia) a política de ociosidade com histórico objetivo. **Do morador** — extrato com as próprias sessões sinalizadas, contestação informada em vez de surpresa no boleto. **Decisão da equipe:** nenhuma saída de anomalia dispara punição automática — suspensão de credencial é decisão de assembleia (coerente com o tratamento de inadimplência da Opção A); a IA produz evidência, o humano decide.

### Síntese: onde cada abordagem entra no fluxo

| Abordagem | Entrada (campos do esquema) | Saída | Decisão habilitada (de quem) | Sprint 2 |
|---|---|---|---|---|
| 1. Previsão de demanda | `session_start/end`, `energy_kwh`, `power_kw` agregados dia × hora | Curva de ocupação/potência 7 dias + alertas de saturação e de limite | Janela de reserva; proposta de 2º carregador com payback; anexo IT-41 (gestor) · melhor horário (morador) | **Sim** |
| 2. Clustering de perfis | Features por credencial (kWh médio, hora típica, frequência, duração) | Rótulo de perfil por unidade, mensal | Janelas por perfil; simulação tarifária por segmento (gestor) · recomendação de janela (morador) | Especificada; implementação adiada |
| 3. Detecção de anomalias | Sessão individual + histórico da credencial + telemetria de status | Flag com categoria e explicação; linha de fatura marcada para auditoria | Manutenção preditiva; auditoria pré-fechamento da fatura; política de ociosidade (gestor) · contestação informada (morador) | **Sim** (fase 1 regras + fase 2 Isolation Forest) |

### Cold start e o dataset da Sprint 2

Honestidade primeiro: **nos primeiros meses não existe histórico do condomínio** — e a Frente 2 mostrou que nem o SEMS expõe sessões encerradas. Nenhum modelo treina no vazio, então a Sprint 2 trabalha em três degraus: (i) regras estatísticas simples já operam com semanas de dado (a fase 1 da abordagem 3 e limiares fixos de ocupação); (ii) um **gerador de dados sintéticos** produz sessões no esquema da Opção C; (iii) o gerador é **calibrado num dataset público real**, para que as distribuições (kWh por sessão, duração, frequência por usuário) não sejam invenção nossa.

O dataset escolhido é o sugerido pelo enunciado (§ 7.4): *Electric Vehicle Charging Dataset* no Kaggle [Kaggle/Bryant, 2026], que reempacota o dado publicado por Asensio, Lawson e Apablaza na revista Scientific Data — **3.395 sessões reais de recarga, 85 motoristas identificados e recorrentes, 105 estações AC nível 2 em 25 instalações de um campus corporativo nos EUA, 46 semanas (nov/2014–out/2015)**, dado primário depositado no Harvard Dataverse [Asensio et al., 2021; Harvard Dataverse, 2021]. As variáveis documentadas no artigo mapeiam quase 1:1 no nosso esquema: identificadores de sessão, usuário (→ `auth_id`), estação (→ `charge_point_id`) e local; timestamps de início e fim ao segundo (→ `session_start`/`session_end`); energia total em kWh (→ `energy_kwh`); duração em horas; custo da sessão; dia da semana; tipo de instalação; indicador de usuário habitual vs. casual. Entre os candidatos no Kaggle, este é o escolhido por três razões: é o que a descrição do enunciado designa (sessões reais de frota corporativa nos EUA); é o único com proveniência acadêmica revisada por pares e DOI público — os concorrentes ou são espelhos deste mesmo dado ou não declaram origem (vários são sintéticos sem documentação); e o contexto é o análogo mais próximo do nosso: recarga AC com usuários recorrentes identificados, onde o carro passa horas estacionado no mesmo lugar.

**Limitação declarada e uso correto:** recarga de trabalho é o espelho diurno do condomínio — os carros chegam de manhã e saem à tarde; no condomínio, chegam à noite. O dataset serve para **calibrar as formas das distribuições e validar o pipeline ponta a ponta** (com o eixo horário espelhado para o padrão noturno e os testes de anomalia injetados com rótulo conhecido pelo gerador), **não** para aprender sazonalidade ou horários brasileiros. Todo modelo entregue na Sprint 2 carrega o aviso de calibração: as previsões viram recomendação operacional somente após N semanas de dado local — N definido pela própria validação (quando o erro sobre dado local cruza o erro sobre dado sintético).

**Decisão da equipe — o que a Sprint 2 implementa: abordagens 1 e 3.** Três razões. Primeira, são as que atacam as dores com evidência mais forte no dossiê: saturação/fila e limite de potência (dores 1 e 3 da Frente 1) e o alerta operacional do caso Copel (disponibilidade destrói confiança mais rápido do que funcionalidade a constrói). Segunda, são avaliáveis com métrica objetiva mesmo sem dado real: erro absoluto médio da previsão contra o gerador, precisão/recall da detecção sobre anomalias injetadas com gabarito. Terceira, sobrevivem ao cold start (regras antes de ML). O clustering (abordagem 2) fica integralmente especificado — features, técnica, decisões que habilita — mas a implementação é adiada por um motivo estatístico que preferimos declarar a maquiar: **k-means sobre as 10–20 unidades aderentes de um único condomínio no primeiro ano é numerologia, não aprendizado**; o precedente de Helmus et al. operou sobre 27 mil usuários. Na Sprint 2, os perfis aparecem como segmentos definidos por regra (rotina noturna / diurno / esporádico) dentro do simulador tarifário, e o clustering entra quando houver base multi-condomínio.

**Anti-padrão que rejeitamos no núcleo: interface conversacional (NLP).** O enunciado a cita como exemplo de abordagem possível, e registramos por que a descartamos do núcleo: um chatbot não consome a telemetria (falha no teste de entrada), não habilita decisão que o painel bem desenhado não habilite (falha no teste de decisão) e seu custo de operação briga com a restrição de infraestrutura. É a definição prática de IA decorativa neste produto. Fica anotada como possibilidade futura — uma camada de consulta em linguagem natural **sobre** as saídas das três abordagens — explicitamente fora do escopo das Sprints 1 e 2.

### Análise da equipe

O critério da rubrica tem um teste prático que aplicamos a nós mesmos: **decorativo é o que se remove sem ninguém notar**. Removida a IA desta plataforma, quebram entregáveis nomeados — o alerta de saturação do painel, a estimativa de payback que embasa a assembleia do segundo carregador, o anexo de curva de carga da renovação do AVCB, a fila de auditoria que protege a fatura e a manutenção preditiva que responde ao caso Copel. Nenhum desses é um gráfico bonito ao lado do produto; são funções pelas quais gestor e morador tomam decisões com consequência financeira. A escolha por métodos clássicos e interpretáveis não é conformismo com a máquina modesta: é coerência com a tese da Opção A de que, em condomínio, auditabilidade vale mais que sofisticação — um gradient boosting com features de calendário se explica em assembleia; uma rede neural, não. O risco que registramos com a mesma franqueza: modelos calibrados em dado sintético derivado de um campus americano de 2014–2015 nascem errados em algum grau, e o produto trata isso como propriedade declarada (aviso de calibração, métrica de quando confiar) em vez de esconder. A aposta verificável da Sprint 2 é, portanto, dupla: que o pipeline previsão + anomalia rode de ponta a ponta sobre o esquema da Opção C em infraestrutura mínima, e que a transição sintético → real exija troca de dados, não refatoração — exatamente o mesmo desenho de adaptador plugável que a Frente 2 adotou para a API do fabricante.

## Opção C — Esquema da base de dados
<!-- a preencher -->

## Fontes

### Frente 3 — Opção A

Todas as fontes abaixo foram acessadas em 2026-06-09. As fontes ChargePoint e NeoCharge são as mesmas da Frente 1, Opção A (lá numeradas 17, 19 e 20), reacessadas nesta data para os trechos de cobrança citados aqui.

1. WEG — landing page oficial *WEMOB® | Eletrifique o seu condomínio* (rateio de consumo na plataforma, custos no boleto do condomínio, cobrança via cartão de crédito ou cartão RFID, identificação por RFID, energia por recarga). https://materiais.wegdigital.weg.net/weg-digital-wemob-condominios-canais
2. EZVolt (Easy Volt Brasil) — *Condomínios Residenciais* (modelo turn-key: investimento integral da empresa, recarga paga pelo app, tarifas personalizadas, receita para o condomínio). https://ezvolt.com.br/solucao/condominios-residenciais/
3. ChargePoint — *EV Charging Solutions for Condo Managers and HOAs* (cobrança direta ao morador, reembolso do custo de energia, preço por grupo de usuário; mesma fonte 17 da Frente 1). https://www.chargepoint.com/solutions/condos
4. NeoCharge — *Carregador para Carro Elétrico em Prédios e Condomínios* (medição por morador e divisão mensal; mesma fonte 20 da Frente 1). https://www.neocharge.com.br/tudo-sobre/carregador-carro-eletrico-predio-condominio-instalacao
5. Ambare — *Carregamento compartilhado em condomínios: como funciona e quem paga a conta?* (quatro formas de rateio praticadas: medidor individual, proporcional ao uso, taxa fixa mensal, inclusão condominial). https://ambare.com.br/carregamento-compartilhado-em-condominios-como-funciona-e-quem-paga-a-conta/
6. CondoCash — *Carregador de carro elétrico em condomínio: instalação, custos e rateio* (vedação de lucro pelo condomínio, cobrança por consumo, totem por tempo como método impreciso, mensalidade de manutenção acordada em contrato). https://condocash.com.br/carregador-de-carro-eletrico-em-condominio-instalacao-custos-e-rateio/

### Frente 3 — Opção B

Todas as fontes abaixo foram acessadas em 2026-06-09. Citações no texto: [Kaggle/Bryant, 2026] = fonte 1; [Asensio et al., 2021] = fonte 2; [Harvard Dataverse, 2021] = fonte 3; [scikit-learn, 2026a–d] = fontes 4–7; [statsmodels, 2026] = fonte 8; [Helmus et al., 2020] = fonte 9.

1. Kaggle — *Electric Vehicle Charging Dataset* (Michael Bryant; 3.395 sessões, 85 motoristas, 105 estações, 25 instalações; reempacotamento do dado de Asensio et al.). https://www.kaggle.com/datasets/michaelbryantds/electric-vehicle-charging-dataset
2. Asensio, O. I.; Lawson, M. C.; Apablaza, C. Z. — *Electric vehicle charging stations in the workplace with high-resolution data from casual and habitual users*. Scientific Data, v. 8, art. 168, 2021 (descrição completa das variáveis do dataset; texto integral consultado via PubMed Central). https://pmc.ncbi.nlm.nih.gov/articles/PMC8263557/ — DOI: https://doi.org/10.1038/s41597-021-00956-1
3. Harvard Dataverse — depósito primário do dataset de Asensio et al. (DOI 10.7910/DVN/QF1PMO). https://doi.org/10.7910/DVN/QF1PMO
4. scikit-learn — exemplo oficial *Time-related feature engineering* (previsão de demanda horária com features de calendário, codificação cíclica e gradient boosting). https://scikit-learn.org/stable/auto_examples/applications/plot_cyclical_feature_engineering.html
5. scikit-learn — guia do usuário *Clustering* (k-means, escolha de k, DBSCAN). https://scikit-learn.org/stable/modules/clustering.html
6. scikit-learn — referência da API `sklearn.ensemble.IsolationForest`. https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html
7. scikit-learn — guia do usuário *Novelty and Outlier Detection* (enquadramento do Isolation Forest entre os métodos de detecção não supervisionada). https://scikit-learn.org/stable/modules/outlier_detection.html
8. statsmodels — documentação oficial do módulo de séries temporais `statsmodels.tsa` (SARIMAX e modelos sazonais). https://www.statsmodels.org/stable/tsa.html
9. Helmus, J. R.; Lees, M. H.; van den Hoed, R. — *A data driven typology of electric vehicle user types and charging sessions*. Transportation Research Part C: Emerging Technologies, v. 115, 102637, 2020 (clustering de 4,9 milhões de sessões públicas holandesas; metadados consultados no repositório institucional da HvA). https://research.hva.nl/en/publications/a-data-driven-typology-of-electric-vehicle-user-types-and-chargin/ — DOI: https://doi.org/10.1016/j.trc.2020.102637
