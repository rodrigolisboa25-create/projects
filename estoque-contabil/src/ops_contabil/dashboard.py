from pathlib import Path

from fastapi.responses import HTMLResponse

from .web.app import create_app

app = create_app()
app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) != "/"]


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    path = Path(__file__).parent / "web" / "templates" / "dashboard.html"
    return path.read_text(encoding="utf-8")
