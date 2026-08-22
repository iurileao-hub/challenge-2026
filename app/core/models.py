"""
As 14 entidades da Frente 3-C (docs/frente-3-arquitetura.md, "Opcao C").

Convencoes herdadas do dossie, mantidas deliberadamente:

- identificadores em ingles (decisao de modelagem 1);
- dinheiro em DECIMAL(10,2), energia em DECIMAL(9,3), tarifas em DECIMAL(8,4);
- timestamps com fuso, persistidos em UTC;
- enums como TEXT + CHECK, nao como tipo ENUM do Postgres -- acrescentar um
  valor a um CHECK e uma migracao barata; a um ENUM, nao.

Os `db_table` sao explicitos e iguais aos nomes do dossie: e o que torna a
"aposta verificavel" da Frente 3-C conferivel tabela a tabela.
"""

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class MeasurementSource(models.TextChoices):
    """De onde veio o kWh. A Frente 2 exigiu rastrear isto desde o dia 1:
    medicao com lastro metrologico (MID) vale mais que numero de API."""

    CLOUD = "cloud", "Nuvem do fabricante"
    MODBUS_LOCAL = "modbus_local", "Modbus TCP local"
    MID_METER = "mid_meter", "Medidor MID (RS-485)"


class Condominium(models.Model):
    name = models.TextField("nome")
    utility_name = models.TextField("distribuidora")
    declared_power_kw = models.DecimalField(
        "potência declarada (kW)",
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Teto da instalacao de recarga (Lei 18.403 / IT-41); "
        "limite do alerta de potencia da abordagem 1 de IA.",
    )
    visitor_price_kwh = models.DecimalField(
        "tarifa de visitante (R$/kWh)",
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Nula desabilita recarga de visitante.",
    )

    class Meta:
        db_table = "condominium"
        verbose_name = "condomínio"
        verbose_name_plural = "condomínios"

    def __str__(self):
        return self.name


class Unit(models.Model):
    """A unidade condominial -- o sujeito da fatura (decisao 3)."""

    condominium = models.ForeignKey(
        Condominium, on_delete=models.PROTECT, related_name="units"
    )
    label = models.TextField("identificação")
    block = models.TextField("bloco", null=True, blank=True)
    ideal_fraction = models.DecimalField(
        "fração ideal",
        max_digits=8,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Cadastral. NAO participa do rateio (decisao 8): o rateio da "
        "taxa de disponibilidade e igual entre unidades aderentes.",
    )

    class Meta:
        db_table = "unit"
        verbose_name = "unidade"
        constraints = [
            models.UniqueConstraint(
                fields=["condominium", "label"], name="unit_label_unique_per_condo"
            )
        ]

    def __str__(self):
        return f"Unidade {self.label}" + (f" (bloco {self.block})" if self.block else "")


class ProgramEnrollment(models.Model):
    """Adesao ao programa de recarga.

    Entidade com datas, e nao booleano em `unit` (decisao 8): `N_aderentes` e
    funcao do tempo -- precisa ser reconstruivel para qualquer competencia
    passada, e e a base do pro rata de adesao no meio do mes.
    """

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="enrollments")
    start_date = models.DateField("início da adesão")
    end_date = models.DateField("fim da adesão", null=True, blank=True)

    class Meta:
        db_table = "program_enrollment"
        verbose_name = "adesão ao programa"
        verbose_name_plural = "adesões ao programa"
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="enrollment_end_after_start",
            )
        ]

    def __str__(self):
        fim = self.end_date.isoformat() if self.end_date else "ativa"
        return f"{self.unit} {self.start_date.isoformat()} -> {fim}"


