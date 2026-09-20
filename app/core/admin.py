"""Admin de inspeção das 14 entidades da Frente 3-C.

O portal (`/painel/`, `/extrato/`) é a interface de trabalho: carrega as regras
de negócio, o ciclo de vida da anomalia e a trilha de auditoria. Este admin
existe para outra coisa -- olhar o dado cru quando algo não fecha, sem escrever
SQL. Por isso cada `ModelAdmin` daqui privilegia navegação (filtro, busca,
hierarquia de data) e evita o dropdown de chave estrangeira: em `ChargingSession`
e `TelemetryReading` ele carregaria a tabela inteira a cada abertura de
formulário.
"""

from django.contrib import admin

from .models import (
    AnomalyFlag,
    AppUser,
    ChargePoint,
    ChargingSession,
    Condominium,
    Credential,
    Invoice,
    InvoiceLine,
    ProgramEnrollment,
    TariffPeriod,
    TariffReconciliation,
    TelemetryReading,
    Unit,
    Vehicle,
)

admin.site.site_header = "EV ChargeOps — dados crus"
admin.site.site_title = "EV ChargeOps"
admin.site.index_title = "As 14 entidades da Frente 3-C"


# --------------------------------------------------------------------------
# Cadastro: condomínio, unidade, adesão
# --------------------------------------------------------------------------


@admin.register(Condominium)
class CondominiumAdmin(admin.ModelAdmin):
    list_display = ("name", "utility_name", "declared_power_kw", "visitor_price_kwh")
    search_fields = ("name", "utility_name")
    ordering = ("name",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("label", "block", "condominium", "ideal_fraction")
    list_filter = ("condominium", "block")
    search_fields = ("label", "block")
    list_select_related = ("condominium",)
    ordering = ("condominium", "label")


@admin.register(ProgramEnrollment)
class ProgramEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("unit", "start_date", "end_date")
    list_filter = ("start_date", "unit__condominium")
    search_fields = ("unit__label",)
    list_select_related = ("unit", "unit__condominium")
    date_hierarchy = "start_date"
    ordering = ("-start_date",)


# --------------------------------------------------------------------------
# Pessoas e o que as identifica no carregador
# --------------------------------------------------------------------------


@admin.register(AppUser)
class AppUserAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "role", "unit", "created_at")
    list_filter = ("role", "unit__condominium")
    search_fields = ("name", "email")
    list_select_related = ("unit",)
    raw_id_fields = ("auth_user",)
    readonly_fields = ("created_at",)
    ordering = ("name",)


@admin.register(Credential)
class CredentialAdmin(admin.ModelAdmin):
    list_display = ("auth_tag", "kind", "status", "user", "valid_from")
    list_filter = ("kind", "status", "valid_from")
    # `auth_tag` é o que o carregador reporta: buscar por ele é o caminho de
    # toda investigação de sessão órfã.
    search_fields = ("auth_tag", "user__name", "user__email")
    list_select_related = ("user",)
    raw_id_fields = ("user",)
    ordering = ("-valid_from",)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("plate", "model", "battery_capacity_kwh", "user")
    search_fields = ("plate", "model", "user__name")
    list_select_related = ("user",)
    raw_id_fields = ("user",)
    ordering = ("plate",)


# --------------------------------------------------------------------------
# Equipamento, sessão e telemetria
# --------------------------------------------------------------------------


@admin.register(ChargePoint)
class ChargePointAdmin(admin.ModelAdmin):
    list_display = (
        "serial_number",
        "model",
        "location",
        "rated_power_kw",
        "condominium",
        "commissioned_at",
    )
    list_filter = ("condominium", "model")
    search_fields = ("serial_number", "model", "location")
    list_select_related = ("condominium",)
    ordering = ("condominium", "serial_number")


@admin.register(ChargingSession)
class ChargingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "charge_point",
        "credential",
        "session_start",
        "session_end",
        "energy_kwh",
        "status",
        "applied_tariff_kwh",
        "source",
    )
    list_filter = (
        "status",
        "auth_method",
        "measurement_source",
        "source",
        "session_start",
    )
    search_fields = ("auth_id", "source_ref", "charge_point__serial_number")
    list_select_related = ("charge_point", "credential", "credential__user")
    raw_id_fields = ("charge_point", "credential", "applied_tariff")
    date_hierarchy = "session_start"
    ordering = ("-session_start",)

    @admin.display(boolean=True, description="leitura final perdida")
    def final_reading_lost(self, obj):
        return obj.final_reading_lost

    readonly_fields = ("final_reading_lost",)


@admin.register(TelemetryReading)
class TelemetryReadingAdmin(admin.ModelAdmin):
    list_display = (
        "ts",
        "charge_point",
        "kind",
        "state",
        "power_kw",
        "energy_kwh_total",
        "session",
    )
    list_filter = ("kind", "state", "measurement_source", "ts")
    # Sem `search_fields`: a busca textual nesta tabela varre a série inteira.
    # O caminho é filtrar por ponto e data, e é para isso que serve a
    # hierarquia abaixo.
    list_select_related = ("charge_point", "session")
    raw_id_fields = ("charge_point", "session")
    date_hierarchy = "ts"
    ordering = ("-ts",)


