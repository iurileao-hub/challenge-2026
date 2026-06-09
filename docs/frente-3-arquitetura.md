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
<!-- a preencher -->

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