class AppUser(models.Model):
    """A pessoa. Separada de `django.contrib.auth.User` de proposito: nem todo
    morador tem login (o cartao RFID basta para gerar sessao), e o visitante
    existe no rateio sem nunca acessar o portal."""

    class Role(models.TextChoices):
        RESIDENT = "resident", "Morador"
        MANAGER = "manager", "Gestor/síndico"
        VISITOR = "visitor", "Visitante"

    name = models.TextField("nome")
    email = models.EmailField("e-mail", unique=True)
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="residents",
        null=True,
        blank=True,
        help_text="Nula para visitante (decisao 3) e para gestor sem unidade.",
    )
    role = models.TextField("papel", choices=Role.choices, default=Role.RESIDENT)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    auth_user = models.OneToOneField(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profile",
        help_text="Login do portal, quando existir.",
    )

    class Meta:
        db_table = "app_user"
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=["resident", "manager", "visitor"]),
                name="app_user_role_valid",
            ),
            # Visitante nunca pertence a unidade: e o que o mantem fora do rateio.
            models.CheckConstraint(
                condition=~Q(role="visitor") | Q(unit__isnull=True),
                name="app_user_visitor_has_no_unit",
            ),
        ]

    def __str__(self):
        return self.name


class Credential(models.Model):
    """O que inicia a sessao (decisao 2).

    Entidade propria, e nao um campo `tag_rfid` no usuario, porque o atributo
    quebraria tres casos reais: usuario com cartao E app, cartao perdido e
    substituido (a credencial antiga precisa continuar resolvendo o historico) e
    visitante com credencial avulsa.
    """

    class Kind(models.TextChoices):
        RFID = "rfid", "Cartão RFID"
        APP = "app", "Conta no app"

    class Status(models.TextChoices):
        ACTIVE = "active", "Ativa"
        SUSPENDED = "suspended", "Suspensa"
        REVOKED = "revoked", "Revogada"

    user = models.ForeignKey(
        AppUser, on_delete=models.PROTECT, related_name="credentials"
    )
    kind = models.TextField("tipo", choices=Kind.choices)
    auth_tag = models.TextField(
        "identificador",
        unique=True,
        help_text="UID do cartao ou id da conta -- e o `auth_id` que o "
        "carregador reporta.",
    )
    status = models.TextField("situação", choices=Status.choices, default=Status.ACTIVE)
    valid_from = models.DateField("válida desde")

    class Meta:
        db_table = "credential"
        verbose_name = "credencial"
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["rfid", "app"]), name="credential_kind_valid"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["active", "suspended", "revoked"]),
                name="credential_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.auth_tag} ({self.user.name})"


class Vehicle(models.Model):
    """Cadastro do veiculo. Nenhuma FK de faturamento passa por aqui
    (decisao 3); existe para UX e como contexto de IA -- sessao maior que a
    bateria e fisicamente impossivel, logo e anomalia de medicao."""

    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="vehicles")
    plate = models.TextField("placa", unique=True)
    model = models.TextField("modelo")
    battery_capacity_kwh = models.DecimalField(
        "capacidade da bateria (kWh)", max_digits=6, decimal_places=2
    )

    class Meta:
        db_table = "vehicle"
        verbose_name = "veículo"

    def __str__(self):
        return f"{self.model} ({self.plate})"


class ChargePoint(models.Model):
    condominium = models.ForeignKey(
        Condominium, on_delete=models.PROTECT, related_name="charge_points"
    )
    serial_number = models.TextField(
        "número de série",
        unique=True,
        help_text="E o `charge_point_id` do contrato da Frente 2 (o `sn` do SEMS).",
    )
    model = models.TextField("modelo")
    location = models.TextField("localização")
    rated_power_kw = models.DecimalField(
        "potência nominal (kW)",
        max_digits=6,
        decimal_places=2,
        help_text="Denominador da razao kWh/hora usada na deteccao de anomalias.",
    )
    commissioned_at = models.DateField("em operação desde")

    class Meta:
        db_table = "charge_point"
        verbose_name = "ponto de recarga"
        verbose_name_plural = "pontos de recarga"

    def __str__(self):
        return f"{self.model} {self.serial_number}"


