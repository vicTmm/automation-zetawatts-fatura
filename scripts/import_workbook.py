import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from backend.importer import import_workbook
from backend.storage import ROOT, Store

load_dotenv(ROOT / ".env")
parser = argparse.ArgumentParser(description="Importa abas Faturamento sem sobrescrever registros existentes.")
parser.add_argument("path", type=Path)
args = parser.parse_args()
store = Store()
store.initialize()
print(json.dumps(import_workbook(args.path.read_bytes(), store, args.path.name), ensure_ascii=False, indent=2))

