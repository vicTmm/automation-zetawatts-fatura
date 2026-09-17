"""Fatura em PDF baseada no layout fornecido, sem depender do PowerPoint."""
import base64
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from backend.calculations import fixed
from backend.history import FULL_MONTHS

BLUE = HexColor("#196280")
INK = HexColor("#17354c")
ORANGE = HexColor("#bf4e0b")
ROOT = Path(__file__).resolve().parents[1]
RENDER_LOCK = Lock()


def render_preview(pdf_bytes):
    # PDFium exige exclusão mútua entre chamadas em threads diferentes.
    import pypdfium2
    with RENDER_LOCK, pypdfium2.PdfDocument(pdf_bytes) as document:
        page = document[0]
        bitmap = page.render(scale=1.6)
        try:
            output = BytesIO()
            bitmap.to_pil().save(output, format="PNG")
            return output.getvalue()
        finally:
            bitmap.close()
            page.close()


def br(value, places=2):
    if value is None:
        return "-"
    text = f"{Decimal(fixed(Decimal(str(value)), places)):,.{places}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def generate_pdf(invoice, history):
    buffer = BytesIO()
    # Dimensões reais do PPTX fornecido: 7,5 x 10,833 polegadas.
    c = canvas.Canvas(buffer, pagesize=(540, 780), pageCompression=1)
    c.setTitle(f"Fatura ZetaGD - {invoice['client']['name']} - {invoice['reference']}")
    c.setAuthor("Zetawatts")
    width, height = 540, 780

    def text(x, top, value, size=8, bold=False, color=INK, align="left"):
        c.setFillColor(color)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        method = c.drawRightString if align == "right" else c.drawCentredString if align == "center" else c.drawString
        method(x, height - top, str(value))

    def paragraph(x, top, value, available_width, size=8, bold=False):
        style = ParagraphStyle("body", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size, leading=size * 1.3, textColor=INK)
        p = Paragraph(escape(str(value)), style)
        _, h = p.wrap(available_width, 200)
        p.drawOn(c, x, height - top - h)
        return h

    def rect(x, top, w, h, color):
        c.setFillColor(color)
        c.rect(x, height - top - h, w, h, fill=1, stroke=0)

    d, r, client = invoice["inputs"], invoice["results"], invoice["client"]
    c.drawImage(str(ROOT / "assets" / "logo.png"), 0, height - 128, width=125, height=100, preserveAspectRatio=True, mask="auto")
    year, month = invoice["reference"].split("-")
    rect(122, 34, 270, 25, BLUE)
    for x, title in [(176, "Mês de referência"), (269, "Vencimento"), (350, "Total a pagar")]:
        text(x, 50, title, 8.5, True, white, "center")
    due = "/".join(reversed(invoice["due_date"].split("-"))) if invoice.get("due_date") else "Não informado"
    for x, value in [(176, FULL_MONTHS[int(month) - 1] + "/" + year), (269, due), (350, "R$ " + br(r["zeta_bill"]))]:
        text(x, 76, value, 9, False, INK, "center")
    c.setStrokeColor(INK)
    c.rect(122, height - 85, 270, 51, fill=0, stroke=1)
    for x in (230, 308):
        c.line(x, height - 34, x, height - 85)
    # QR estático extraído do PDF original: mesma chave, sem valor fixo.
    c.drawImage(str(ROOT / "assets" / "pix.png"), 425, height - 109, width=76, height=76, preserveAspectRatio=True, mask="auto")
    text(404, 121, "Chave pix: 42.808.090/0001-91", 6.5)
    text(404, 132, "Nome: ZETAWATTS GD", 6.5)
    cursor = 95
    cursor += paragraph(122, cursor, client.get("legal_name") or client["name"], 270, 10, True)
    cursor += paragraph(122, cursor + 3, client.get("address") or "Endereço não informado", 270, 8)
    cursor += 6 + paragraph(122, cursor + 6, f"CPF/CNPJ: {client.get('document') or '-'}     Nº do cliente: {client.get('installation') or '-'}", 270, 8)

    table_top = max(177, cursor + 32)
    for x, title in [(39, "Itens da fatura"), (202, "Unid."), (273, "Quantidade"), (331, "Valor unitário"), (396, "Valor (R$)")]:
        text(x, table_top, title, 7, True, align="right" if x >= 273 else "left")
    c.line(34, height - table_top - 8, 400, height - table_top - 8)
    rows = invoice["line_items"]
    top = table_top + 25
    for item in rows:
        label = item["label"]
        if label == "Desconto bandeira" and invoice.get("flag_label"):
            label += " " + invoice["flag_label"]
        discount = item["discount"]
        text(39, top, label, 7, True, ORANGE if discount else INK)
        text(202, top, item["unit"], 7)
        text(273, top, br(item["quantity"], 2) if item["quantity"] is not None else "", 7, color=ORANGE if discount else INK, align="right")
        text(331, top, br(item["rate"], 5) if item["rate"] is not None else "", 7, align="right")
        text(396, top, br(item["amount"]), 7, discount, ORANGE if discount else INK, "right")
        c.setStrokeColor(HexColor("#aec0c9"))
        c.line(34, height - top - 9, 400, height - top - 9)
        top += 25
    for label, value in [("Total a pagar ZetaGD", br(r["zeta_bill"])), ("Desconto total", br(-Decimal(r["discount_total"])) )]:
        rect(34, top - 14, 366, 25, BLUE)
        text(40, top + 2, label, 9, True, white)
        text(396, top + 2, value, 10, True, white, "right")
        top += 25
    if client.get("rule", "spec") == "spec" and Decimal(d["balance_credits"]):
        paragraph(34, top, "Desconto total: desconto sobre créditos do mês + bandeira, conforme contrato. O desconto sobre saldo está discriminado separadamente.", 472, 7)
        top += 22

    series = history["series"]
    text(417, table_top, "Consumo (kWh)", 7, True)
    text(417, table_top + 11, "últimos 12 meses", 7, True)
    max_cons = max([float(item["consumption"] or 0) for item in series] + [1])
    for index, item in enumerate(reversed(series)):
        row_top = table_top + 28 + index * 11
        val = item["consumption"]
        bar_width = max(0, float(val or 0)) / max_cons * 45
        text(437, row_top, item["label"], 5.5, align="right")
        rect(440, row_top - 5, bar_width, 4, BLUE)
        text(510, row_top, br(val, 0), 5.5, align="right")
    chart_top = max(top + 18, table_top + 180)
    text(34, chart_top, "Desconto ZetaGD (R$) nos últimos 12 meses", 8, True)
    max_discount = max([float(item["discount"] or 0) for item in series] + [1])
    for index, item in enumerate(series):
        x = 38 + index * 28
        val = item["discount"]
        bar_height = max(0, float(val or 0)) / max_discount * 55
        rect(x + 5, chart_top + 80 - bar_height, 11, bar_height, BLUE)
        text(x + 10, chart_top + 93, item["label"], 5.5, align="center")
        text(x + 10, chart_top + 76 - bar_height, br(val, 2), 5.5, align="center")
    rect(393, chart_top + 17, 113, 77, ORANGE)
    text(402, chart_top + 34, "Você economizou", 8, color=white)
    text(402, chart_top + 47, "nos últimos 12 meses", 8, color=white)
    text(449, chart_top + 74, "R$ " + br(history["discount_total"]), 14, True, white, "center")
    payment_top = chart_top + 116
    c.setDash(4, 4)
    c.setStrokeColor(HexColor("#aab5bc"))
    c.line(20, height - payment_top, 520, height - payment_top)
    c.setDash()
    if invoice.get("payment_image"):
        picture = ImageReader(BytesIO(base64.b64decode(invoice["payment_image"].split(",", 1)[1])))
        available = max(70, 738 - payment_top)
        c.drawImage(picture, 25, height - payment_top - available - 10, width=490, height=available, preserveAspectRatio=True, anchor="c", mask="auto")
    else:
        text(270, payment_top + 35, "Boleto não anexado", 9, color=HexColor("#788995"), align="center")
    if history["available_months"] < 12:
        text(34, 756, f"Histórico disponível: {history['available_months']} de 12 meses. Meses sem registro aparecem com traço.", 7)
    text(506, 770, "ZetaGD", 7, align="right")
    c.showPage()
    c.save()
    return buffer.getvalue()
