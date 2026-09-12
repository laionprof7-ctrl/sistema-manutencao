import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Garante que a suíte nunca use as credenciais ou o banco de produção.
os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
