"""Perfis de cálculo derivados das últimas linhas de cada aba de faturamento."""
from decimal import Decimal, localcontext

from backend.calculations import CalculationError, INPUT_LABELS, decimal_input, fixed

LABELS = {
    **INPUT_LABELS,
    "te": "TE (R$/kWh)", "tusd": "TUSD (R$/kWh)",
    "enel_consumption": "Eletricidade Enel (kWh)",
    "panel_consumption": "Eletricidade painel (kWh)",
    "grid_credits": "Crédito utilizado da Enel (kWh)",
    "tusd_gd1": "TUSD injeção GD1 (R$/kWh)",
    "tusd_gd2": "TUSD injeção GD2 (R$/kWh)",
    "credits_gd1": "Créditos GD1 (kWh)", "credits_gd2": "Créditos GD2 (kWh)",
    "public_fees": "Iluminação pública e multas (R$)",
}

SPEC_FIELDS = list(INPUT_LABELS)
LEGACY_FIELDS = ["consumption", "te", "tusd", "flag", "balance_credits", "current_credits", "enel_bill", "discount_percent"]
PANEL_FIELDS = ["enel_consumption", "panel_consumption", "te", "tusd", "flag", "grid_credits", "enel_bill", "discount_percent"]
GD_FIELDS = ["consumption", "te_supply", "tusd_supply", "tusd_gd1", "tusd_gd2", "flag", "credits_gd1", "credits_gd2", "enel_bill", "public_fees", "discount_percent"]
PROFILES = {
    "spec": {"name": "Icaraí / SPEC", "fields": SPEC_FIELDS, "note": "Desconto ZetaGD sobre créditos do mês. A fatura considera desconto em todos os créditos utilizados."},
    "legacy_total": {"name": "Itaipu / Laura Jardim", "fields": LEGACY_FIELDS, "note": "Fatura Zeta = total de fornecimento − fatura Enel − desconto percentual − desconto bandeira."},
    "essential": {"name": "Essencial", "fields": LEGACY_FIELDS, "note": "Desconto total limitado à diferença entre total de fornecimento e fatura Enel; fatura Zeta com mínimo zero, conforme planilha."},
    "panel_235": {"name": "Faturamento 235", "fields": PANEL_FIELDS, "note": "A aba 235 adiciona a bandeira à tarifa e novamente ao total. Essa fórmula foi preservada. Consumo = Enel + painel."},
    "panel_281": {"name": "Faturamento 281", "fields": PANEL_FIELDS, "note": "Consumo = Enel + painel. Créditos para desconto bandeira = painel + crédito utilizado da Enel."},
    "gd": {"name": "GD1/GD2 · Pio Borges / ZeroHum", "fields": GD_FIELDS, "note": "Tarifas GD1 e GD2 = TE de fornecimento + TUSD da modalidade, conforme as fórmulas da planilha."},
    "gd_geraldo": {"name": "GD1/GD2 · Geraldo Martins", "fields": GD_FIELDS, "note": "Desconto total = total de fornecimento + iluminação e multas − fatura Zeta − fatura Enel."},
}
SHEET_RULES = {"235": "panel_235", "281": "panel_281", "Itaipu": "legacy_total", "Icaraí": "spec", "Laura Jardim": "legacy_total", "Essencial": "essential", "Geraldo Martins": "gd_geraldo", "Pio Borges": "gd", "ZeroHum Maricá": "gd"}


def line(label, quantity, rate, amount, unit="kWh", discount=False):
    return {"label": label, "quantity": format(quantity, "f") if quantity is not None else None, "rate": format(rate, "f") if rate is not None else None, "amount": fixed(amount, 2), "unit": unit, "discount": discount}