class ChargingSession(models.Model):
    """A sessao de recarga -- entidade central.

    Espelha o contrato de dados da Frente 2 e o ciclo OCPP da Frente 1.

    Regra de competencia (Opcao A, caso "virada de mes"): a sessao pertence ao
    mes civil de `session_start`. Mes civil so existe em fuso local, por isso o
    calculo nunca usa o timestamp UTC cru -- ver `billing.competence`.
    """

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "Em andamento"
        COMPLETED = "completed", "Concluída"
        INTERRUPTED = "interrupted", "Interrompida"
        FAULT = "fault", "Falha"

    class AuthMethod(models.TextChoices):
        RFID = "rfid", "RFID"
        APP = "app", "App"

    charge_point = models.ForeignKey(
        ChargePoint, on_delete=models.PROTECT, related_name="sessions"
    )
    credential = models.ForeignKey(
        Credential,
        on_delete=models.PROTECT,
        related_name="sessions",
        null=True,
        blank=True,
        help_text="Credencial resolvida no cadastro. Nula = sessao orfa "
        "(auth_id desconhecido) -- fica fora do rateio ate ser resolvida.",
    )
    auth_id = models.TextField(
        "identificador bruto",
        help_text="O que o carregador reportou, sem tratamento. Redundancia "
        "deliberada (decisao 2): se o cadastro for corrigido depois, a trilha "
        "de auditoria preserva o que o equipamento de fato disse.",
    )
    auth_method = models.TextField("método", choices=AuthMethod.choices)
    session_start = models.DateTimeField("início")
    session_end = models.DateTimeField("fim", null=True, blank=True)
    meter_start = models.DecimalField(
        "medidor no início (kWh)", max_digits=12, decimal_places=3
    )
    meter_stop = models.DecimalField(
        "medidor no fim (kWh)",
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Nulo = leitura final perdida (caso degenerado da Opcao A): "
        "vale a ultima leitura periodica e a sessao vai para auditoria.",
    )
    energy_kwh = models.DecimalField(
        "energia (kWh)",
        max_digits=9,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        help_text="E o `kwh_s` da formula de rateio.",
    )
    max_power_kw = models.DecimalField(
        "potência máxima (kW)", max_digits=6, decimal_places=2, null=True, blank=True
    )
    status = models.TextField("situação", choices=Status.choices)
    stop_reason = models.TextField(
        "motivo do encerramento",
        null=True,
        blank=True,
        help_text="Vocabulario OCPP: Local, EVDisconnected, PowerLoss, "
        "EmergencyStop...",
    )
    measurement_source = models.TextField(
        "origem da medição",
        choices=MeasurementSource.choices,
        default=MeasurementSource.CLOUD,
    )
    applied_tariff = models.ForeignKey(
        "TariffPeriod",
        on_delete=models.PROTECT,
        related_name="sessions",
        null=True,
        blank=True,
        help_text="Vigencia aplicada; nula enquanto em andamento.",
    )
    applied_tariff_kwh = models.DecimalField(
        "tarifa aplicada (R$/kWh)",
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Snapshot do valor provisorio no encerramento -- e a "
        "`tarifa_s` da formula (decisoes 4 e 5). Imune ate a correcao "
        "retroativa da propria vigencia.",
    )

    class Meta:
        db_table = "charging_session"
        verbose_name = "sessão de recarga"
        verbose_name_plural = "sessões de recarga"
        indexes = [
            models.Index(fields=["charge_point", "session_start"]),
            models.Index(fields=["credential", "session_start"]),
            models.Index(fields=["session_start"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=["in_progress", "completed", "interrupted", "fault"]
                ),
                name="session_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(session_end__isnull=True)
                | Q(session_end__gte=F("session_start")),
                name="session_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(energy_kwh__gte=0), name="session_energy_non_negative"
            ),
            # Sessao encerrada tem de ter tarifa congelada: sem isso o rateio
            # de um mes fechado poderia mudar quando a vigencia mudasse.
            models.CheckConstraint(
                condition=Q(status="in_progress")
                | Q(applied_tariff_kwh__isnull=False),
                name="session_closed_has_tariff_snapshot",
            ),
        ]

    def __str__(self):
        return f"Sessao {self.pk} ({self.energy_kwh} kWh)"

    @property
    def duration_hours(self):
        if not self.session_end:
            return None
        return (self.session_end - self.session_start).total_seconds() / 3600


