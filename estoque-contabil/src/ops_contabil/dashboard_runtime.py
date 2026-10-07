from pathlib import Path

from fastapi.responses import HTMLResponse

from .settings_runtime import load_runtime_settings
from .web.app import create_app

app = create_app(load_runtime_settings())
app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) != "/"]


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return (Path(__file__).parent / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")
