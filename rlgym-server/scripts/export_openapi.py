import json
from app.api import app

with open("openapi.json", "w") as f:
    json.dump(app.openapi(), f, indent=2)