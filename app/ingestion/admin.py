"""Admin do diário operacional da ingestão.

Não são entidades de domínio -- são as duas tabelas que contam o que aconteceu
na porta de entrada. No admin elas são deliberadamente somente-leitura: o
`RawEvent` é o registro *como a fonte o entregou*, e editar isso à mão apagaria
justamente a evidência que a tabela existe para preservar. Reprocessar
quarentena se faz pelo gateway, não por formulário.
"""

from django.contrib import admin

from .models import IngestionRun, RawEvent


class SomenteLeituraAdmin(admin.ModelAdmin):
    """Janela de inspeção: navega, filtra, não escreve."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class RawEventInline(admin.TabularInline):
    model = RawEvent
    extra = 0
    can_delete = False
    fields = ("received_at", "source_ref", "outcome", "reason", "session")
    readonly_fields = fields
    show_change_link = True
    # Uma execução pode trazer milhares de registros; o inline mostra uma
    # amostra e o link "ver todos" leva à listagem filtrada.
    max_num = 25

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(IngestionRun)
class IngestionRunAdmin(SomenteLeituraAdmin):
    list_display = (
        "started_at",
        "source",
        "mode",
        "status",
        "condominium",
        "received",
        "created",
        "updated",
        "duplicates",
        "rejected",
        "orphans",
        "finished_at",
    )
    list_filter = ("status", "mode", "source", "started_at")
    search_fields = ("source", "error", "cursor_after")
    list_select_related = ("condominium",)
    date_hierarchy = "started_at"
    inlines = (RawEventInline,)


@admin.register(RawEvent)
class RawEventAdmin(SomenteLeituraAdmin):
    list_display = (
        "received_at",
        "source",
        "source_ref",
        "outcome",
        "reason",
        "session",
        "resolved_at",
    )
    list_filter = ("outcome", "source", "received_at")
    search_fields = ("source_ref", "reason")
    list_select_related = ("run", "session")
    raw_id_fields = ("run", "session")
    date_hierarchy = "received_at"
