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
from intelligence.forecast import forecast

#: A demo opera sobre junho/2026, que e a competencia do mes ficticio do dossie.
DEMO_TODAY = date(2026, 6, 30)


def _app_user(request) -> AppUser | None:
    return AppUser.objects.filter(auth_user=request.user).select_related("unit").first()


def _is_manager(request) -> bool:
    au = _app_user(request)
    return bool(au and au.role == AppUser.Role.MANAGER)


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
    condo = Condominium.objects.first()
    comp = _current_competence()

    sessions = list(billable_sessions(condo, comp))
    kwh_mes = sum((Decimal(s.energy_kwh) for s in sessions), Decimal("0.000"))
    aderentes = enrolled_units(condo, comp)

    faturas = Invoice.objects.filter(condominium=condo, competence=str(comp))
    receita = faturas.aggregate(t=Sum("total_amount"))["t"] or Decimal("0.00")

    anomalias = (
        AnomalyFlag.objects.filter(status=AnomalyFlag.Status.OPEN)
        .filter(Q(session__charge_point__condominium=condo) | Q(charge_point__condominium=condo))
        .select_related("session__credential__user__unit", "charge_point")
        .order_by("-created_at")
    )

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

    return render(request, "portal/painel.html", {
        "condo": condo,
        "competencia": comp,
        "kwh_mes": kwh_mes,
        "sessoes_mes": len(sessions),
        "aderentes": len(aderentes),
        "receita": receita,
        "faturas": faturas.count(),
        "em_auditoria": faturas.filter(status=Invoice.Status.UNDER_REVIEW).count(),
        "anomalias": anomalias,
        "previsao": previsao,
        "pontos": pontos,
        "ocupacao": [{"hora": h, "n": n, "pct": int(n / pico * 100)} for h, n in enumerate(ocupacao)],
    })


@login_required
@require_POST
def revisar_anomalia(request, flag_id: int):
    """O humano decide. A IA nunca fecha o proprio caso."""
    if not _is_manager(request):
        raise Http404
    flag = get_object_or_404(AnomalyFlag, pk=flag_id)
    decisao = request.POST.get("decisao")
    if decisao not in {"accepted", "dismissed"}:
        messages.error(request, "Decisão inválida.")
        return redirect("painel")

    flag.status = decisao
    flag.reviewed_by_user = _app_user(request)
    flag.reviewed_at = timezone.now()
    flag.save(update_fields=["status", "reviewed_by_user", "reviewed_at"])

    # A decisao volta para a fatura -- e as duas decisoes NAO sao simetricas.
    #
    # Descartar significa "nao havia problema": a linha sai da auditoria.
    # Confirmar significa o oposto -- o problema e real, e a linha PERMANECE
    # marcada, com a fatura retida, ate que o caso se resolva. Tratar as duas
    # como equivalentes (ambas tiram a flag de `open`) fecharia a fatura
    # justamente no caso em que o sindico acabou de dizer que ha algo errado.
    if flag.session_id:
        linhas = InvoiceLine.objects.filter(session_id=flag.session_id)
        ainda_aberta = AnomalyFlag.objects.filter(
            session_id=flag.session_id,
            status__in=[AnomalyFlag.Status.OPEN, AnomalyFlag.Status.ACCEPTED,
                        AnomalyFlag.Status.CONTESTED],
        ).exists()
        for linha in linhas:
            linha.flagged_for_audit = ainda_aberta or linha.session.meter_stop is None
            linha.save(update_fields=["flagged_for_audit"])
            inv = linha.invoice
            if not inv.lines.filter(flagged_for_audit=True).exists() and inv.status == Invoice.Status.UNDER_REVIEW:
                inv.status = Invoice.Status.CLOSED
                inv.save(update_fields=["status"])

    verbo = "confirmada" if decisao == "accepted" else "descartada"
    messages.success(request, f"Anomalia {verbo}. Quem revisou e quando fica registrado na trilha de auditoria.")
    return redirect("painel")


@login_required
def relatorio(request):
    """Relatorio mensal para a assembleia.

    O que o sindico precisa levar impresso: quanto entrou, de quem, quanto
    ficou de residuo do rateio e o que esta em auditoria.
    """
    if not _is_manager(request):
        raise Http404
    condo = Condominium.objects.first()
    comp = Competence.parse(request.GET.get("competencia", str(_current_competence())))

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
                ln.energy_kwh or "", ln.unit_price_kwh or "",
                str(ln.amount).replace(".", ","),
                "sim" if ln.flagged_for_audit else "não",
            ])
    resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
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

    comp = Competence.parse(request.GET.get("competencia", str(_current_competence())))
    fatura = (
        Invoice.objects.filter(unit=au.unit, competence=str(comp))
        .prefetch_related("lines__session__credential__user")
        .first()
    )
    competencias = list(
        Invoice.objects.filter(unit=au.unit).values_list("competence", flat=True).distinct().order_by("-competence")
    )

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
        charge_point__condominium=condominium, session_start__gte=desde
    ).values_list("session_start", flat=True)

    contagem = [0] * 24
    for s in sessoes:
        contagem[s.astimezone(condo_tz()).hour] += 1
    if not any(contagem):
        return None

    # So faz sentido sugerir horario noturno: e quando o carro esta na garagem.
    noturnas = [(h, contagem[h]) for h in list(range(18, 24)) + list(range(0, 7))]
    melhor = min(noturnas, key=lambda t: t[1])
    pior = max(noturnas, key=lambda t: t[1])
    return {
        "hora": melhor[0],
        "sessoes": melhor[1],
        "pior_hora": pior[0],
        "pior_sessoes": pior[1],
    }


@login_required
@require_POST
def contestar(request, linha_id: int):
    """Contestacao informada: o morador ve a evidencia antes de discordar."""
    au = _app_user(request)
    linha = get_object_or_404(InvoiceLine, pk=linha_id)
    if not au or linha.invoice.unit_id != au.unit_id:
        raise Http404

    motivo = (request.POST.get("motivo") or "").strip()
    if not motivo:
        messages.error(request, "Descreva o motivo da contestação.")
        return redirect("extrato")

    AnomalyFlag.objects.create(
        session=linha.session,
        charge_point=linha.session.charge_point if linha.session else None,
        category=AnomalyFlag.Category.CONSUMPTION,
        explanation=f"Contestação do morador ({au.name}, unidade {au.unit.label}): {motivo}",
        detector="morador",
        status=AnomalyFlag.Status.CONTESTED,
    )
    linha.flagged_for_audit = True
    linha.save(update_fields=["flagged_for_audit"])
    inv = linha.invoice
    if inv.status == Invoice.Status.CLOSED:
        inv.status = Invoice.Status.UNDER_REVIEW
        inv.save(update_fields=["status"])

    messages.success(
        request, "Contestação registrada. A linha entra na fila de auditoria do síndico."
    )
    return redirect("extrato")