# --------------------------------------------------------------------------
# Economia: vigência, reconciliação, fatura
# --------------------------------------------------------------------------


@admin.register(TariffPeriod)
class TariffPeriodAdmin(admin.ModelAdmin):
    list_display = (
        "condominium",
        "price_kwh",
        "availability_fee_month",
        "valid_from",
        "valid_to",
        "basis",
    )
    list_filter = ("condominium", "valid_from")
    search_fields = ("basis", "assembly_ref")
    list_select_related = ("condominium",)
    date_hierarchy = "valid_from"
    ordering = ("-valid_from",)


@admin.register(TariffReconciliation)
class TariffReconciliationAdmin(admin.ModelAdmin):
    list_display = (
        "condominium",
        "competence",
        "effective_price_kwh",
        "provisional_price_kwh",
        "delta_price_kwh",
        "settled_in_competence",
        "created_at",
    )
    list_filter = ("condominium", "competence")
    search_fields = ("competence", "settled_in_competence")
    list_select_related = ("condominium",)
    readonly_fields = ("created_at",)
    ordering = ("-competence",)


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    fields = (
        "kind",
        "description",
        "energy_kwh",
        "unit_price_kwh",
        "amount",
        "flagged_for_audit",
        "session",
        "reconciliation",
    )
    raw_id_fields = ("session", "reconciliation")
    show_change_link = True


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "competence",
        "unit",
        "visitor_user",
        "condominium",
        "status",
        "total_amount",
        "due_date",
    )
    list_filter = ("status", "competence", "condominium")
    search_fields = ("competence", "unit__label", "visitor_user__name")
    list_select_related = ("condominium", "unit", "visitor_user")
    raw_id_fields = ("unit", "visitor_user")
    date_hierarchy = "due_date"
    ordering = ("-competence", "unit__label")
    inlines = (InvoiceLineInline,)


@admin.register(InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "kind",
        "description",
        "energy_kwh",
        "unit_price_kwh",
        "amount",
        "flagged_for_audit",
    )
    list_filter = ("kind", "flagged_for_audit", "invoice__status")
    search_fields = ("description", "invoice__competence")
    list_select_related = ("invoice", "invoice__unit")
    raw_id_fields = ("invoice", "session", "reconciliation")
    ordering = ("-invoice__competence", "kind")

    @admin.display(description="descrição para o morador")
    def descricao_amigavel(self, obj):
        return obj.descricao_amigavel

    # Só no formulário de um registro: a propriedade toca `session` e em
    # listagem viraria uma query por linha.
    readonly_fields = ("descricao_amigavel",)


# --------------------------------------------------------------------------
# Anomalias
# --------------------------------------------------------------------------


class SeguraFaturaFilter(admin.SimpleListFilter):
    """Filtra pela pergunta que o síndico de fato faz: esta flag está segurando
    dinheiro de alguém AGORA?

    A resposta não é o `status` sozinho. `AnomalyFlag.holds_billing` combina
    três coisas -- a categoria põe o NÚMERO em dúvida (`BILLING_CATEGORIES`),
    o detector é regra ou mera sugestão (`SUGGESTING_DETECTORS`), e o caso
    ainda não teve desfecho (`HOLDING`). O queryset equivalente já existe em
    `AnomalyFlagQuerySet.holding()`.
    """

    title = "retenção de fatura"
    parameter_name = "segura"

    def lookups(self, request, model_admin):
        return (("1", "Segurando a fatura"), ("0", "Não segura"))

    def queryset(self, request, queryset):
        # A regra mora em `holding()` e só lá: o filtro a consulta, não a copia.
        # "Não segura" é o complemento puro, para concordar com a coluna
        # `segura fatura` -- inclui os casos encerrados E as flags operacionais,
        # que nunca seguraram nada. Quem quer só os encerrados filtra por situação.
        if self.value() == "1":
            return queryset.holding()
        if self.value() == "0":
            return queryset.exclude(pk__in=queryset.holding().values("pk"))
        return queryset


@admin.register(AnomalyFlag)
class AnomalyFlagAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "category",
        "status",
        "detector",
        "score",
        "segura_fatura",
        "session",
        "charge_point",
        "explanation",
    )
    list_filter = ("status", "category", "detector", SeguraFaturaFilter, "created_at")
    search_fields = ("explanation", "resolution")
    list_select_related = ("session", "charge_point", "reviewed_by_user")
    raw_id_fields = ("session", "charge_point", "reviewed_by_user")
    readonly_fields = ("created_at", "detector_legivel")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    @admin.display(boolean=True, description="segura fatura")
    def segura_fatura(self, obj):
        return obj.holds_billing

    @admin.display(description="detector, em português")
    def detector_legivel(self, obj):
        return obj.detector_legivel