class TelemetryReading(models.Model):
    """Serie temporal de telemetria (decisao 7).

    Tabela propria, fora da sessao, por duas razoes: a previsao consome
    `power_kw` como serie, e a saude do ponto precisa de sinal *mesmo sem
    sessao ativa* -- leitura fora de sessao e justamente o que denuncia
    carregador offline ou cabo conectado sem corrente (o caso Copel).
    """

    class Kind(models.TextChoices):
        METER_VALUE = "meter_value", "Leitura de medidor"
        HEARTBEAT = "heartbeat", "Heartbeat"
        STATUS_CHANGE = "status_change", "Mudança de estado"

    class State(models.TextChoices):
        DISCONNECTED = "disconnected", "Desconectado"
        CONNECTED = "connected", "Conectado"
        CHARGING = "charging", "Carregando"
        FINISHED = "finished", "Finalizado"
        OFFLINE = "offline", "Offline"

    charge_point = models.ForeignKey(
        ChargePoint, on_delete=models.CASCADE, related_name="readings"
    )
    session = models.ForeignKey(
        ChargingSession,
        on_delete=models.CASCADE,
        related_name="readings",
        null=True,
        blank=True,
    )
    ts = models.DateTimeField("instante")
    kind = models.TextField("tipo", choices=Kind.choices)
    state = models.TextField("estado", choices=State.choices, null=True, blank=True)
    power_kw = models.DecimalField(
        "potência (kW)", max_digits=6, decimal_places=2, null=True, blank=True
    )
    energy_kwh_total = models.DecimalField(
        "medidor acumulado (kWh)", max_digits=12, decimal_places=3, null=True, blank=True
    )
    measurement_source = models.TextField(
        "origem da medição",
        choices=MeasurementSource.choices,
        default=MeasurementSource.CLOUD,
    )

    class Meta:
        db_table = "telemetry_reading"
        verbose_name = "leitura de telemetria"
        verbose_name_plural = "leituras de telemetria"
        indexes = [
            models.Index(fields=["charge_point", "ts"]),
            models.Index(fields=["session", "ts"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["meter_value", "heartbeat", "status_change"]),
                name="telemetry_kind_valid",
            )
        ]

    def __str__(self):
        return f"{self.get_kind_display()} @ {self.ts.isoformat()}"


class TariffPeriod(models.Model):
    """Parametros economicos versionados por vigencia (decisao 4).

    Guardar um valor unico "atual" faria um reajuste reescrever o passado.
    """

    condominium = models.ForeignKey(
        Condominium, on_delete=models.CASCADE, related_name="tariff_periods"
    )
    price_kwh = models.DecimalField(
        "tarifa provisória (R$/kWh)",
        max_digits=8,
        decimal_places=4,
        help_text="Provisoria de repasse (decisao 5). O efetivo entra depois, "
        "por linha de ajuste.",
    )
    availability_fee_month = models.DecimalField(
        "taxa de disponibilidade mensal (R$)",
        max_digits=10,
        decimal_places=2,
        help_text="E o `C_disp` da formula -- valor TOTAL, rateado entre as "
        "unidades aderentes.",
    )
    basis = models.TextField(
        "origem do valor",
        help_text='Ex.: "homologada ANEEL Enel SP B3 -- bootstrap" ou '
        '"efetiva da fatura abr/2026".',
    )
    assembly_ref = models.TextField("ata de assembleia", null=True, blank=True)
    valid_from = models.DateField("vigente desde")
    valid_to = models.DateField("vigente até", null=True, blank=True)

    class Meta:
        db_table = "tariff_period"
        verbose_name = "vigência de tarifa"
        verbose_name_plural = "vigências de tarifa"
        constraints = [
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gte=F("valid_from")),
                name="tariff_period_valid_range",
            )
        ]

    def __str__(self):
        fim = self.valid_to.isoformat() if self.valid_to else "vigente"
        return f"R$ {self.price_kwh}/kWh ({self.valid_from.isoformat()} -> {fim})"


