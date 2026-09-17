import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from backend.storage import ROOT, Store
load_dotenv(ROOT / ".env")
Store().initialize()
print("Banco inicializado.")

