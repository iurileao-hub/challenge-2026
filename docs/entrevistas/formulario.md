# Formulário autoaplicado — Frente 1-B (Pesquisa com usuários)

> **Relação com o roteiro.** Este formulário é a adaptação do [`roteiro.md`](roteiro.md) para
> aplicação autoaplicada (Google Forms), criada para ampliar o alcance da pesquisa. As duas
> modalidades coexistem: o roteiro segue valendo para conversas síncronas; o formulário
> estrutura as mesmas perguntas para resposta sem entrevistador. A tabela de mapeamento ao
> final preserva a rastreabilidade: cada pergunta do formulário (F1, F2...) aponta a pergunta
> de origem no roteiro (P1, P2...), e os insights citam evidência como "R3, F9" (respondente 3,
> pergunta F9), no mesmo espírito do "E2, P7" das entrevistas síncronas.

## Decisões de desenho

1. **Anônimo de verdade:** sem coleta de e-mail, sem login obrigatório, sem nome/endereço/
   condomínio. Único campo que quebra o anonimato é o contato opcional do final (F19),
   explicitamente sinalizado como opcional e voluntário.
2. **TCLE mínimo na abertura**, com consentimento obrigatório e saída digna: quem não
   concorda é levado direto ao envio, sem responder nada.
3. **Sem citar a empresa parceira nem o nome do produto** — evita viés de resposta e
   mantém a pesquisa neutra ("recarga compartilhada", não uma marca).
4. **Ramificação por persona** (exigência do enunciado: moradores, gestores, motoristas):
   F1 roteia para o bloco Morador/motorista ou Gestor; blocos convergem no fechamento.
   Perfis mistos escolhem o papel principal e complementam em F18.
5. **Estruturado onde dá, aberto onde importa:** as perguntas de história (conflito real,
   motivo de ruptura) e a de confiança permanecem abertas — são as que mais rendem insight.
   O resto vira escolha/checkbox para reduzir o atrito (alvo: 5–8 minutos).
6. **Hipóteses do dossiê testadas explicitamente:** F9/F16 testam a aceitação da taxa de
   disponibilidade (a hipótese de justiça percebida da Frente 3-A); F6 alimenta o desenho
   da fatura; F10 a escolha de credencial (RFID vs app); F13/F14/F15 o painel do gestor.

## Estrutura do formulário

**Título:** Pesquisa acadêmica — Recarga de veículos elétricos em espaços compartilhados

### Seção 1 — Apresentação e consentimento (TCLE mínimo)

Texto de abertura:

> Esta é uma pesquisa acadêmica conduzida por estudantes de graduação da FIAP sobre recarga
> de veículos elétricos e divisão de custos de energia em espaços compartilhados
> (condomínios, edifícios e estacionamentos).
>
> **Participação voluntária** — você pode desistir a qualquer momento, fechando esta página.
> **Anonimato** — o formulário não coleta nome, e-mail, endereço, nome de condomínio nem
> qualquer dado que identifique você; não é necessário login.
> **Uso dos dados** — as respostas serão analisadas de forma agregada e usadas
> exclusivamente neste trabalho acadêmico.
> **Tempo estimado** — 5 a 8 minutos.
> **Riscos e benefícios** — não há riscos previsíveis nem compensação financeira; o
> benefício é contribuir para o desenho de soluções mais justas de recarga compartilhada.
>
> Dúvidas sobre a pesquisa: **[e-mail de contato da equipe — preencher antes de publicar]**

- **F0** *(obrigatória, escolha única)* — "Declaro que li as informações acima, entendi o
  objetivo da pesquisa e concordo em participar voluntariamente."
  - Concordo em participar → continua
  - Não concordo → **envia o formulário** (nada respondido)

### Seção 2 — Perfil (todos)

- **F1** *(obrigatória, escolha única — define a ramificação)* — "Qual perfil melhor
  descreve você hoje? Se mais de um se aplicar, escolha o principal — haverá espaço no
  final para complementar."
  - Tenho veículo elétrico ou híbrido plug-in → **bloco Morador**
  - Não tenho veículo elétrico, mas considero ter nos próximos anos → **bloco Morador**
  - Não tenho nem pretendo ter veículo elétrico tão cedo → **bloco Morador**
  - Sou síndico(a), subsíndico(a), conselheiro(a) ou atuo em administradora de condomínios → **bloco Gestor**
  - Gerencio estacionamento, garagem comercial ou frota → **bloco Gestor**
