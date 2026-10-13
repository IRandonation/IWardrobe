import json
from iwardrobe.config import ROOT
from iwardrobe.main import app

path = ROOT / "apps/web/openapi.json"
path.write_text(
    json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(path)
