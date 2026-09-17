import base64
import binascii
import hmac
import os
import re
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from backend.calculations import CalculationError, calculate, decimal_input
from backend.history import history_summary
from backend.importer import import_workbook
from backend.pdf import generate_pdf, render_preview
from backend.rules import LABELS, PROFILES
from backend.storage import ConflictError, ROOT, Store

load_dotenv(ROOT / ".env")
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]


class ClientData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    legal_name: Short = ""
    document: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] = ""
    installation: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] = ""
    address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=250)] = ""
    discount_percent: Short = "10"
    rule: Short = "spec"
    version: int = Field(default=0, ge=0)

    @field_validator("discount_percent")
    @classmethod
    def check_discount(cls, value):
        number = decimal_input(value, "Desconto (%)")
        if number > 100:
            raise ValueError("Desconto deve ficar entre 0 e 100.")
        return format(number, "f")

    @field_validator("rule")
    @classmethod
    def check_rule(cls, value):
        if value not in PROFILES:
            raise ValueError("Perfil de faturamento desconhecido.")
        return value


class CalculationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inputs: dict[str, str]
    client_id: Short
    reference: Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


class InvoiceData(CalculationData):
    reference: Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
    due_date: date
    flag_label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=25)] = ""
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=600)] = ""
    payment_image: str | None = Field(default=None, max_length=2_000_000)
    version: int = Field(default=0, ge=0)

    @field_validator("reference")
    @classmethod
    def check_reference(cls, value):
        if not 1900 <= int(value[:4]) <= 2200:
            raise ValueError("Ano de referência deve ficar entre 1900 e 2200.")
        return value

    @field_validator("payment_image")
    @classmethod
    def check_image(cls, value):
        if value is None:
            return None
        if not re.match(r"^data:image/(png|jpeg);base64,", value):
            raise ValueError("O boleto deve ser uma imagem PNG ou JPEG.")
        try:
            raw = base64.b64decode(value.split(",", 1)[1], validate=True)
            with Image.open(BytesIO(raw)) as image:
                if image.format not in ("PNG", "JPEG") or image.width * image.height > 8_000_000:
                    raise ValueError("Imagem acima do limite de 8 megapixels.")
                image.verify()
        except (ValueError, OSError, binascii.Error, Image.DecompressionBombError) as error:
            raise ValueError("Imagem inválida ou muito grande. Use PNG/JPEG com até 1,4 MB e 8 megapixels.") from error
        return value


