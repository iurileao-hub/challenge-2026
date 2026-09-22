"""Interfaces do EV ChargeOps.

Duas audiencias com necessidades opostas, e a separacao e deliberada:

- **o gestor** precisa decidir sobre o coletivo -- ocupacao, saude dos pontos,
  o que auditar antes de fechar o mes, o que levar para a assembleia;
- **o morador** precisa entender a propria conta -- o que consumiu, por que
  custou isso, e como contestar se discordar.

Servir os dois na mesma tela produziria uma tela que nao serve nenhum.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count, Max, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from billing.audit import sync_session
from billing.competence import Competence, condo_tz
from billing.engine import billable_sessions, close_competence, enrolled_units
from core.models import (
    AnomalyFlag,
    AppUser,
    ChargePoint,
    ChargingSession,
    Condominium,
    Invoice,
    InvoiceLine,
    TelemetryReading,
    Unit,
)
from ingestion import orphans
from ingestion.models import IngestionRun, RawEvent
from intelligence.forecast import forecast

#: Abaixo disso, a contagem por hora nao sustenta uma recomendacao de horario.
MIN_SESSOES_PARA_SUGERIR = 20

#: A demo opera sobre junho/2026, que e a competencia do mes ficticio do dossie.
DEMO_TODAY = date(2026, 6, 30)


def _hora_humana(h: int) -> str:
    """`6` -> "6h da manha". Sem isso o morador le "6h" como duracao."""
    if 0 <= h < 5:
        return f"{h}h da madrugada"
    if 5 <= h < 12:
        return f"{h}h da manhã"
    if 12 <= h < 18:
        return f"{h}h da tarde"
    return f"{h}h da noite"


def _grafico_previsao(previsao, largura: int = 680, altura: int = 176) -> dict | None:
    """Geometria do grafico de area da previsao, pronta para o template.

    Template do Django nao faz aritmetica, entao as coordenadas saem calculadas
    daqui. SVG inline em vez de biblioteca: zero dependencia, coerente com a
    decisao de nao depender de CDN, e escala sem perder nitidez -- o que importa
    quando a tela vira video.
    """
    dias = list(previsao.days)
    if not dias:
        return None

    pad_x, topo, base = 30.0, 30.0, float(altura - 26)
    teto = (max(d.predicted_kwh for d in dias) or 1.0) * 1.20   # respiro p/ o rotulo
    passo = (largura - 2 * pad_x) / (len(dias) - 1) if len(dias) > 1 else 0.0

    pontos = []
    for i, d in enumerate(dias):
        x = pad_x + i * passo
        y = base - (d.predicted_kwh / teto) * (base - topo)
        pontos.append({
            "x": round(x, 1),
            "y": round(y, 1),
            "ry": round(y - 13, 1),        # linha de base do rotulo de valor
            "dia": d.day,
            "valor": d.predicted_kwh,
        })

    linha = " ".join(f"{p['x']},{p['y']}" for p in pontos)
    return {
        "largura": largura,
        "altura": altura,
        "base": base,
        "pontos": pontos,
        "linha": linha,
        "area": f"{pontos[0]['x']},{base} {linha} {pontos[-1]['x']},{base}",
        "y_dia": altura - 7,               # linha de base do rotulo de dia
        "x_fim": largura - 12,
        "grade": [round(base - k * (base - topo) / 2, 1) for k in (1, 2)],
    }


def _app_user(request) -> AppUser | None:
    return AppUser.objects.filter(auth_user=request.user).select_related("unit").first()


def _is_manager(request) -> bool:
    au = _app_user(request)
    return bool(au and au.role == AppUser.Role.MANAGER)


def _condo() -> Condominium:
    condo = Condominium.objects.order_by("id").first()
    if condo is None:
        raise Http404("nenhum condominio cadastrado")
    return condo


def _competence_from(request) -> Competence:
    """`?competencia=abc` e pagina nao encontrada, nao erro 500."""
    try:
        return Competence.parse(request.GET.get("competencia") or str(_current_competence()))
    except (ValueError, TypeError):
        raise Http404("competencia invalida") from None


def _flags_do_condo(condo):
    return AnomalyFlag.objects.filter(
        Q(session__charge_point__condominium=condo) | Q(charge_point__condominium=condo)
    ).select_related("session__credential__user__unit", "charge_point")


def _current_competence() -> Competence:
    return Competence.of(datetime.combine(DEMO_TODAY, time(12), tzinfo=condo_tz()))


@login_required
def home(request):
    """Encaminha cada pessoa para a interface que e dela."""
    return redirect("painel" if _is_manager(request) else "extrato")


# --------------------------------------------------------------------------
# Painel do gestor
# --------------------------------------------------------------------------

@login_required
def painel(request):
    if not _is_manager(request):
        raise Http404
    condo = _condo()
    comp = _current_competence()

    sessions = list(billable_sessions(condo, comp))
    kwh_mes = sum((Decimal(s.energy_kwh) for s in sessions), Decimal("0.000"))
    aderentes = enrolled_units(condo, comp)

    faturas = Invoice.objects.filter(condominium=condo, competence=str(comp))
    receita = faturas.aggregate(t=Sum("total_amount"))["t"] or Decimal("0.00")

    # A fila e tudo o que ESPERA decisao: o que a deteccao abriu e o que o
    # morador contestou. Listar so `open` deixava a contestacao sem destinatario.
    anomalias = list(_flags_do_condo(condo).filter(status__in=AnomalyFlag.AWAITING).order_by("-created_at"))
    # Duas filas, porque sao duas perguntas: o VALOR esta certo? (segura a
    # linha) e a VAGA / o EQUIPAMENTO esta bem? (nao segura). Quem separa e o
    # modelo, nao a tela.
    # O que ja segura dinheiro vem antes do que so sugere (a ordenacao e
    # estavel: dentro de cada grupo continua do mais recente ao mais antigo).
    cobranca = sorted((a for a in anomalias if a.doubts_billing), key=lambda a: not a.holds_billing)
    operacao = [a for a in anomalias if not a.doubts_billing]
    confirmadas = _flags_do_condo(condo).filter(status=AnomalyFlag.Status.ACCEPTED).order_by("-reviewed_at")
    sem_dono = orphans.orphan_summary(condo)
    quarentena = RawEvent.objects.filter(
        outcome__in=RawEvent.QUARANTINE, resolved_at__isnull=True
    ).count()

    previsao = forecast(condo, today=DEMO_TODAY)

    # Saude dos pontos: ultimo sinal recebido de cada um.
    pontos = []
    agora = datetime.combine(DEMO_TODAY, time(23, 59), tzinfo=condo_tz())
    for p in ChargePoint.objects.filter(condominium=condo):
        ultimo = TelemetryReading.objects.filter(charge_point=p).aggregate(t=Max("ts"))["t"]
        horas = (agora - ultimo).total_seconds() / 3600 if ultimo else None
        sess_mes = [s for s in sessions if s.charge_point_id == p.id]
        pontos.append({
            "ponto": p,
            "ultimo_sinal": ultimo,
            "horas_sem_sinal": horas,
            "online": horas is not None and horas < 3,
            "sessoes_mes": len(sess_mes),
            "kwh_mes": sum((Decimal(s.energy_kwh) for s in sess_mes), Decimal("0.000")),
            "falhas": sum(1 for s in sess_mes if s.status == "fault"),
        })

    # Ocupacao por hora do dia -- alimenta a barra do painel.
    ocupacao = [0] * 24
    for s in sessions:
        ocupacao[s.session_start.astimezone(condo_tz()).hour] += 1
    pico = max(ocupacao) or 1

    # Quem esta retido: alimenta a faixa de estado do topo, que responde
    # "esta tudo bem?" antes de qualquer numero.
    retidas = [
        f.unit.label for f in faturas.filter(status=Invoice.Status.UNDER_REVIEW).select_related("unit")
        if f.unit
    ]

    return render(request, "portal/painel.html", {
        "condo": condo,
        "grafico": _grafico_previsao(previsao),
        "unidades_retidas": retidas,
        "competencia": comp,
        "kwh_mes": kwh_mes,
        "sessoes_mes": len(sessions),
        "aderentes": len(aderentes),
        "receita": receita,
        "faturas": faturas.count(),
        "em_auditoria": faturas.filter(status=Invoice.Status.UNDER_REVIEW).count(),
        "anomalias": anomalias,
        "cobranca": cobranca,
        "cobranca_retendo": any(a.holds_billing for a in cobranca),
        "operacao": operacao,
        "confirmadas": confirmadas,
        "confirmadas_retendo": [a for a in confirmadas if a.holds_billing],
        "sem_dono": sem_dono,
        "quarentena": quarentena,
        "previsao": previsao,
        "pontos": pontos,
        "ocupacao": [{"hora": h, "n": n, "pct": int(n / pico * 100)} for h, n in enumerate(ocupacao)],
    })


@login_required
@require_POST
def revisar_anomalia(request, flag_id: int):
    """O humano decide. A IA nunca fecha o proprio caso.

    As duas decisoes NAO sao simetricas. Descartar significa "nao havia
    problema": a linha sai da auditoria. Confirmar significa o oposto -- o
    problema e real, e a linha PERMANECE retida ate o caso ter desfecho
    (`resolver_anomalia`). A regra de retencao mora em `billing.audit`.
    """
    if not _is_manager(request):
        raise Http404
    flag = get_object_or_404(_flags_do_condo(_condo()), pk=flag_id)
    decisao = request.POST.get("decisao")
    if decisao not in {"accepted", "dismissed"}:
        messages.error(request, "Decisão inválida.")
        return redirect("painel")
    if flag.status not in AnomalyFlag.AWAITING:
        # Decisao tomada nao se sobrescreve: `reviewed_by` e a trilha.
        messages.error(request, "Este caso já foi decidido.")
        return redirect("painel")

    retinha = flag.holds_billing
    flag.status = decisao
    flag.reviewed_by_user = _app_user(request)
    flag.reviewed_at = timezone.now()
    flag.save(update_fields=["status", "reviewed_by_user", "reviewed_at"])
    if flag.session_id:
        sync_session(flag.session_id)

    # A mensagem diz o que aconteceu com o DINHEIRO, e isso depende do que a
    # flag duvidava: so promete retencao ou liberacao quando houve.
    if decisao == "accepted" and flag.holds_billing:
        if retinha:
            messages.success(request, "Problema confirmado. A cobrança segue retida até você registrar o desfecho do caso.")
        else:
            messages.success(request, "Sugestão confirmada. A cobrança passa a ficar retida até você registrar o desfecho do caso.")
    elif decisao == "accepted":
        messages.success(request, "Problema confirmado. Nenhuma cobrança foi retida: registre o desfecho quando o caso for tratado.")
    elif retinha:
        messages.success(request, "Caso encerrado sem problema: a cobrança foi liberada. A decisão fica registrada no seu nome.")
    else:
        messages.success(request, "Aviso descartado. A decisão fica registrada no seu nome.")
    return redirect("painel")


@login_required
@require_POST
def resolver_anomalia(request, flag_id: int):
    """A saida do caso confirmado. Sem ela, confirmar um problema era condenar
    a fatura a ficar retida para sempre."""
    if not _is_manager(request):
        raise Http404
    flag = get_object_or_404(_flags_do_condo(_condo()), pk=flag_id, status=AnomalyFlag.Status.ACCEPTED)
    desfecho = (request.POST.get("desfecho") or "").strip()[:500]
    if not desfecho:
        messages.error(request, "Descreva o que foi feito: liberar cobrança retida exige registro.")
        return redirect("painel")

    retinha = flag.holds_billing
    flag.status = AnomalyFlag.Status.RESOLVED
    flag.resolution = desfecho
    flag.resolved_at = timezone.now()
    flag.save(update_fields=["status", "resolution", "resolved_at"])
    if flag.session_id:
        sync_session(flag.session_id)
    messages.success(request, "Desfecho registrado. A cobrança foi liberada." if retinha else "Desfecho registrado.")
    return redirect("painel")


@login_required
def relatorio(request):
    """Relatorio mensal para a assembleia.

    O que o sindico precisa levar impresso: quanto entrou, de quem, quanto
    ficou de residuo do rateio e o que esta em auditoria.
    """
    if not _is_manager(request):
        raise Http404
    condo = _condo()
    comp = _competence_from(request)

    faturas = list(
        Invoice.objects.filter(condominium=condo, competence=str(comp))
        .select_related("unit", "visitor_user")
        .prefetch_related("lines")
    )
    # Ordenacao NUMERICA. `order_by("unit__label")` ordena como texto e produz
    # 102, 105, 110, 12, 21 -- que e correto para o banco e absurdo para quem le
    # uma lista de apartamentos.
    faturas.sort(key=lambda f: (
        f.unit is None,
        int(f.unit.label) if f.unit and f.unit.label.isdigit() else 0,
        f.unit.label if f.unit else "",
    ))
    energia = sum(
        (ln.amount for f in faturas for ln in f.lines.all() if ln.kind == "session"),
        Decimal("0.00"),
    )
    disponibilidade = sum(
        (ln.amount for f in faturas for ln in f.lines.all() if ln.kind == "availability_fee"),
        Decimal("0.00"),
    )
    ajustes = sum(
        (ln.amount for f in faturas for ln in f.lines.all() if ln.kind == "tariff_adjustment"),
        Decimal("0.00"),
    )
    kwh = sum(
        (Decimal(ln.energy_kwh) for f in faturas for ln in f.lines.all()
         if ln.kind == "session" and ln.energy_kwh),
        Decimal("0.000"),
    )
    aderentes = enrolled_units(condo, comp)
    # A tarifa vem da primeira linha de SESSAO que existir -- a primeira fatura
    # da lista pode ser de uma unidade que so paga disponibilidade, e ai nao ha
    # tarifa nenhuma para mostrar.
    tarifa = next(
        (ln.unit_price_kwh for f in faturas for ln in f.lines.all()
         if ln.kind == "session" and ln.unit_price_kwh),
        None,
    )

    # Agregados por fatura para a tabela da assembleia. Calculados a partir das
    # LINHAS ja persistidas, e nao por uma consulta paralela: o relatorio tem de
    # mostrar exatamente o que o morador ve no extrato dele, ou vira outra fonte
    # de verdade -- que e como um rateio perde a confianca.
    for f in faturas:
        linhas = list(f.lines.all())
        f.n_sessoes = sum(1 for ln in linhas if ln.kind == "session")
        f.kwh = sum((Decimal(ln.energy_kwh) for ln in linhas
                     if ln.kind == "session" and ln.energy_kwh), Decimal("0.000"))
        f.v_energia = sum((ln.amount for ln in linhas if ln.kind == "session"), Decimal("0.00"))
        f.v_taxa = sum((ln.amount for ln in linhas if ln.kind == "availability_fee"), Decimal("0.00"))
        f.v_ajuste = sum((ln.amount for ln in linhas if ln.kind == "tariff_adjustment"), Decimal("0.00"))

    if request.GET.get("formato") == "csv":
        return _relatorio_csv(comp, faturas)

    return render(request, "portal/relatorio.html", {
        "condo": condo,
        "competencia": comp,
        "faturas": faturas,
        "energia": energia,
        "disponibilidade": disponibilidade,
        "ajustes": ajustes,
        "total": energia + disponibilidade + ajustes,
        "kwh": kwh,
        "aderentes": len(aderentes),
        "tarifa": tarifa,
        "em_auditoria": sum(1 for f in faturas if f.status == Invoice.Status.UNDER_REVIEW),
    })


def _br(valor) -> str:
    return "" if valor is None else str(valor).replace(".", ",")


def _relatorio_csv(comp, faturas) -> HttpResponse:
    """Exportacao para quem vai conferir na planilha -- e sempre tem alguem."""
    import csv, io

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["competencia", "unidade", "tipo", "descricao", "kwh", "tarifa", "valor", "auditoria"])
    for f in faturas:
        alvo = f.unit.label if f.unit else f"visitante:{f.visitor_user.name}"
        for ln in f.lines.all():
            w.writerow([
                comp, alvo, ln.get_kind_display(), ln.description,
                _br(ln.energy_kwh), _br(ln.unit_price_kwh), _br(ln.amount),
                "sim" if ln.flagged_for_audit else "não",
            ])
    # BOM na frente: sem ele o Excel abre o arquivo como Latin-1 e "não" vira
    # "nÃ£o". E virgula decimal nos TRES numeros: com ponto, o Excel pt-BR le
    # "11.400" kWh como onze mil e quatrocentos.
    resp = HttpResponse("\ufeff" + buf.getvalue(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="rateio-{comp}.csv"'
    return resp


# --------------------------------------------------------------------------
# Portal do morador
# --------------------------------------------------------------------------

@login_required
def extrato(request):
    """A fatura explicada linha a linha, e as sessoes que a formaram."""
    au = _app_user(request)
    if not au or not au.unit:
        raise Http404("usuário sem unidade vinculada")

    comp = _competence_from(request)
    fatura = (
        Invoice.objects.filter(unit=au.unit, competence=str(comp))
        .prefetch_related("lines__session__credential__user")
        .first()
    )
    # "Outras" competencias -- a atual e a pagina onde a pessoa ja esta, e um
    # botao que aponta para a propria tela e ruido.
    competencias = [
        c for c in Invoice.objects.filter(unit=au.unit)
        .values_list("competence", flat=True).distinct().order_by("-competence")
        if c != str(comp)
    ]

    # Ordem de leitura, nao alfabetica: primeiro o que consumi, depois o que
    # rateio, por ultimo o acerto do mes passado.
    ORDEM = {"session": 0, "availability_fee": 1, "tariff_adjustment": 2}
    linhas = (
        sorted(fatura.lines.all(), key=lambda l: (ORDEM.get(l.kind, 9), l.id))
        if fatura else []
    )
    kwh_total = sum(
        (Decimal(ln.energy_kwh) for ln in linhas if ln.kind == "session" and ln.energy_kwh),
        Decimal("0.000"),
    )
    # Quem carregou. `descricao_amigavel` suprime o nome de proposito: na tela
    # do proprio morador, repeti-lo em cada linha e ruido. Numa unidade com mais
    # de uma pessoa credenciada (o caso do casal com dois veiculos) essa
    # supressao apaga informacao: as recargas do outro ficam indistinguiveis
    # das proprias, e a fatura e uma so. Entao o rotulo aparece apenas quando
    # ha mais de um credenciado na unidade.
    credenciados = {
        ln.session.credential.user_id
        for ln in linhas
        if ln.kind == "session" and ln.session_id and ln.session.credential_id
    }
    if len(credenciados) > 1:
        for ln in linhas:
            if ln.kind == "session" and ln.session_id and ln.session.credential_id:
                cred = ln.session.credential
                ln.quem = cred.user.name
                ln.como = cred.get_kind_display()

    melhor_janela = _melhor_janela(au.unit.condominium)
    return render(request, "portal/extrato.html", {
        "kwh_total": kwh_total,
        "n_sessoes": sum(1 for ln in linhas if ln.kind == "session"),
        "app_user": au,
        "unidade": au.unit,
        "competencia": comp,
        "competencias": competencias,
        "fatura": fatura,
        "linhas": linhas,
        "melhor_janela": melhor_janela,
    })


def _melhor_janela(condominium) -> dict | None:
    """A hora com menos disputa pelo ponto, nos ultimos 90 dias.

    Nao e IA nem precisa ser: e contagem. Registrado assim de proposito -- a
    Sprint 1 decidiu que IA que nao ganha de uma consulta simples nao entra.
    """
    desde = datetime.combine(DEMO_TODAY - timedelta(days=90), time.min, tzinfo=condo_tz())
    sessoes = ChargingSession.objects.filter(
        charge_point__condominium=condominium, session_start__gte=desde, session_start__lt=desde + timedelta(days=91)
    ).values_list("session_start", flat=True)

    contagem = [0] * 24
    for s in sessoes:
        contagem[s.astimezone(condo_tz()).hour] += 1
    if not any(contagem):
        return None

    # So faz sentido sugerir horario noturno: e quando o carro esta na garagem.
    noturnas = [(h, contagem[h]) for h in list(range(18, 24)) + list(range(0, 7))]
    # Amostra pequena nao sustenta recomendacao. Sugerir horario com base em
    # duas ou tres recargas seria achismo com cara de estatistica.
    if sum(n for _, n in noturnas) < MIN_SESSOES_PARA_SUGERIR:
        return None

    melhor = min(noturnas, key=lambda t: t[1])
    pior = max(noturnas, key=lambda t: t[1])
    return {
        "hora": melhor[0],
        "hora_texto": _hora_humana(melhor[0]),
        "sessoes": melhor[1],
        "pior_hora": pior[0],
        "pior_hora_texto": _hora_humana(pior[0]),
        "pior_sessoes": pior[1],
    }


@login_required
@require_POST
def contestar(request, linha_id: int):
    """Contestacao informada: o morador ve a evidencia antes de discordar."""
    au = _app_user(request)
    linha = get_object_or_404(InvoiceLine.objects.select_related("invoice", "session"), pk=linha_id)
    if not au or not au.unit_id or linha.invoice.unit_id != au.unit_id:
        raise Http404
    if linha.session_id is None:
        messages.error(request, "Só recargas podem ser contestadas por aqui. Para a taxa ou o ajuste, fale com a administração.")
        return redirect("extrato")

    motivo = (request.POST.get("motivo") or "").strip()[:500]
    if not motivo:
        messages.error(request, "Descreva o motivo da contestação.")
        return redirect("extrato")
    if AnomalyFlag.objects.filter(
        session_id=linha.session_id, detector="morador", status=AnomalyFlag.Status.CONTESTED
    ).exists():
        messages.info(request, "Esta recarga já está contestada e aguarda a decisão do síndico.")
        return redirect("extrato")

    AnomalyFlag.objects.create(
        session=linha.session,
        charge_point=linha.session.charge_point,
        category=AnomalyFlag.Category.CONSUMPTION,
        explanation=f"Contestação do morador ({au.name}, unidade {au.unit.label}): {motivo}",
        detector="morador",
        status=AnomalyFlag.Status.CONTESTED,
    )
    sync_session(linha.session_id)

    messages.success(
        request, "Contestação registrada. A recarga entrou na fila de decisão do síndico e a cobrança fica suspensa até lá."
    )
    return redirect("extrato")


# --------------------------------------------------------------------------
# Entrada de dados -- o que chegou, o que ficou de fora, e o que nao tem dono
# --------------------------------------------------------------------------

@login_required
def entrada(request):
    """A porta de entrada, vista por quem responde por ela.

    Tres perguntas que o gestor faz e que nenhuma tela respondia: o dado esta
    chegando? algo foi recusado? ha energia que ninguem assumiu?
    """
    if not _is_manager(request):
        raise Http404
    condo = _condo()
    execucoes = list(
        IngestionRun.objects.filter(Q(condominium=condo) | Q(condominium__isnull=True))[:8]
    )
    pendentes = list(
        RawEvent.objects.filter(outcome__in=RawEvent.QUARANTINE, resolved_at__isnull=True)[:20]
    )
    sem_dono = orphans.orphan_summary(condo)
    for s in sem_dono["sessoes"]:
        s.autostart = orphans.is_autostart(s.auth_id)
        s.valor = (Decimal(s.energy_kwh) * Decimal(s.applied_tariff_kwh or 0)).quantize(Decimal("0.01"))
    fontes = (
        ChargingSession.objects.filter(charge_point__condominium=condo)
        .values("source", "measurement_source")
        .annotate(n=Count("id"), kwh=Sum("energy_kwh"), ultima=Max("session_start"))
        .order_by("-n")
    )
    moradores = (
        AppUser.objects.filter(unit__condominium=condo, role=AppUser.Role.RESIDENT)
        .select_related("unit").order_by("unit__label", "name")
    )
    return render(request, "portal/entrada.html", {
        "condo": condo,
        "execucoes": execucoes,
        "pendentes": pendentes,
        "sem_dono": sem_dono,
        "fontes": fontes,
        "moradores": moradores,
    })


@login_required
@require_POST
def atribuir_recarga(request, session_id: int):
    if not _is_manager(request):
        raise Http404
    condo = _condo()
    sessao = get_object_or_404(orphans.orphan_sessions(condo), pk=session_id)
    morador = get_object_or_404(AppUser, pk=request.POST.get("morador") or 0, unit__condominium=condo)
    try:
        if request.POST.get("alcance") == "cartao":
            n = orphans.register_card(condo, sessao.auth_id, morador)
            messages.success(request, f"Cartão {sessao.auth_id} cadastrado para {morador.name}: {n} recarga(s) ganharam dono.")
        else:
            orphans.assign_session(sessao, morador)
            messages.success(
                request,
                f"Recarga atribuída a {morador.name} (unidade {morador.unit.label}). "
                "Entra na próxima fatura aberta; meses já fechados não são reescritos.",
            )
    except orphans.OrphanError as exc:
        messages.error(request, str(exc).capitalize() + ".")
    return redirect("entrada")
