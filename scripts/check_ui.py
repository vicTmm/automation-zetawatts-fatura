"""Valida a jornada no navegador com banco temporário, sem alterar dados operacionais."""
import json
import os
import subprocess
import socket
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
virtual_python = ROOT / ".venv" / "Scripts" / "python.exe"
if virtual_python.exists() and Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
    result = subprocess.run([str(virtual_python), str(Path(__file__).resolve())], capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    raise SystemExit(result.returncode)
from playwright.sync_api import sync_playwright, expect
from backend.importer import import_workbook
from backend.storage import Store

OUTPUT = ROOT / "tmp" / "review"
OUTPUT.mkdir(parents=True, exist_ok=True)
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
url = f"http://127.0.0.1:{port}"
python = ROOT / ".venv" / "Scripts" / "python.exe"
if not python.exists():
    python = Path(sys.executable)

with tempfile.TemporaryDirectory(dir=ROOT / "tmp", prefix="ui-") as temporary:
    assert Path(temporary).resolve().parent == (ROOT / "tmp").resolve()
    store = Store(path=Path(temporary) / "test.db", url="")
    store.initialize()
    import_workbook((ROOT / "Controle de créditos ZetaGD.xlsx").read_bytes(), store)
    env = {**os.environ, "SQLITE_PATH": store.path, "DATABASE_URL": "", "APP_PASSWORD": "", "APP_ENV": "development"}
    env.pop("VERCEL", None)
    with open(Path(temporary) / "server.log", "w", encoding="utf-8") as log:
        server = subprocess.Popen([str(python), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            import httpx
            for _ in range(50):
                try:
                    if httpx.get(url + "/api/bootstrap").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.2)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1080}, device_scale_factor=1)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url)
                expect(page.locator("#client-name")).to_have_text("Icaraí")
                expect(page.locator("#pdf-preview")).to_be_visible(timeout=15000)
                page.wait_for_function("document.querySelector('#pdf-preview').naturalWidth > 0")
                expect(page.locator("#metric-zeta")).to_contain_text("2.474,13")
                page.screenshot(path=str(OUTPUT / "app-desktop.png"), full_page=True)
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                # Novo mês, campos vazios, cálculo com vírgula, salvamento e download.
                page.locator("#reference").fill("2026-09")
                page.locator("#reference").dispatch_event("change")
                expect(page.locator("#field-consumption")).to_have_value("")
                page.locator("#due-date").fill("2026-10-20")
                case = next(x for x in json.loads((ROOT / "tests/reference_cases.json").read_text(encoding="utf-8")) if x["rule"] == "spec")
                for key, value in case["inputs"].items():
                    page.locator("#field-" + key).fill(value.replace(".", ","))
                expect(page.locator("#metric-zeta")).to_contain_text("2.474,13")
                expect(page.locator("#save-invoice")).to_be_enabled()
                expect(page.locator("#download-pdf")).to_be_disabled()
                page.locator("#save-invoice").click()
                expect(page.locator("#save-state")).to_have_text("Salvo")
                with page.expect_download() as downloaded:
                    page.locator("#download-pdf").click()
                assert downloaded.value.suggested_filename.endswith("2026-09.pdf")
                # Navegação preserva rascunhos sem misturar clientes.
                page.locator("#field-consumption").fill("5000")
                page.get_by_role("button", name="Pio Borges", exact=False).click()
                expect(page.locator("#client-name")).to_have_text("Pio Borges")
                expect(page.locator("#field-credits_gd1")).to_be_visible()
                expect(page.locator("#field-consumption")).to_have_value("")
                page.get_by_role("button", name="Icaraí", exact=False).click()
                expect(page.locator("#field-consumption")).to_have_value("5000")
                expect(page.locator("#save-state")).to_have_text("Não salvo")
                # Valores inválidos retiram resultado antigo e bloqueiam emissão.
                page.locator("#field-te_supply").fill("abc")
                expect(page.locator("#calculation-error")).to_be_visible()
                expect(page.locator("#save-invoice")).to_be_disabled()
                expect(page.locator("#metric-zeta")).to_have_text("—")
                # Tela menor e histórico consultável.
                page.set_viewport_size({"width": 390, "height": 844})
                page.locator("#reference").fill("2026-08")
                page.locator("#reference").dispatch_event("change")
                expect(page.locator("#pdf-preview")).to_be_visible()
                page.wait_for_function("document.querySelector('#pdf-preview').naturalWidth > 0")
                page.locator("#reference").blur()
                page.evaluate("document.querySelector('#toast').hidden = true")
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                page.screenshot(path=str(OUTPUT / "app-mobile.png"), full_page=True)
                page.locator("#tab-history").click()
                expect(page.locator("#history-rows tr")).to_have_count(43)
                assert not errors, errors
                # Cadastro de um novo cliente sem criar aba nem alterar código.
                page.locator("#new-client").click()
                page.locator("#client-form input[name=name]").fill("Novo cliente QA")
                page.locator("#client-form input[name=legal_name]").fill("Cliente QA Ltda")
                page.locator("#client-form button[type=submit]").click()
                expect(page.locator("#client-name")).to_have_text("Novo cliente QA")
                browser.close()
                print("UI: cálculo, PDF, persistência, navegação, rascunhos, cadastro e responsividade OK.")
        finally:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(server.pid), "/T", "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                server.terminate()
            server.wait(timeout=15)
