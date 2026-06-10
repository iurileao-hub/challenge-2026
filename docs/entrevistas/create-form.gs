/**
 * Cria o formulário da Frente 1-B no Google Forms.
 * Espelho fiel de docs/entrevistas/formulario.md — se editar lá, edite aqui.
 *
 * Como usar (uma vez, ~2 min):
 *   1. Acesse script.google.com → Novo projeto.
 *   2. Apague o conteúdo de Code.gs e cole este arquivo inteiro.
 *   3. Menu Executar → função `criarFormulario` → autorize com a conta Google da equipe.
 *   4. Abra Execuções (ou Ver → Registros): o log traz a URL de edição e a URL pública.
 *   5. Siga o checklist de publicação do formulario.md (e-mail de contato no TCLE, etc.).
 *
 * Navegação implementada:
 *   TCLE: "Não concordo" → envia sem responder; "Concordo" → seção Perfil.
 *   Perfil (F1): morador/motorista → seção Morador; gestor → seção Gestor.
 *   Fim da seção Morador → pula a seção Gestor, vai ao Fechamento.
 *   (No Forms API, esse pulo se configura no page break da seção SEGUINTE — pgGestor —
 *    porque setGoToPage governa quem chega àquele break vindo da página anterior.)
 */
function criarFormulario() {
  const form = FormApp.create(
    'Pesquisa acadêmica — Recarga de veículos elétricos em espaços compartilhados'
  );

  form
    .setDescription(
      'Esta é uma pesquisa acadêmica conduzida por estudantes de graduação da FIAP sobre ' +
      'recarga de veículos elétricos e divisão de custos de energia em espaços compartilhados ' +
      '(condomínios, edifícios e estacionamentos).\n\n' +
      'PARTICIPAÇÃO VOLUNTÁRIA — você pode desistir a qualquer momento, fechando esta página.\n' +
      'ANONIMATO — o formulário não coleta nome, e-mail, endereço, nome de condomínio nem ' +
      'qualquer dado que identifique você; não é necessário login.\n' +
      'USO DOS DADOS — as respostas serão analisadas de forma agregada e usadas ' +
      'exclusivamente neste trabalho acadêmico.\n' +
      'TEMPO ESTIMADO — 5 a 8 minutos.\n' +
      'RISCOS E BENEFÍCIOS — não há riscos previsíveis nem compensação financeira; o ' +
      'benefício é contribuir para o desenho de soluções mais justas de recarga compartilhada.\n\n' +
      'Dúvidas sobre a pesquisa: [PREENCHER e-mail de contato da equipe antes de publicar]'
    )
    .setCollectEmail(false)
    .setLimitOneResponsePerUser(false)
    .setAllowResponseEdits(false)
    .setProgressBar(true)
    .setConfirmationMessage(
      'Obrigado! Suas respostas foram registradas anonimamente e serão usadas apenas ' +
      'neste trabalho acadêmico.'
    );

  // ---- Page breaks (criados antes, para a navegação poder referenciá-los) ----
  const pgPerfil = form.addPageBreakItem().setTitle('Sobre você');
  const pgMorador = form.addPageBreakItem().setTitle('Recarga no dia a dia');
  const pgGestor = form.addPageBreakItem().setTitle('A visão de quem administra');
  const pgFinal = form.addPageBreakItem().setTitle('Para terminar');

  // Quem termina a seção Morador chega a pgGestor por progressão linear → pula ao Fechamento.
  pgGestor.setGoToPage(pgFinal);

  // ---- Seção 1: TCLE (primeiro item da página 1) ----
  const consent = form.addMultipleChoiceItem();
  consent
    .setTitle(
      'Declaro que li as informações acima, entendi o objetivo da pesquisa e concordo em ' +
      'participar voluntariamente.'
    )
    .setRequired(true)
    .setChoices([
      consent.createChoice('Concordo em participar', pgPerfil),
      consent.createChoice('Não concordo', FormApp.PageNavigationType.SUBMIT),
    ]);
  form.moveItem(consent.getIndex(), 0);

  // ---- Seção 2: Perfil (todos) ----
  const perfilItems = [];

  const f1 = form.addMultipleChoiceItem();
  f1.setTitle('Qual perfil melhor descreve você hoje?')
    .setHelpText(
      'Se mais de um se aplicar, escolha o principal — haverá espaço no final para complementar.'
    )
    .setRequired(true)
    .setChoices([
      f1.createChoice('Tenho veículo elétrico ou híbrido plug-in', pgMorador),
      f1.createChoice('Não tenho veículo elétrico, mas considero ter nos próximos anos', pgMorador),
      f1.createChoice('Não tenho nem pretendo ter veículo elétrico tão cedo', pgMorador),
      f1.createChoice(
        'Sou síndico(a), subsíndico(a), conselheiro(a) ou atuo em administradora de condomínios',
        pgGestor
      ),
      f1.createChoice('Gerencio estacionamento, garagem comercial ou frota', pgGestor),
    ]);
  perfilItems.push(f1);

  perfilItems.push(
    form
      .addMultipleChoiceItem()
      .setTitle('Onde você mora?')
      .setRequired(true)
      .setChoiceValues(['Apartamento em condomínio', 'Casa em condomínio', 'Casa de rua', 'Outro'])
  );

  perfilItems.push(
    form
      .addMultipleChoiceItem()
      .setTitle(
        'Você já usou ou viu de perto um ponto de recarga compartilhado (no prédio, shopping, ' +
        'trabalho, estacionamento)?'
      )
      .setRequired(true)
      .setChoiceValues([
        'Uso com frequência',
        'Já usei algumas vezes',
        'Já vi, mas nunca usei',
        'Nunca vi de perto',
      ])
  );

  perfilItems.push(
    form
      .addParagraphTextItem()
      .setTitle('Se já usou ou viu: o que funcionou bem e o que incomodou?')
      .setRequired(false)
  );

  const f5 = form
    .addCheckboxItem()
    .setTitle(
      'Pense numa conta dividida entre várias pessoas (energia de área comum, restaurante, ' +
      'viagem). O que mais pesa para a divisão parecer JUSTA para você?'
    )
    .setRequired(true)
    .setChoiceValues([
      'Cada um pagar pelo que de fato consumiu',
      'Simplicidade, mesmo que o valor seja aproximado',
      'Transparência: poder ver como o valor foi calculado',
      'As regras terem sido combinadas antes, por todos',
    ]);
  f5.showOtherOption(true);
  perfilItems.push(f5);

  // ---- Seção 3: Bloco Morador / motorista ----
  const moradorItems = [];

  const f6 = form
    .addCheckboxItem()
    .setTitle(
      'Imagine que no fim do mês chega a cobrança das suas recargas no prédio. O que ' +
      'precisaria estar nela para você CONFIAR no valor?'
    )
    .setRequired(true)
    .setChoiceValues([
      'A energia (kWh) de cada recarga',
      'Data e horário de cada recarga',
      'O preço por kWh e de onde ele vem (tarifa da distribuidora)',
      'Qual cartão/app iniciou cada recarga',
      'Comparativo com meses anteriores',
      'Um jeito fácil de contestar uma cobrança específica',
    ]);
  f6.showOtherOption(true);
  moradorItems.push(f6);

  const f7 = form
    .addMultipleChoiceItem()
    .setTitle('Você desce na garagem e o carregador está ocupado. O que mais ajudaria nessa hora?')
    .setRequired(true)
    .setChoiceValues([
      'Ver pelo celular quando vai liberar',
      'Poder reservar um horário',
      'Receber aviso quando liberar',
      'Existir um segundo carregador',
      'Nada, eu esperaria',
    ]);
  f7.showOtherOption(true);
  moradorItems.push(f7);

  moradorItems.push(
    form
      .addMultipleChoiceItem()
      .setTitle(
        'Carregar no prédio tem custo de instalação e gestão. Em relação ao preço da energia ' +
        'da sua própria casa, quanto a mais você toparia pagar pela conveniência?'
      )
      .setRequired(true)
      .setChoiceValues([
        'Nada — só o custo exato da energia',
        'Até uns 10% a mais',
        'Até uns 25% a mais',
        'Até uns 50% a mais',
        'Pagaria preço de eletroposto pela conveniência',
        'Não sei avaliar',
      ])
  );

  moradorItems.push(
    form
      .addMultipleChoiceItem()
      .setTitle(
        'Um modelo possível: quem ADERE ao serviço paga uma taxa fixa mensal (que mantém o ' +
        'equipamento disponível e com manutenção em dia) mais o valor exato da energia que ' +
        'consumir. Quem não adere não paga nada. Esse modelo parece:'
      )
      .setRequired(true)
      .setChoiceValues(['Justo', 'Aceitável, com ressalvas', 'Injusto', 'Não sei'])
  );

  moradorItems.push(
    form.addParagraphTextItem().setTitle('Quer explicar sua resposta anterior?').setRequired(false)
  );

  moradorItems.push(
    form
      .addMultipleChoiceItem()
      .setTitle('Para a recarga ficar registrada no seu nome, você preferiria:')
      .setRequired(true)
      .setChoiceValues([
        'Encostar um cartão ou chaveiro',
        'Abrir um aplicativo',
        'O sistema reconhecer o carro automaticamente',
        'Indiferente',
      ])
  );

  // ---- Seção 4: Bloco Gestor ----
  const gestorItems = [];

  const f11 = form
    .addMultipleChoiceItem()
    .setTitle('Como a energia das áreas comuns é dividida hoje onde você atua?')
    .setRequired(true)
    .setChoiceValues([
      'Igualmente entre as unidades',
      'Pela fração ideal',
      'Há medição individualizada',
      'Entra na taxa condominial sem detalhamento',
      'Não sei',
    ]);
  f11.showOtherOption(true);
  gestorItems.push(f11);

  gestorItems.push(
    form
      .addParagraphTextItem()
      .setTitle(
        'Conte brevemente um conflito real entre moradores (ou clientes) por causa de custo ' +
        'ou uso de algo compartilhado, e como foi resolvido. Duas ou três frases bastam.'
      )
      .setRequired(true)
  );

  const f13 = form
    .addCheckboxItem()
    .setTitle(
      'Se fosse instalado um carregador compartilhado amanhã, o que NÃO PODERIA FALTAR para ' +
      'isso não virar dor de cabeça para a administração?'
    )
    .setRequired(true)
    .setChoiceValues([
      'Cobrança automática junto ao boleto',
      'Relatório pronto para prestação de contas em assembleia',
      'Regras de uso aprovadas em assembleia antes de ligar',
      'Suporte técnico rápido quando quebrar',
      'Garantia de que a instalação atende às normas e ao Corpo de Bombeiros',
      'Não depender de planilha manual de ninguém',
    ]);
  f13.showOtherOption(true);
  gestorItems.push(f13);

  const f14 = form
    .addCheckboxItem()
    .setTitle('Que informações você gostaria de receber sobre o uso do carregador?')
    .setRequired(true)
    .setChoiceValues([
      'Consumo por unidade/apartamento',
      'Faturamento e inadimplência',
      'Estado do equipamento (funcionando/com defeito)',
      'Horários de pico e fila',
      'Relatório mensal pronto para assembleia',
    ]);
  f14.showOtherOption(true);
  gestorItems.push(f14);

  const f15 = form
    .addCheckboxItem()
    .setTitle(
      'Pensando em contestações de valores: o que te deixaria MENOS EXPOSTO a reclamação ' +
      'de morador ou cliente?'
    )
    .setRequired(true)
    .setChoiceValues([
      'Preço ancorado na tarifa oficial da distribuidora',
      'Extrato detalhado por recarga',
      'Regras registradas em ata',
      'Canal formal de contestação',
      'Histórico completo e auditável de cada cobrança',
    ]);
  f15.showOtherOption(true);
  gestorItems.push(f15);

  gestorItems.push(
    form
      .addMultipleChoiceItem()
      .setTitle(
        'Um modelo possível: quem adere ao serviço paga uma taxa fixa mensal (manutenção e ' +
        'disponibilidade) mais a energia que consumir; quem não adere não paga nada. Numa ' +
        'assembleia do condomínio (ou na sua operação), esse modelo seria aprovado?'
      )
      .setRequired(true)
      .setChoiceValues(['Sim, tranquilamente', 'Sim, mas com debate', 'Dificilmente', 'Não', 'Não sei'])
  );

  gestorItems.push(
    form.addParagraphTextItem().setTitle('Quer explicar sua resposta anterior?').setRequired(false)
  );

  // ---- Seção 5: Fechamento (todos) ----
  const finalItems = [];

  finalItems.push(
    form
      .addParagraphTextItem()
      .setTitle(
        'Para terminar: o que te faria NÃO USAR (ou não aprovar) um sistema de recarga ' +
        'compartilhada com cobrança individual? Qual seria o motivo de ruptura?'
      )
      .setRequired(true)
  );

  finalItems.push(
    form
      .addParagraphTextItem()
      .setTitle(
        'Quer complementar algo? Se você se encaixa em mais de um perfil (ex.: síndico que ' +
        'também tem carro elétrico), conte aqui a outra perspectiva.'
      )
      .setRequired(false)
  );

  finalItems.push(
    form
      .addTextItem()
      .setTitle(
        'Esta pesquisa é anônima. Mas se você topar uma conversa rápida de 15 minutos com a ' +
        'equipe, deixe um contato (e-mail ou WhatsApp). Este campo é totalmente opcional e ' +
        'quebra o anonimato apenas para quem preferir deixá-lo.'
      )
      .setRequired(false)
  );

  // ---- Reordenação: os itens nasceram no fim do formulário; cada bloco vai
  // para logo depois do seu page break, na ordem em que foi declarado. ----
  moveBlockAfter(form, perfilItems, pgPerfil);
  moveBlockAfter(form, moradorItems, pgMorador);
  moveBlockAfter(form, gestorItems, pgGestor);
  moveBlockAfter(form, finalItems, pgFinal);

  Logger.log('Formulário criado.');
  Logger.log('URL de edição:  ' + form.getEditUrl());
  Logger.log('URL pública:    ' + form.getPublishedUrl());
}

/** Move uma lista de itens (na ordem dada) para logo após um page break. */
function moveBlockAfter(form, items, pageBreak) {
  let target = pageBreak.getIndex() + 1;
  for (const item of items) {
    form.moveItem(item.getIndex(), target);
    target = item.getIndex() + 1;
  }
}
