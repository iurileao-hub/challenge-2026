"""Endpoint de push: a fonte ENTREGA eventos, em vez de a plataforma busca-los.

    POST /api/v1/ingest/<fonte>/
    X-ChargeOps-Signature: sha256=<hmac-sha256 do corpo, em hexadecimal>
    {"events": [ {...}, {...} ]}

Autenticacao por segredo compartilhado, no padrao de webhook que GitHub e
Stripe usam: a fonte assina o CORPO BRUTO com HMAC-SHA256 e manda a assinatura
no cabecalho. Isso prova duas coisas de uma vez -- quem mandou conhece o
segredo, e o corpo nao foi alterado no caminho -- sem sessao, sem cookie e sem
CSRF (que protege navegador autenticado, e aqui nao ha navegador).

Replay de uma entrega antiga e inofensivo por construcao: a ingestao e
idempotente, e reenviar o mesmo lote devolve "duplicata" para tudo. Por isso
nao ha janela de timestamp na assinatura -- ela adicionaria dependencia de
relogio sincronizado sem fechar nenhum buraco real.

A resposta e 200 mesmo quando ha registros recusados: o LOTE foi recebido e
esta guardado; recusa individual vai para a quarentena e vem discriminada no
corpo. Responder 4xx faria a fonte reenviar para sempre um lote que nunca vai
passar. So respondem com erro as recusas do LOTE inteiro, que nao abrem
execucao no diario: metodo que nao e POST (405), endpoint desligado (503),
assinatura invalida (401), corpo ilegivel (400) e lote acima de MAX_EVENTS (413).
"""

import hashlib
import hmac
import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ingestion.adapters import EventStreamAdapter
from ingestion.gateway import IngestionGateway

MAX_EVENTS = 5000


def sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@csrf_exempt
@require_POST
def push_events(request, source: str):
    secret = settings.INGEST_PUSH_SECRETS.get(source)
    if not secret:
        return JsonResponse({"error": f"fonte '{source}' nao habilitada para push"}, status=503)

    recebida = request.headers.get("X-ChargeOps-Signature", "")
    # compare_digest: comparacao em tempo constante. `==` vaza, pelo tempo de
    # resposta, quantos caracteres iniciais da assinatura estavam certos.
    if not hmac.compare_digest(recebida, sign(request.body, secret)):
        return JsonResponse({"error": "assinatura invalida"}, status=401)

    try:
        body = json.loads(request.body)
        events = body["events"] if isinstance(body, dict) else body
        if not isinstance(events, list):
            raise ValueError("'events' precisa ser uma lista")
    except (ValueError, KeyError, TypeError) as exc:
        return JsonResponse({"error": f"corpo ilegivel: {exc}"}, status=400)
    if len(events) > MAX_EVENTS:
        return JsonResponse({"error": f"lote acima de {MAX_EVENTS} eventos"}, status=413)

    report = IngestionGateway().ingest(EventStreamAdapter(events, source=source))
    return JsonResponse({
        "run": report.run_id,
        "received": report.received,
        "created": report.created,
        "updated": report.updated,
        "duplicates": report.duplicates,
        "telemetry": report.readings_ingested,
        "quarantined": report.quarantined,
        "rejections": report.rejections[:20],
    })
