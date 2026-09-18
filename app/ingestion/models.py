"""Diario operacional da ingestao.

O esquema de DOMINIO continua com as 14 entidades da Frente 3-C, em `core`. O
que mora aqui e encanamento: duas tabelas que nao descrevem o condominio, e sim
o que aconteceu na porta de entrada. A separacao e deliberada -- apagar estas
tabelas nao muda uma fatura; apagar uma de `core` muda.

Por que existem. O gateway da primeira versao respondia "quantas sessoes
entraram", e so. Tres perguntas que uma integracao real faz no primeiro mes
ficavam sem resposta:

1. *O que exatamente a fonte mandou?* A sessao persistida e a versao ja
   traduzida. Se o mapeamento do adaptador estiver errado (e o do SEMS e
   hipotese documentada, nao contrato confirmado), o dado original se perdeu e
   nao ha o que reprocessar. `RawEvent.payload` guarda o registro como chegou.
2. *O que foi recusado, e por que?* Registro malformado era excecao que
   derrubava o lote. Agora vira `RawEvent` com `outcome=rejected` e motivo
   legivel: uma quarentena que se reprocessa depois de corrigida a causa.
3. *De onde continuar?* Fonte consultada por polling precisa de marca d'agua.
   `IngestionRun.cursor_after` e a da ultima execucao bem-sucedida.
"""

from django.db import models
from django.db.models import Q


class IngestionRun(models.Model):
    """Uma execucao do gateway: um arquivo lido, um pull, um POST recebido."""

    class Mode(models.TextChoices):
        FILE = "file", "Arquivo"
        PULL = "pull", "Consulta a fonte (polling)"
        PUSH = "push", "Entrega pela fonte (webhook)"
        REPLAY = "replay", "Reprocessamento da quarentena"

    class Status(models.TextChoices):
        RUNNING = "running", "Em execução"
        OK = "ok", "Concluída"
        PARTIAL = "partial", "Concluída com recusas"
        FAILED = "failed", "Falhou"

    condominium = models.ForeignKey(
        "core.Condominium",
        on_delete=models.CASCADE,
        related_name="ingestion_runs",
        null=True,
        blank=True,
        help_text="Nulo quando a entrega e por push: o condominio se descobre "
        "pelo numero de serie do carregador, registro a registro.",
    )
    source = models.TextField("fonte")
    mode = models.TextField("modo", choices=Mode.choices, default=Mode.FILE)
    status = models.TextField("situação", choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField("início", auto_now_add=True)
    finished_at = models.DateTimeField("fim", null=True, blank=True)
    cursor_before = models.TextField("marca d'água de partida", null=True, blank=True)
    cursor_after = models.TextField("marca d'água de chegada", null=True, blank=True)

    received = models.PositiveIntegerField("registros recebidos", default=0)
    created = models.PositiveIntegerField("sessões criadas", default=0)
    updated = models.PositiveIntegerField("sessões atualizadas", default=0)
    duplicates = models.PositiveIntegerField("duplicatas", default=0)
    rejected = models.PositiveIntegerField("recusados", default=0)
    unknown_point = models.PositiveIntegerField("carregador desconhecido", default=0)
    conflicts = models.PositiveIntegerField("conflitos", default=0)
    orphans = models.PositiveIntegerField("sessões órfãs", default=0)
    readings = models.PositiveIntegerField("leituras de telemetria", default=0)
    error = models.TextField("erro", null=True, blank=True)

    class Meta:
        db_table = "ingestion_run"
        verbose_name = "execução de ingestão"
        verbose_name_plural = "execuções de ingestão"
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["source", "-started_at"])]

    def __str__(self):
        return f"{self.source} @ {self.started_at:%Y-%m-%d %H:%M} ({self.status})"


class RawEvent(models.Model):
    """O registro como a fonte o entregou, e o que o gateway fez com ele."""

    class Outcome(models.TextChoices):
        CREATED = "created", "Sessão criada"
        UPDATED = "updated", "Sessão atualizada"
        DUPLICATE = "duplicate", "Duplicata (ignorada)"
        TELEMETRY = "telemetry", "Telemetria fora de sessão"
        REJECTED = "rejected", "Recusado"
        UNKNOWN_POINT = "unknown_point", "Carregador desconhecido"
        CONFLICT = "conflict", "Conflito com sessão já faturada"

    #: desfechos que ficam na quarentena a espera de acao humana
    QUARANTINE = ("rejected", "unknown_point", "conflict")

    run = models.ForeignKey(IngestionRun, on_delete=models.CASCADE, related_name="events")
    source = models.TextField("fonte")
    source_ref = models.TextField("identificador na fonte", null=True, blank=True)
    received_at = models.DateTimeField("recebido em", auto_now_add=True)
    payload = models.JSONField("registro bruto")
    outcome = models.TextField("desfecho", choices=Outcome.choices)
    reason = models.TextField(
        "motivo",
        null=True,
        blank=True,
        help_text="Por que foi recusado, ou o que mudou na atualizacao.",
    )
    warnings = models.JSONField(
        "avisos",
        default=list,
        blank=True,
        help_text="O registro entrou, mas algo merece olho humano: credencial "
        "revogada, sobreposicao com outra sessao no mesmo conector.",
    )
    session = models.ForeignKey(
        "core.ChargingSession",
        on_delete=models.SET_NULL,
        related_name="raw_events",
        null=True,
        blank=True,
    )
    resolved_at = models.DateTimeField(
        "resolvido em",
        null=True,
        blank=True,
        help_text="Preenchido quando um reprocessamento posterior aceitou o registro.",
    )

    class Meta:
        db_table = "ingestion_raw_event"
        verbose_name = "registro bruto"
        verbose_name_plural = "registros brutos"
        ordering = ["-received_at", "-id"]
        indexes = [
            models.Index(fields=["source", "source_ref"]),
            models.Index(
                fields=["outcome"],
                condition=Q(outcome__in=["rejected", "unknown_point", "conflict"]),
                name="raw_event_quarantine_idx",
            ),
        ]

    def __str__(self):
        return f"{self.source}:{self.source_ref or '-'} -> {self.outcome}"