- **F2** *(obrigatória, escolha única)* — "Onde você mora?"
  - Apartamento em condomínio · Casa em condomínio · Casa de rua · Outro
- **F3** *(obrigatória, escolha única)* — "Você já usou ou viu de perto um ponto de recarga
  compartilhado (no prédio, shopping, trabalho, estacionamento)?"
  - Uso com frequência · Já usei algumas vezes · Já vi, mas nunca usei · Nunca vi de perto
- **F4** *(opcional, parágrafo)* — "Se já usou ou viu: o que funcionou bem e o que incomodou?"
- **F5** *(obrigatória, caixas de seleção)* — "Pense numa conta dividida entre várias
  pessoas (energia de área comum, restaurante, viagem). O que mais pesa para a divisão
  parecer **justa** para você?"
  - Cada um pagar pelo que de fato consumiu
  - Simplicidade, mesmo que o valor seja aproximado
  - Transparência: poder ver como o valor foi calculado
  - As regras terem sido combinadas antes, por todos
  - Outro (campo livre)

### Seção 3 — Bloco Morador / motorista (real ou potencial)

- **F6** *(obrigatória, caixas de seleção)* — "Imagine que no fim do mês chega a cobrança
  das suas recargas no prédio. O que precisaria estar nela para você **confiar** no valor?"
  - A energia (kWh) de cada recarga · Data e horário de cada recarga · O preço por kWh e de
    onde ele vem (tarifa da distribuidora) · Qual cartão/app iniciou cada recarga ·
    Comparativo com meses anteriores · Um jeito fácil de contestar uma cobrança específica ·
    Outro
- **F7** *(obrigatória, escolha única)* — "Você desce na garagem e o carregador está
  ocupado. O que mais ajudaria nessa hora?"
  - Ver pelo celular quando vai liberar · Poder reservar um horário · Receber aviso quando
    liberar · Existir um segundo carregador · Nada, eu esperaria · Outro
- **F8** *(obrigatória, escolha única)* — "Carregar no prédio tem custo de instalação e
  gestão. Em relação ao preço da energia da sua própria casa, quanto a mais você toparia
  pagar pela conveniência?"
  - Nada — só o custo exato da energia · Até uns 10% a mais · Até uns 25% a mais · Até uns
    50% a mais · Pagaria preço de eletroposto pela conveniência · Não sei avaliar
- **F9** *(obrigatória, escolha única)* — "Um modelo possível: quem **adere** ao serviço
  paga uma taxa fixa mensal (que mantém o equipamento disponível e com manutenção em dia)
  mais o valor exato da energia que consumir. Quem não adere não paga nada. Esse modelo
  parece:"
  - Justo · Aceitável, com ressalvas · Injusto · Não sei
- **F9b** *(opcional, parágrafo)* — "Quer explicar sua resposta anterior?"
- **F10** *(obrigatória, escolha única)* — "Para a recarga ficar registrada no seu nome,
  você preferiria:"
  - Encostar um cartão ou chaveiro · Abrir um aplicativo · O sistema reconhecer o carro
    automaticamente · Indiferente

### Seção 4 — Bloco Gestor (síndico / administradora / estacionamento)

- **F11** *(obrigatória, escolha única)* — "Como a energia das áreas comuns é dividida hoje
  onde você atua?"
  - Igualmente entre as unidades · Pela fração ideal · Há medição individualizada · Entra
    na taxa condominial sem detalhamento · Não sei · Outro
- **F12** *(obrigatória, parágrafo)* — "Conte brevemente um conflito real entre moradores
  (ou clientes) por causa de custo ou uso de algo compartilhado, e como foi resolvido.
  Duas ou três frases bastam."
- **F13** *(obrigatória, caixas de seleção)* — "Se fosse instalado um carregador
  compartilhado amanhã, o que **não poderia faltar** para isso não virar dor de cabeça
  para a administração?"
  - Cobrança automática junto ao boleto · Relatório pronto para prestação de contas em
    assembleia · Regras de uso aprovadas em assembleia antes de ligar · Suporte técnico
    rápido quando quebrar · Garantia de que a instalação atende às normas e ao Corpo de
    Bombeiros · Não depender de planilha manual de ninguém · Outro
- **F14** *(obrigatória, caixas de seleção)* — "Que informações você gostaria de receber
  sobre o uso do carregador?"
  - Consumo por unidade/apartamento · Faturamento e inadimplência · Estado do equipamento
    (funcionando/com defeito) · Horários de pico e fila · Relatório mensal pronto para
    assembleia · Outro