def create_app(store=None, password=None, production=None):
    store = store or Store()
    password = password if password is not None else os.getenv("APP_PASSWORD", "")
    production = production if production is not None else bool(os.getenv("VERCEL") or os.getenv("APP_ENV") == "production")
    if production and (not password or not store.url):
        raise RuntimeError("Configure APP_PASSWORD e DATABASE_URL antes de publicar.")
    if not store.url:
        store.initialize()
    app = FastAPI(title="Zetawatts Faturas", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store

    @app.middleware("http")
    async def protect(request, call_next):
        if password:
            credentials = request.headers.get("authorization", "")
            valid = False
            if credentials.startswith("Basic "):
                try:
                    user, supplied = base64.b64decode(credentials[6:], validate=True).decode().split(":", 1)
                    valid = hmac.compare_digest(user.encode(), b"operador") and hmac.compare_digest(supplied.encode(), password.encode())
                except (ValueError, UnicodeError, binascii.Error):
                    pass
            if not valid:
                return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Zetawatts", charset="UTF-8"', "Cache-Control": "no-store"})
        elif request.client and request.client.host not in ("127.0.0.1", "::1", "testclient"):
            return JSONResponse({"detail": "Configure APP_PASSWORD para acesso remoto."}, status_code=403)
        if request.method in ("POST", "PUT", "DELETE"):
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Origem da requisição não permitida."}, status_code=403)
            allowed = ("application/json", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/octet-stream")
            if not request.headers.get("content-type", "").split(";")[0] in allowed:
                return JSONResponse({"detail": "Formato de requisição não permitido."}, status_code=415)
            try:
                if int(request.headers.get("content-length", "0")) > 11 * 1024 * 1024:
                    return JSONResponse({"detail": "Arquivo acima de 10 MB."}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Tamanho inválido."}, status_code=400)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; frame-src 'self' blob:; object-src 'self' blob:; connect-src 'self'; base-uri 'none'; frame-ancestors 'self'"
        return response

    @app.exception_handler(CalculationError)
    async def invalid_calculation(request, error):
        return JSONResponse({"detail": str(error)}, status_code=422)

    @app.exception_handler(ConflictError)
    async def conflict(request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.get("/")
    def index():
        return FileResponse(ROOT / "frontend" / "index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")
    app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")

    @app.get("/api/bootstrap")
    def bootstrap():
        clients = store.list("client")
        invoices = store.list("invoice")
        for client in clients:
            rows = [item for item in invoices if item["client_id"] == client["id"]]
            client["latest_reference"] = max([item["reference"] for item in rows], default=None)
            client["invoice_count"] = len(rows)
        return {"clients": sorted(clients, key=lambda item: item["name"].casefold()), "profiles": PROFILES, "labels": LABELS, "invoice_count": len(invoices), "latest_reference": max([item["reference"] for item in invoices], default=date.today().strftime("%Y-%m"))}

    @app.post("/api/clients", status_code=201)
    def create_client(data: ClientData):
        cid = str(uuid4())
        return store.put("client", cid, {**data.model_dump(exclude={"version"}), "id": cid}, 0)

    @app.put("/api/clients/{cid}")
    def update_client(cid: str, data: ClientData):
        previous = store.get("client", cid)
        if not previous:
            raise HTTPException(404, "Cliente não encontrado.")
        return store.put("client", cid, {**previous, **data.model_dump(exclude={"version"})}, data.version)

    @app.post("/api/calculate")
    def calculate_api(data: CalculationData):
        client = store.get("client", data.client_id)
        if not client:
            raise HTTPException(404, "Cliente não encontrado.")
        previous = store.get("invoice", data.client_id + ":" + data.reference)
        rule = previous["client"].get("rule", "spec") if previous else client.get("rule", "spec")
        return calculate(data.inputs, rule)

    @app.get("/api/clients/{cid}/invoices")
    def list_invoices(cid: str):
        rows = [item for item in store.list("invoice") if item["client_id"] == cid]
        return [{key: item.get(key) for key in ("reference", "results", "editable", "source", "due_date", "version")} for item in sorted(rows, key=lambda item: item["reference"], reverse=True)]

    @app.get("/api/invoices/{cid}/{reference}")
    def get_invoice(cid: str, reference: str):
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", reference) or not 1900 <= int(reference[:4]) <= 2200:
            raise HTTPException(422, "Mês inválido.")
        client = store.get("client", cid)
        if not client:
            raise HTTPException(404, "Cliente não encontrado.")
        invoice = store.get("invoice", cid + ":" + reference)
        return {"invoice": invoice, "client": client, "history": history_summary(store.list("invoice"), cid, reference)}

    def build_invoice(data):
        client = store.get("client", data.client_id)
        if not client:
            raise HTTPException(404, "Cliente não encontrado.")
        previous = store.get("invoice", data.client_id + ":" + data.reference)
        if previous and not previous.get("editable", True):
            raise HTTPException(409, "Este mês usa uma regra histórica. Os valores importados são preservados; selecione um novo mês para faturar pela SPEC.")
        client = {**client, "rule": previous["client"].get("rule", "spec") if previous else client.get("rule", "spec")}
        calculated = calculate(data.inputs, client["rule"])
        return {**data.model_dump(mode="json", exclude={"version"}), **calculated, "id": data.client_id + ":" + data.reference, "client": client, "source": "application", "editable": True, "updated_at": datetime.now(timezone.utc).isoformat()}

    @app.put("/api/invoices")
    def save_invoice(data: InvoiceData):
        invoice = build_invoice(data)
        return store.put("invoice", invoice["id"], invoice, data.version)

    @app.post("/api/preview")
    def preview(data: InvoiceData):
        invoice = build_invoice(data)
        history = history_summary(store.list("invoice"), data.client_id, data.reference, invoice)
        return Response(generate_pdf(invoice, history), media_type="application/pdf")

    @app.post("/api/preview.png")
    def preview_image(data: InvoiceData):
        invoice = build_invoice(data)
        history = history_summary(store.list("invoice"), data.client_id, data.reference, invoice)
        return Response(render_preview(generate_pdf(invoice, history)), media_type="image/png")

    @app.get("/api/invoices/{cid}/{reference}/pdf")
    def download(cid: str, reference: str):
        invoice = store.get("invoice", cid + ":" + reference)
        if not invoice:
            raise HTTPException(404, "Salve a fatura antes de baixar.")
        if not invoice.get("editable") or not invoice.get("due_date"):
            raise HTTPException(409, "Este registro histórico não tem os dados necessários para gerar uma nova fatura.")
        client = invoice["client"]
        missing = [label for key, label in (("legal_name", "razão social"), ("document", "CPF/CNPJ"), ("installation", "número do cliente Enel"), ("address", "endereço")) if not client.get(key)]
        if missing:
            raise HTTPException(422, "Complete o cadastro e salve a fatura novamente: " + ", ".join(missing) + ".")
        history = history_summary(store.list("invoice"), cid, reference)
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", client["name"])[:60]
        return Response(generate_pdf(invoice, history), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe_name}-fatura-ZetaGD-{reference}.pdf"'})

    @app.post("/api/import")
    async def import_api(request: Request):
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > 10 * 1024 * 1024:
                raise HTTPException(413, "Planilha acima de 10 MB.")
        try:
            return import_workbook(bytes(content), store)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    return app


app = create_app()
