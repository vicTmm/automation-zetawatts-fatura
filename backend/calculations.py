"""Regras da SPEC, com Decimal e sem arredondamento intermediário."""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

RULE_VERSION = "spec-1"
INPUT_LABELS = {
    "consumption": "Consumo (kWh)",
    "te_supply": "TE fornecimento (R$/kWh)",
    "tusd_supply": "TUSD fornecimento (R$/kWh)",
    "te_injected": "TE injeção (R$/kWh)",
    "tusd_injected": "TUSD injeção (R$/kWh)",
    "flag": "Bandeira (R$/kWh)",
    "balance_credits": "Créditos de saldo utilizados (kWh)",
    "current_credits": "Créditos do mês utilizados (kWh)",
    "enel_bill": "Fatura Enel (R$)",
    "discount_percent": "Desconto (%)",
}


class CalculationError(ValueError):
    pass


def decimal_input(value, label, allow_negative=False):
    """Aceita 1234.56 ou 1.234,56; rejeita vazios, expoentes e não finitos."""
    text = str(value).strip() if value is not None else ""
    negative = text.startswith("-") and allow_negative
    if negative:
        text = text[1:]
    if "," in text:
        if not re.fullmatch(r"(?:\d+|\d{1,3}(?:\.\d{3})+),\d{1,8}", text):
            raise CalculationError(f"{label}: informe um número como 1234,56.")
        text = text.replace(".", "").replace(",", ".")
    elif not re.fullmatch(r"\d+(?:\.\d{1,8})?", text):
        raise CalculationError(f"{label}: informe um número positivo ou zero, com até 8 casas decimais.")
    try:
        number = Decimal(text)
    except InvalidOperation as error:
        raise CalculationError(f"{label}: número inválido.") from error
    if not number.is_finite() or number > Decimal("1000000000"):
        raise CalculationError(f"{label}: valor acima do limite de 1 bilhão.")
    return -number if negative else number


def fixed(value, places):
    return format(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP), "f")


def calculate(values, rule="spec"):
    if rule != "spec":
        from backend.rules import calculate_profile
        return calculate_profile(values, rule)
    missing = set(INPUT_LABELS) - set(values)
    unknown = set(values) - set(INPUT_LABELS)
    if missing:
        raise CalculationError("Preencha: " + ", ".join(INPUT_LABELS[key] for key in INPUT_LABELS if key in missing))
    if unknown:
        raise CalculationError("Campos desconhecidos: " + ", ".join(sorted(unknown)))
    inputs = {key: decimal_input(values[key], label) for key, label in INPUT_LABELS.items()}
    if inputs["discount_percent"] > 100:
        raise CalculationError("Desconto (%): informe um valor entre 0 e 100.")
    with localcontext() as ctx:
        ctx.prec = 50
        d = inputs
        discount = d["discount_percent"] / 100
        supply = d["te_supply"] + d["tusd_supply"] + d["flag"]
        injected = d["te_injected"] + d["tusd_injected"]
        credits = d["balance_credits"] + d["current_credits"]
        zeta = (1 - discount) * credits * injected
        discount_current = discount * injected * d["current_credits"]
        discount_flag = credits * d["flag"]
        raw_discount_total = format(discount_current + discount_flag, "f")
        results = {
            "supply_rate": fixed(supply, 8),
            "injected_rate": fixed(injected, 8),
            "used_credits": fixed(credits, 8),
            "total": fixed(d["consumption"] * supply, 2),
            "zeta_bill": fixed(zeta, 2),
            "discount_current": fixed(discount_current, 2),
            "discount_flag": fixed(discount_flag, 2),
            "discount_total": fixed(discount_current + discount_flag, 2),
            "electricity_rate": fixed(zeta / credits, 8) if credits else None,
            "enel_bill": fixed(d["enel_bill"], 2),
        }
        from backend.rules import line
        lines = [
            line("Energia injetada ZetaGD", credits, injected, credits * injected),
            line("Adicional bandeira", credits, d["flag"], discount_flag),
            line("Desconto ZetaGD", d["discount_percent"], None, -discount_current, "%", True),
        ]
        if d["balance_credits"]:
            lines.append(line("Desconto créditos de saldo", d["discount_percent"], None, -discount * injected * d["balance_credits"], "%", True))
        lines.append(line("Desconto bandeira", Decimal(100), None, -discount_flag, "%", True))
    warnings = []
    if credits == 0:
        warnings.append("Sem créditos utilizados: o valor da eletricidade por kWh não se aplica.")
    if credits > d["consumption"]:
        warnings.append("Os créditos utilizados superam o consumo informado. Confira os dados da Enel.")
    return {
        "inputs": {key: format(value, "f") for key, value in inputs.items()},
        "results": results,
        "warnings": warnings,
        "rule_version": RULE_VERSION,
        "raw_discount_total": raw_discount_total,
        "line_items": lines,
    }