- **F15** *(obrigatória, caixas de seleção)* — "Pensando em contestações de valores: o que
  te deixaria **menos exposto** a reclamação de morador ou cliente?"
  - Preço ancorado na tarifa oficial da distribuidora · Extrato detalhado por recarga ·
    Regras registradas em ata · Canal formal de contestação · Histórico completo e
    auditável de cada cobrança · Outro
- **F16** *(obrigatória, escolha única)* — "Um modelo possível: quem adere ao serviço paga
  uma taxa fixa mensal (manutenção e disponibilidade) mais a energia que consumir; quem não
  adere não paga nada. Numa assembleia do condomínio (ou na sua operação), esse modelo
  seria aprovado?"
  - Sim, tranquilamente · Sim, mas com debate · Dificilmente · Não · Não sei
- **F16b** *(opcional, parágrafo)* — "Quer explicar sua resposta anterior?"

### Seção 5 — Fechamento (todos)

- **F17** *(obrigatória, parágrafo)* — "Para terminar: o que te faria **não usar** (ou não
  aprovar) um sistema de recarga compartilhada com cobrança individual? Qual seria o motivo
  de ruptura?"
- **F18** *(opcional, parágrafo)* — "Quer complementar algo? Se você se encaixa em mais de
  um perfil (ex.: síndico que também tem carro elétrico), conte aqui a outra perspectiva."
- **F19** *(opcional, resposta curta)* — "Esta pesquisa é anônima. Mas se você **topar** uma
  conversa rápida de 15 minutos com a equipe, deixe um contato (e-mail ou WhatsApp). Este
  campo é totalmente opcional e quebra o anonimato apenas para quem preferir deixá-lo."

**Mensagem de confirmação:** "Obrigado! Suas respostas foram registradas anonimamente e
serão usadas apenas neste trabalho acadêmico."

## Mapeamento formulário → roteiro

| Formulário | Roteiro | Observação |
|---|---|---|
| F1 | P1 | Estruturada (perfil/relação com EV) |
| F2 | perfil | Contexto de moradia (instruções de aplicação do roteiro) |
| F3, F4 | P2 | Experiência com recarga compartilhada (fechada + aberta opcional) |
| F5 | P3, P4 | Justiça percebida em divisão de contas, estruturada |
| F6 | P6 | Confiança na fatura — alimenta o desenho de `invoice_line` |
| F7 | P7 | Recurso ocupado — alimenta fila/reserva |
| F8 | P8 | Disposição a pagar — calibra preço de repasse |
| F9, F9b | P8 (desdobr.) | **Teste da hipótese `C_disp`** (Frente 3-A) — visão do morador |
| F10 | P9 | Credencial: RFID × app × automático |
| F11 | P10 | Rateio atual de áreas comuns |
| F12 | P11 | Conflito real (aberta — história) |
| F13 | P12 | Implantação "indolor" para a administração |
| F14 | P13 | Relatórios desejados — alimenta o painel do gestor |
| F15 | P14 | Exposição a contestação — alimenta auditabilidade |
| F16, F16b | P14 (desdobr.) | **Teste da hipótese `C_disp`** — visão do gestor/assembleia |
| F17 | P15 | Motivo de ruptura (aberta, obrigatória — nunca pular) |
| F18 | — | Perfil misto (substitui a aplicação dupla de blocos do roteiro) |
| F19 | — | Recrutamento opcional para entrevista síncrona (roteiro completo) |
| Não migradas | P5 | Tomada própria × compartilhado — exige nuance de conversa; fica para as síncronas |

## Publicação — checklist de configuração (fazer no Forms após rodar o script)

- [ ] Configurações → Respostas → **"Coletar endereços de e-mail": Desativado** (o script já configura; conferir)
- [ ] **"Limitar a 1 resposta": Desativado** (exigiria login — quebraria o anonimato)
- [ ] "Permitir edição das respostas": Desativado
- [ ] Preencher o **e-mail de contato da equipe** no texto do TCLE
- [ ] Tema sóbrio (sem imagem de marca de fabricante)
- [ ] Testar a ramificação: consentimento negado → envia; perfil gestor → pula bloco morador; morador → pula bloco gestor
- [ ] Vincular a uma planilha (Respostas → ícone Sheets) para análise
- [ ] Distribuir por link encurtado; combinar com o grupo quem divulga em quais redes/grupos