class TariffReconciliation(models.Model):
    """Apuracao do custo efetivo e fechamento da reconciliacao (decisao 5).

    Resolve a tensao entre duas promessas do dossie: snapshot por sessao
    (previsibilidade) e repasse do custo efetivo (exatidao). As duas, em dois
    tempos -- a fatura fecha com a provisoria e o mes seguinte carrega UMA
    linha de ajuste por unidade.
    """

    condominium = models.ForeignKey(
        Condominium, on_delete=models.CASCADE, related_name="reconciliations"
    )
    competence = models.CharField("competência apurada", max_length=7)
    utility_invoice_total = models.DecimalField(
        "total da fatura da distribuidora (R$)", max_digits=12, decimal_places=2
    )
    utility_invoice_kwh = models.DecimalField(
        "kWh faturados", max_digits=12, decimal_places=3
    )
    effective_price_kwh = models.DecimalField(
        "tarifa efetiva (R$/kWh)", max_digits=8, decimal_places=4
    )
    provisional_price_kwh = models.DecimalField(
        "tarifa provisória vigente (R$/kWh)", max_digits=8, decimal_places=4
    )
    delta_price_kwh = models.DecimalField(
        "delta (R$/kWh)",
        max_digits=8,
        decimal_places=4,
        help_text="Efetiva menos provisoria. Pode ser negativa.",
    )
    settled_in_competence = models.CharField(
        "liquidada na competência", max_length=7,
        help_text="Competencia cuja fatura carrega as linhas de ajuste.",
    )
    created_at = models.DateTimeField("registrada em", auto_now_add=True)

    class Meta:
        db_table = "tariff_reconciliation"
        verbose_name = "reconciliação de tarifa"
        verbose_name_plural = "reconciliações de tarifa"
        constraints = [
            models.UniqueConstraint(
                fields=["condominium", "competence"],
                name="reconciliation_unique_per_competence",
            )
        ]

    def __str__(self):
        return f"Reconciliacao {self.competence} (delta {self.delta_price_kwh})"


