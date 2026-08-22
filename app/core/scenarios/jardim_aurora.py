"""O mes ficticio de junho/2026 no Residencial Jardim Aurora.

Esta nao e uma fixture inventada para o teste passar: e a transcricao literal
da secao "Um mes ficticio" da Frente 3-C (docs/frente-3-arquitetura.md), cujos
valores foram conferidos na Sprint 1 por script em aritmetica decimal half-up,
**antes** de existir qualquer codigo de producao.

Isso torna o teste de aceitacao do motor um oraculo de verdade: os numeros
esperados nao foram lidos da implementacao, foram escritos meses antes dela.

Cenario: 48 unidades, 12 aderentes, 1 ponto HCA G2 de 7 kW, tarifa provisoria
R$ 0,7252/kWh, C_disp R$ 180,00. Tres unidades carregaram, e cada uma
exercita um dos casos excepcionais exigidos pelo enunciado:

- **72** (Ana e Bruno) -- dois veiculos, duas credenciais, UMA fatura;
- **34** (Carla) -- sessao interrompida com leitura final perdida;
- **105** (Davi) -- sessao que atravessa a virada do mes.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from core.models import (
    AppUser,
    ChargePoint,
    ChargingSession,
    Condominium,
    Credential,
    MeasurementSource,
    ProgramEnrollment,
    TariffPeriod,
    Unit,
    Vehicle,
)

BRT = ZoneInfo("America/Sao_Paulo")

PRICE_KWH = Decimal("0.7252")
AVAILABILITY_FEE = Decimal("180.00")
N_ENROLLED = 12
OTHER_ENROLLED_LABELS = ["12", "21", "45", "58", "63", "87", "91", "102", "110"]

#: (id, inicio, fim, credencial, kWh, status, motivo, leitura_final_perdida)
SESSIONS = [
    (1001, "2026-06-02 22:10", "2026-06-03 06:05", "RFID-ANA", "18.400", "completed", "Local", False),
    (1002, "2026-06-05 21:30", "2026-06-06 01:15", "RFID-CARLA", "22.150", "completed", "Local", False),
    (1003, "2026-06-08 19:05", "2026-06-09 01:00", "APP-DAVI", "40.000", "completed", "EVDisconnected", False),
    (1004, "2026-06-10 23:00", "2026-06-11 03:40", "APP-BRUNO", "25.000", "completed", "Local", False),
    (1005, "2026-06-12 22:45", "2026-06-12 23:41", "RFID-CARLA", "6.020", "interrupted", "PowerLoss", True),
    (1006, "2026-06-15 21:00", "2026-06-15 23:05", "APP-DAVI", "11.250", "completed", "Local", False),
    (1007, "2026-06-18 22:40", "2026-06-19 03:30", "RFID-CARLA", "30.500", "completed", "Local", False),
    (1008, "2026-06-22 20:50", "2026-06-22 22:30", "RFID-ANA", "9.300", "completed", "Local", False),
    (1009, "2026-06-26 21:10", "2026-06-26 23:20", "RFID-CARLA", "12.700", "completed", "Local", False),
    # Comeca 30/06 23:40 BRT: em UTC ja e 01/07. Competencia = JUNHO.
    (1010, "2026-06-30 23:40", "2026-07-01 05:20", "APP-DAVI", "27.800", "completed", "Local", False),
]

METER_ORIGIN = Decimal("1000.000")


def _dt(text: str) -> datetime:
    """Interpreta o horario no fuso do condominio -- e assim que o dossie
    escreveu as sessoes, e e assim que o sindico le a tabela."""
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=BRT)


def build_jardim_aurora(*, extra_residents: bool = False) -> dict:
    """Monta o cenario completo e devolve os objetos que os testes usam.

    `extra_residents=True` cadastra moradores e credenciais nas outras 9
    unidades aderentes. Eles nao tem sessao em junho -- e por isso os testes de
    aceitacao continuam exatos -- mas dao ao gerador sintetico populacao
    suficiente para os meses anteriores, que e o que a IA precisa para ter o que
    aprender. O default e `False` para que o teste do dossie rode sobre
    exatamente o cenario do dossie.
    """
    condo = Condominium.objects.create(
        name="Residencial Jardim Aurora",
        utility_name="Enel SP",
        declared_power_kw=Decimal("22.00"),
        visitor_price_kwh=Decimal("1.2000"),
    )

    # 48 unidades no total (o cenario do dossie), das quais 12 aderentes.
    enrolled_labels = ["34", "72", "105", *OTHER_ENROLLED_LABELS]
    labels = list(enrolled_labels)
    for n in range(1, 400):
        if len(labels) >= 48:
            break
        if str(n) not in labels:
            labels.append(str(n))

    units = {
        label: Unit.objects.create(condominium=condo, label=label)
        for label in sorted(labels, key=lambda x: int(x))
    }
    for label in enrolled_labels:
        ProgramEnrollment.objects.create(
            unit=units[label], start_date=date(2026, 1, 1), end_date=None
        )

    tariff = TariffPeriod.objects.create(
        condominium=condo,
        price_kwh=PRICE_KWH,
        availability_fee_month=AVAILABILITY_FEE,
        basis="homologada ANEEL Enel SP B3 (REH 3.477/2025) - bootstrap, sem tributos",
        assembly_ref="Ata da AGO de 12/03/2026",
        valid_from=date(2026, 1, 1),
        valid_to=None,
    )

    ana = AppUser.objects.create(name="Ana Ribeiro", email="ana@jardimaurora.test", unit=units["72"])
    bruno = AppUser.objects.create(name="Bruno Ribeiro", email="bruno@jardimaurora.test", unit=units["72"])
    carla = AppUser.objects.create(name="Carla Menezes", email="carla@jardimaurora.test", unit=units["34"])
    davi = AppUser.objects.create(name="Davi Lopes", email="davi@jardimaurora.test", unit=units["105"])
    gestor = AppUser.objects.create(
        name="Sonia Duarte", email="sindica@jardimaurora.test",
        unit=None, role=AppUser.Role.MANAGER,
    )

    creds = {
        "RFID-ANA": Credential.objects.create(
            user=ana, kind=Credential.Kind.RFID, auth_tag="RFID-ANA", valid_from=date(2026, 1, 1)
        ),
        "APP-BRUNO": Credential.objects.create(
            user=bruno, kind=Credential.Kind.APP, auth_tag="APP-BRUNO", valid_from=date(2026, 1, 1)
        ),
        "RFID-CARLA": Credential.objects.create(
            user=carla, kind=Credential.Kind.RFID, auth_tag="RFID-CARLA", valid_from=date(2026, 1, 1)
        ),
        "APP-DAVI": Credential.objects.create(
            user=davi, kind=Credential.Kind.APP, auth_tag="APP-DAVI", valid_from=date(2026, 1, 1)
        ),
    }

    Vehicle.objects.create(user=ana, plate="ABC1D23", model="BYD Dolphin", battery_capacity_kwh=Decimal("44.90"))
    Vehicle.objects.create(user=bruno, plate="EFG4H56", model="Volvo EX30", battery_capacity_kwh=Decimal("69.00"))
    Vehicle.objects.create(user=carla, plate="IJK7L89", model="GWM Ora 03", battery_capacity_kwh=Decimal("48.00"))
    Vehicle.objects.create(user=davi, plate="MNO0P12", model="BYD Seal", battery_capacity_kwh=Decimal("82.50"))

    point = ChargePoint.objects.create(
        condominium=condo,
        serial_number="57000HPA247L0002",
        model="GoodWe HCA G2 7 kW",
        location="Garagem G1, vaga de recarga 01",
        rated_power_kw=Decimal("7.00"),
        commissioned_at=date(2026, 1, 15),
    )

    meter = METER_ORIGIN
    sessions = {}
    for sid, start, end, tag, kwh, status, reason, lost_reading in SESSIONS:
        energy = Decimal(kwh)
        meter_start = meter
        meter += energy
        cred = creds[tag]
        sessions[sid] = ChargingSession.objects.create(
            charge_point=point,
            credential=cred,
            auth_id=tag,
            auth_method=(
                ChargingSession.AuthMethod.RFID
                if cred.kind == Credential.Kind.RFID
                else ChargingSession.AuthMethod.APP
            ),
            session_start=_dt(start),
            session_end=_dt(end),
            meter_start=meter_start,
            meter_stop=None if lost_reading else meter,
            energy_kwh=energy,
            max_power_kw=Decimal("7.00"),
            status=status,
            stop_reason=reason,
            measurement_source=MeasurementSource.CLOUD,
            applied_tariff=tariff,
            applied_tariff_kwh=PRICE_KWH,
        )

    if extra_residents:
        _add_extra_residents(condo, units, creds)

    return {
        "condominium": condo,
        "units": units,
        "tariff": tariff,
        "charge_point": point,
        "credentials": creds,
        "sessions": sessions,
        "users": {"ana": ana, "bruno": bruno, "carla": carla, "davi": davi, "gestor": gestor},
        "enrolled_labels": enrolled_labels,
    }


EXTRA_RESIDENTS = [
    ("12", "Elisa Prado", "BYD Dolphin Mini", "38.00", "rfid"),
    ("21", "Fabio Nunes", "Renault Kwid E-Tech", "26.80", "app"),
    ("45", "Gisela Amorim", "Volvo EX40", "69.00", "rfid"),
    ("58", "Heitor Sampaio", "BYD Song Plus", "71.80", "app"),
    ("63", "Ines Barreto", "GWM Ora 03", "48.00", "rfid"),
    ("87", "Joao Vilela", "Chevrolet Bolt", "65.00", "app"),
    ("91", "Kelly Andrade", "Fiat 500e", "42.00", "rfid"),
    ("102", "Lucas Tavares", "BYD Seal", "82.50", "app"),
    ("110", "Marina Coelho", "JAC E-JS1", "30.20", "rfid"),
]


def _add_extra_residents(condo, units, creds):
    """Moradores das demais unidades aderentes.

    Sem sessao em junho de proposito: o mes ficticio do dossie tem tres
    unidades consumidoras, e o teste de aceitacao afere exatamente isso.
    """
    for i, (label, nome, modelo, bateria, tipo) in enumerate(EXTRA_RESIDENTS):
        primeiro = nome.split()[0].lower()
        user = AppUser.objects.create(
            name=nome, email=f"{primeiro}@jardimaurora.test", unit=units[label]
        )
        tag = f"{'RFID' if tipo == 'rfid' else 'APP'}-{primeiro.upper()}"
        creds[tag] = Credential.objects.create(
            user=user,
            kind=Credential.Kind.RFID if tipo == "rfid" else Credential.Kind.APP,
            auth_tag=tag,
            valid_from=date(2026, 1, 1),
        )
        Vehicle.objects.create(
            user=user,
            plate=f"XYZ{i}{chr(65 + i)}{i}{i}",
            model=modelo,
            battery_capacity_kwh=Decimal(bateria),
        )
