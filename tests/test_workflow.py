import base64
import json
import tempfile
import unittest
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader
from PIL import Image

from app import create_app
from backend.calculations import calculate
from backend.history import history_summary, month_window
from backend.importer import import_workbook
from backend.storage import ConflictError, ROOT, Store
from tests.test_calculations import EXAMPLE

CASES = json.loads((Path(__file__).parent / "reference_cases.json").read_text(encoding="utf-8"))


class ProfileTests(unittest.TestCase):
    def test_last_month_of_all_nine_source_sheets(self):
        self.assertEqual(len(CASES), 9)
        for case in CASES:
            with self.subTest(sheet=case["sheet"], reference=case["reference"]):
                actual = calculate(case["inputs"], case["rule"])["results"]
                for key, expected in case["expected"].items():
                    self.assertEqual(actual[key], expected)

    def test_mixed_gd1_gd2_and_geraldo_discount(self):
        data = {"consumption": "1000", "te_supply": "0.4", "tusd_supply": "0.8", "tusd_gd1": "0.6", "tusd_gd2": "0.4", "flag": "0.05", "credits_gd1": "500", "credits_gd2": "500", "enel_bill": "400", "public_fees": "80", "discount_percent": "20"}
        common = calculate(data, "gd")["results"]
        self.assertEqual(common["zeta_bill"], "720.00")
        self.assertEqual(common["discount_total"], "230.00")
        self.assertEqual(calculate(data, "gd_geraldo")["results"]["discount_total"], "210.00")

    def test_essential_cap_and_negative_discount_preserved(self):
        case = next(case for case in CASES if case["rule"] == "essential")
        result = calculate({**case["inputs"], "enel_bill": "20000"}, "essential")
        self.assertEqual(result["results"]["zeta_bill"], "0.00")
        self.assertLess(Decimal(result["results"]["discount_total"]), 0)
        self.assertTrue(result["warnings"])

    def test_all_profiles_support_zero_base(self):
        for case in CASES:
            with self.subTest(rule=case["rule"]):
                result = calculate({key: "0" for key in case["inputs"]}, case["rule"])
                self.assertEqual(result["results"]["zeta_bill"], "0.00")
                self.assertIsNone(result["results"]["electricity_rate"])

    def test_235_total_has_zero_floor(self):
        case = next(case for case in CASES if case["rule"] == "panel_235")
        result = calculate({**case["inputs"], "enel_consumption": "0", "panel_consumption": "-70"}, "panel_235")
        self.assertEqual(result["results"]["total"], "0.00")

    def test_window_has_exactly_twelve_calendar_months(self):
        self.assertEqual(month_window("2026-08"), ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"])
        items = [{"client_id": "a", "reference": "2025-08", "inputs": {"consumption": "100"}, "results": {"discount_total": "999"}}, {"client_id": "a", "reference": "2026-08", "inputs": {"consumption": "100"}, "results": {"discount_total": "100"}}, {"client_id": "other", "reference": "2026-08", "results": {"discount_total": "900"}}]
        summary = history_summary(items, "a", "2026-08")
        self.assertEqual(summary["available_months"], 1)
        self.assertEqual(summary["discount_total"], "100.00")
        self.assertIsNone(summary["series"][0]["discount"])


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "tmp").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "tmp")
        assert Path(self.temp.name).resolve().parent == (ROOT / "tmp").resolve()
        self.store = Store(path=Path(self.temp.name) / "test.db", url="")
        self.client = TestClient(create_app(self.store, password="", production=False))
        self.customer = self.client.post("/api/clients", json={"name": "Cliente teste", "legal_name": "Cliente de Testes Ltda", "document": "00.000.000/0001-00", "installation": "12345", "address": "Rua de Testes, 10", "rule": "spec"}).json()
        self.body = {"client_id": self.customer["id"], "reference": "2026-08", "due_date": "2026-09-20", "inputs": EXAMPLE, "version": 0}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_calculate_save_reopen_pdf_and_conflict(self):
        response = self.client.put("/api/invoices", json=self.body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["results"]["zeta_bill"], "504.00")
        conflict = self.client.put("/api/invoices", json=self.body)
        self.assertEqual(conflict.status_code, 409)
        stored = self.client.get(f"/api/invoices/{self.customer['id']}/2026-08").json()["invoice"]
        self.assertEqual(stored["version"], 1)
        response = self.client.get(f"/api/invoices/{self.customer['id']}/2026-08/pdf")
        self.assertEqual(response.status_code, 200)
        pdf = PdfReader(BytesIO(response.content))
        self.assertEqual(len(pdf.pages), 1)
        text = pdf.pages[0].extract_text()
        self.assertIn("504,00", text)
        self.assertIn("Desconto créditos de saldo", text)
        self.assertNotIn("WW Studio", text)
        self.assertIn("Chave pix: 42.808.090/0001-91", text)
        self.assertIn("Nome: ZETAWATTS GD", text)
        with Image.open(ROOT / "assets" / "pix.png") as original_qr:
            self.assertTrue(any(
                item.image.size == original_qr.size
                and item.image.convert("RGB").tobytes() == original_qr.convert("RGB").tobytes()
                for item in pdf.pages[0].images
            ), "O PDF deve incorporar o QR Code Pix original sem alterações.")

    def test_preview_does_not_save(self):
        response = self.client.post("/api/preview", json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.store.list("invoice"), [])
        response = self.client.post("/api/preview.png", json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"\x89PNG"))

    def test_changed_registration_preserves_saved_document_and_rule(self):
        self.client.put("/api/invoices", json=self.body)
        data = {key: self.customer[key] for key in ("name", "legal_name", "document", "installation", "address", "discount_percent", "rule", "version")}
        response = self.client.put(f"/api/clients/{self.customer['id']}", json={**data, "legal_name": "Novo nome", "rule": "gd"})
        self.assertEqual(response.status_code, 200)
        old = self.store.get("invoice", self.customer["id"] + ":2026-08")
        self.assertEqual(old["client"]["legal_name"], "Cliente de Testes Ltda")
        updated = self.client.put("/api/invoices", json={**self.body, "version": 1})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["client"]["rule"], "spec")

    def test_client_and_month_isolation(self):
        self.client.put("/api/invoices", json=self.body)
        other = self.client.post("/api/clients", json={"name": "Outro cliente"}).json()
        result = self.client.get(f"/api/invoices/{other['id']}/2026-08").json()
        self.assertIsNone(result["invoice"])
        self.assertEqual(result["history"]["discount_total"], "0.00")
        result = self.client.get(f"/api/invoices/{self.customer['id']}/2026-09").json()
        self.assertIsNone(result["invoice"])

    def test_validation_and_forged_calculated_results(self):
        for extra in [{"results": {"zeta_bill": "1"}}, {"due_date": "2026-02-30"}, {"reference": "2026-13"}, {"payment_image": "data:image/png;base64,Ym9ndXM="}]:
            with self.subTest(extra=extra):
                self.assertEqual(self.client.put("/api/invoices", json={**self.body, **extra}).status_code, 422)
        self.assertEqual(self.client.put("/api/invoices", json={**self.body, "inputs": {**EXAMPLE, "te_supply": ""}}).status_code, 422)

    def test_basic_auth_csrf_and_cloud_configuration(self):
        protected = TestClient(create_app(self.store, password="test-password", production=False))
        self.assertEqual(protected.get("/api/bootstrap").status_code, 401)
        self.assertEqual(protected.get("/api/bootstrap", auth=("operador", "test-password")).status_code, 200)
        invalid_auth = base64.b64encode("não:senha".encode()).decode()
        self.assertEqual(protected.get("/api/bootstrap", headers={"Authorization": "Basic " + invalid_auth}).status_code, 401)
        attack = self.client.post("/api/clients", json={"name": "Cross site"}, headers={"Origin": "https://other.example"})
        self.assertEqual(attack.status_code, 403)
        with self.assertRaises(RuntimeError):
            create_app(self.store, password="", production=True)
        protected.close()

    def test_source_import_idempotence_history_and_pdf_amount(self):
        source = ROOT / "Controle de créditos ZetaGD.xlsx"
        if not source.exists():
            self.skipTest("Planilha de referência não disponível neste ambiente.")
        content = source.read_bytes()
        result = import_workbook(content, self.store)
        self.assertEqual(len(result["sheets"]), 9)
        self.assertEqual(result["added"], 243)
        self.assertEqual(import_workbook(content, self.store)["added"], 0)
        ic = next(c for c in self.store.list("client") if c["name"] == "Icaraí")
        history = history_summary(self.store.list("invoice"), ic["id"], "2026-08")
        self.assertEqual(history["discount_total"], "7846.65")
        response = self.client.get(f"/api/invoices/{ic['id']}/2026-08/pdf")
        self.assertEqual(response.status_code, 200)
        text = PdfReader(BytesIO(response.content)).pages[0].extract_text()
        for number in ("2.474,13", "413,62", "7.846,65", "2.827,57"):
            self.assertIn(number, text)
        old = self.store.get("invoice", ic["id"] + ":2026-07")
        blocked = self.client.put("/api/invoices", json={**self.body, "client_id": ic["id"], "reference": "2026-07", "version": old["version"]})
        self.assertEqual(blocked.status_code, 409)

    def test_invalid_import_does_not_change_database(self):
        count = len(self.store.list("client"))
        response = self.client.post("/api/import", content=b"not an xlsx", headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(self.store.list("client")), count)


if __name__ == "__main__":
    unittest.main()
