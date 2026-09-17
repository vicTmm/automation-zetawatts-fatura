from decimal import Decimal
from backend.calculations import fixed

MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
FULL_MONTHS = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")


def month_window(reference):
    year, month = map(int, reference.split("-"))
    position = year * 12 + month - 1
    return [f"{index // 12:04d}-{index % 12 + 1:02d}" for index in range(position - 11, position + 1)]


def history_summary(invoices, client_id, reference, current=None):
    keyed = {item["reference"]: item for item in invoices if item["client_id"] == client_id}
    if current:
        keyed[reference] = current
    total = Decimal(0)
    count = 0
    series = []
    for month in month_window(reference):
        item = keyed.get(month)
        consumption = item.get("inputs", {}).get("consumption", item.get("results", {}).get("consumption")) if item else None
        discount = item.get("raw_discount_total", item.get("results", {}).get("discount_total")) if item else None
        if discount is not None:
            total += Decimal(discount)
            count += 1
        series.append({"reference": month, "label": MONTHS[int(month[5:]) - 1] + "/" + month[2:4], "consumption": consumption, "discount": discount})
    return {"series": series, "discount_total": fixed(total, 2), "available_months": count}