class Invoice(models.Model):
    """A fatura mensal. Por unidade, nao por usuario nem por veiculo
    (decisao 3) -- o casal com dois carros recebe uma fatura so."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        UNDER_REVIEW = "under_review", "Em auditoria"
        CLOSED = "closed", "Fechada"
        PAID = "paid", "Paga"
        OVERDUE = "overdue", "Em atraso"

    condominium = models.ForeignKey(
        Condominium, on_delete=models.PROTECT, related_name="invoices"
    )
    unit = models.ForeignKey(
        Unit, on_delete=models.PROTECT, related_name="invoices", null=True, blank=True
    )
    visitor_user = models.ForeignKey(
        AppUser,
        on_delete=models.PROTECT,
        related_name="visitor_invoices",
        null=True,
        blank=True,
        help_text="Fatura avulsa de visitante, fora do rateio.",
    )
    competence = models.CharField("competência", max_length=7)
    status = models.TextField("situação", choices=Status.choices, default=Status.DRAFT)
    total_amount = models.DecimalField(
        "total (R$)",
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Soma das linhas, persistida no fechamento para auditoria.",
    )
    issued_at = models.DateTimeField("emitida em", null=True, blank=True)
    due_date = models.DateField("vencimento", null=True, blank=True)

    class Meta:
        db_table = "invoice"
        verbose_name = "fatura"
        constraints = [
            models.UniqueConstraint(
                fields=["unit", "competence"],
                condition=Q(unit__isnull=False),
                name="invoice_unique_per_unit_competence",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["draft", "under_review", "closed", "paid", "overdue"]),
                name="invoice_status_valid",
            ),
            # Exatamente uma das duas FKs: fatura e de unidade OU de visitante.
            models.CheckConstraint(
                condition=(
                    Q(unit__isnull=False, visitor_user__isnull=True)
                    | Q(unit__isnull=True, visitor_user__isnull=False)
                ),
                name="invoice_unit_xor_visitor",
            ),
        ]

    def __str__(self):
        alvo = self.unit or self.visitor_user
        return f"Fatura {self.competence} - {alvo}"


class InvoiceLine(models.Model):
    """A linha da fatura -- e a unidade do arredondamento (`round2` por linha
    da Opcao A), nao o total. Arredondar so no fim mudaria centavos."""

    class Kind(models.TextChoices):
        SESSION = "session", "Sessão de recarga"
        AVAILABILITY_FEE = "availability_fee", "Taxa de disponibilidade"
        TARIFF_ADJUSTMENT = "tariff_adjustment", "Ajuste de tarifa"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    kind = models.TextField("tipo", choices=Kind.choices)
    session = models.ForeignKey(
        ChargingSession,
        on_delete=models.PROTECT,
        related_name="invoice_lines",
        null=True,
        blank=True,
    )
    reconciliation = models.ForeignKey(
        TariffReconciliation,
        on_delete=models.PROTECT,
        related_name="invoice_lines",
        null=True,
        blank=True,
    )
    description = models.TextField("descrição")
    energy_kwh = models.DecimalField(
        "energia (kWh)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    unit_price_kwh = models.DecimalField(
        "tarifa (R$/kWh)", max_digits=8, decimal_places=4, null=True, blank=True
    )
    amount = models.DecimalField("valor (R$)", max_digits=10, decimal_places=2)
    flagged_for_audit = models.BooleanField("marcada para auditoria", default=False)

    class Meta:
        db_table = "invoice_line"
        verbose_name = "linha de fatura"
        verbose_name_plural = "linhas de fatura"
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["session", "availability_fee", "tariff_adjustment"]),
                name="invoice_line_kind_valid",
            ),
            models.CheckConstraint(
                condition=~Q(kind="session") | Q(session__isnull=False),
                name="invoice_line_session_requires_fk",
            ),
            models.CheckConstraint(
                condition=~Q(kind="tariff_adjustment") | Q(reconciliation__isnull=False),
                name="invoice_line_adjustment_requires_fk",
            ),
        ]

    def __str__(self):
        return f"{self.description}: R$ {self.amount}"


class AnomalyFlag(models.Model):
    """Saida da deteccao de anomalias, com explicacao legivel.

    Nenhuma flag dispara punicao automatica: a IA produz evidencia, o humano
    decide (`status` + `reviewed_by_user`).
    """

    class Category(models.TextChoices):
        CONSUMPTION = "consumption", "Consumo"
        IDLE = "idle", "Ociosidade"
        POWER_DEGRADATION = "power_degradation", "Degradação de potência"
        METERING = "metering", "Medição"
        HEALTH = "health", "Saúde do ponto"

    class Status(models.TextChoices):
        OPEN = "open", "Aberta"
        ACCEPTED = "accepted", "Aceita"
        CONTESTED = "contested", "Contestada"
        DISMISSED = "dismissed", "Descartada"

    session = models.ForeignKey(
        ChargingSession,
        on_delete=models.CASCADE,
        related_name="anomalies",
        null=True,
        blank=True,
    )
    charge_point = models.ForeignKey(
        ChargePoint,
        on_delete=models.CASCADE,
        related_name="anomalies",
        null=True,
        blank=True,
    )
    category = models.TextField("categoria", choices=Category.choices)
    explanation = models.TextField(
        "explicação",
        help_text='Legivel por humano: "consumo 4x o padrao da credencial".',
    )
    detector = models.TextField(
        "detector",
        default="rule",
        help_text="`rule` (fase 1, estatistica interpretavel) ou "
        "`isolation_forest` (fase 2).",
    )
    score = models.FloatField("escore", null=True, blank=True)
    status = models.TextField("situação", choices=Status.choices, default=Status.OPEN)
    reviewed_by_user = models.ForeignKey(
        AppUser,
        on_delete=models.SET_NULL,
        related_name="reviewed_anomalies",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField("detectada em", auto_now_add=True)
    reviewed_at = models.DateTimeField("revisada em", null=True, blank=True)

    class Meta:
        db_table = "anomaly_flag"
        verbose_name = "anomalia"
        verbose_name_plural = "anomalias"
        constraints = [
            models.CheckConstraint(
                condition=Q(session__isnull=False) | Q(charge_point__isnull=False),
                name="anomaly_targets_session_or_point",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["open", "accepted", "contested", "dismissed"]),
                name="anomaly_status_valid",
            ),
        ]

    def __str__(self):
        return f"[{self.get_category_display()}] {self.explanation[:60]}"