def calculate_profile(values, rule):
    if rule not in PROFILES:
        raise CalculationError("Perfil de faturamento desconhecido.")
    fields = PROFILES[rule]["fields"]
    missing = set(fields) - set(values)
    if missing:
        raise CalculationError("Preencha: " + ", ".join(LABELS[key] for key in fields if key in missing))
    if set(values) - set(fields):
        raise CalculationError("Há campos incompatíveis com o perfil deste cliente.")
    d = {key: decimal_input(values[key], LABELS[key], allow_negative=key in ("panel_consumption", "public_fees")) for key in fields}
    if d["discount_percent"] > 100:
        raise CalculationError("Desconto (%): informe um valor entre 0 e 100.")
    with localcontext() as context:
        context.prec = 50
        pct = d["discount_percent"] / 100
        is_gd = rule in ("gd", "gd_geraldo")
        panel = rule in ("panel_235", "panel_281")
        supply = (d["te_supply"] + d["tusd_supply"] if is_gd else d["te"] + d["tusd"]) + d["flag"]
        if panel:
            consumption = d["enel_consumption"] + d["panel_consumption"]
            credits = d["grid_credits"] + d["panel_consumption"]
        else:
            consumption = d["consumption"]
            credits = d["credits_gd1"] + d["credits_gd2"] if is_gd else d["balance_credits"] + d["current_credits"]
        total_rate = supply + d["flag"] if rule == "panel_235" else supply
        total = total_rate * consumption
        if rule == "panel_235":
            total = max(total, Decimal(0))
        flag_discount = credits * d["flag"]
        extras = {}
        if is_gd:
            gd1 = d["te_supply"] + d["tusd_gd1"]
            gd2 = d["te_supply"] + d["tusd_gd2"]
            gross1 = gd1 * d["credits_gd1"]
            gross2 = gd2 * d["credits_gd2"]
            injected = (gross1 + gross2) / credits if credits else None
            zeta = (1 - pct) * (gross1 + gross2)
            discount_current = pct * (gross1 + gross2)
            discount_total = total + d["public_fees"] - zeta - d["enel_bill"] if rule == "gd_geraldo" else discount_current + flag_discount
            extras = {"gd1_rate": fixed(gd1, 8), "gd2_rate": fixed(gd2, 8), "gd1_discount": fixed(gross1 * pct, 2), "gd2_discount": fixed(gross2 * pct, 2)}
            lines = [line("Energia injetada GD1", d["credits_gd1"], gd1, gross1), line("Energia injetada GD2", d["credits_gd2"], gd2, gross2), line("Adicional bandeira", credits, d["flag"], flag_discount), line("Desconto GD1", d["discount_percent"], None, -gross1 * pct, "%", True), line("Desconto GD2", d["discount_percent"], None, -gross2 * pct, "%", True), line("Desconto bandeira", Decimal(100), None, -flag_discount, "%", True)]
        else:
            injected = None
            discount_current = pct * total
            discount_total = min(discount_current + flag_discount, total - d["enel_bill"]) if rule == "essential" else discount_current + flag_discount
            zeta = total - d["enel_bill"] - discount_total
            if rule in ("essential", "panel_235", "panel_281"):
                zeta = max(zeta, Decimal(0))
            lines = [line("Fornecimento de energia", consumption, total_rate, total), line("Fatura Enel (dedução)", None, None, -d["enel_bill"], "")]
            if rule == "essential":
                lines.append(line("Desconto aplicado", None, None, -discount_total, "", True))
            else:
                lines.extend([line("Desconto percentual", d["discount_percent"], None, -discount_current, "%", True), line("Desconto bandeira", None, None, -flag_discount, "", True)])
            adjustment = zeta - (total - d["enel_bill"] - discount_total)
            if adjustment:
                lines.append(line("Limite mínimo da fatura", None, None, adjustment, ""))
        denominator = consumption if rule == "panel_235" else credits
        results = {"supply_rate": fixed(supply, 8), "injected_rate": fixed(injected, 8) if injected is not None else None, "used_credits": fixed(credits, 8), "consumption": fixed(consumption, 8), "total": fixed(total, 2), "zeta_bill": fixed(zeta, 2), "discount_current": fixed(discount_current, 2), "discount_flag": fixed(flag_discount, 2), "discount_total": fixed(discount_total, 2), "electricity_rate": fixed(zeta / denominator, 8) if denominator else None, "enel_bill": fixed(d["enel_bill"], 2), **extras}
    warnings = []
    if denominator == 0:
        warnings.append("Base de consumo/créditos zerada: valor da eletricidade não aplicável.")
    if credits > consumption:
        warnings.append("Os créditos utilizados superam o consumo. Confira os dados da Enel.")
    if discount_total < 0:
        warnings.append("A regra da planilha resultou em desconto total negativo. Confira os valores antes de emitir.")
    if panel and d["panel_consumption"] < 0:
        warnings.append("Eletricidade painel negativa: valor preservado como ajuste, conforme a aba de origem.")
    return {"inputs": {key: format(value, "f") for key, value in d.items()}, "results": results, "raw_discount_total": format(discount_total, "f"), "line_items": lines, "warnings": warnings, "rule_version": rule + "-1"}
