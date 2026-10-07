# ruff: noqa: E501
from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
import zipfile
from pathlib import Path
from tkinter import BOTH, END, LEFT, Button, Label, StringVar, Text, Tk, X, messagebox, ttk

APP_NAME = "Estoque Contábil"
INSTALLER_ENTRY_NAME = "INSTALAR_ESTOQUE_CONTABIL.bat"
INSTALLER_ARCHIVE_NAME = "INSTALAR_ESTOQUE_CONTABIL.zip"
MANIFEST_NAME = "INSTALAR_ESTOQUE_CONTABIL.manifest.json"
LOCAL_ROOT = Path(
    os.environ.get("OPS_INSTALL_ROOT")
    or (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OpsContabil")
)
RUNTIME_ROOT = LOCAL_ROOT / "runtime"
APP_ROOT = RUNTIME_ROOT / "app"
VENV_ROOT = RUNTIME_ROOT / ".venv"
LOG_FILE = LOCAL_ROOT / "logs" / "installer.log"


def payload_root() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "payload"


def run(
    command: list[str],
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        env=env,
        cwd=None if cwd is None else str(cwd),
    )
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"\n> {' '.join(command)}\n{result.stdout or ''}\n")
    if check and result.returncode:
        detail = (result.stdout or "").strip()[-2000:]
        raise RuntimeError(f"Comando falhou ({result.returncode}).\n{detail}")
    return result


def find_python() -> Path | None:
    candidates: list[list[str]] = [
        ["py", "-3.13", "-c", "import sys;print(sys.executable)"],
        ["py", "-3.12", "-c", "import sys;print(sys.executable)"],
        ["python", "-c", "import sys;print(sys.executable)"],
    ]
    local_programs = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python"
    for version in ("Python313", "Python312"):
        candidate = local_programs / version / "python.exe"
        if candidate.is_file():
            return candidate
    for command in candidates:
        try:
            result = run(command, check=False)
        except OSError:
            continue
        if result.returncode == 0:
            candidate = Path(result.stdout.strip().splitlines()[-1])
            if candidate.is_file():
                return candidate
    return None


def install_python() -> Path:
    winget = shutil.which("winget")
    if not winget:
        raise RuntimeError(
            "O Python não foi localizado e o Windows Package Manager (winget) não está disponível. "
            "Atualize o App Installer do Windows e execute este instalador novamente."
        )
    run(
        [
            winget,
            "install",
            "--id",
            "Python.Python.3.13",
            "--exact",
            "--scope",
            "user",
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
    )
    python = find_python()
    if not python:
        raise RuntimeError("O Python foi instalado, mas ainda não foi localizado nesta sessão do Windows.")
    return python


def stop_local_server() -> None:
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        "$connections=Get-NetTCPConnection -LocalPort 8765 -State Listen;"
        "foreach($c in $connections){$p=Get-CimInstance Win32_Process -Filter \"ProcessId=$($c.OwningProcess)\";"
        "if($p.CommandLine -match 'ops_contabil|uvicorn'){Stop-Process -Id $c.OwningProcess -Force}}"
    )
    run(["powershell.exe", "-NoProfile", "-Command", script], check=False)


def write_launcher() -> Path:
    launcher = LOCAL_ROOT / "ABRIR_ESTOQUE_CONTABIL.ps1"
    launcher.write_text(
        r"""$ErrorActionPreference = 'Stop'
$LocalRoot = Join-Path $env:LOCALAPPDATA 'OpsContabil'
$Runtime = Join-Path $LocalRoot 'runtime'
$App = Join-Path $Runtime 'app'
$Python = Join-Path $Runtime '.venv\Scripts\python.exe'
$LogDir = Join-Path $LocalRoot 'logs'
if (-not (Test-Path -LiteralPath $Python) -or -not (Test-Path -LiteralPath (Join-Path $App 'src\ops_contabil\dashboard_runtime.py'))) {
  Add-Type -AssemblyName PresentationFramework
  [System.Windows.MessageBox]::Show('A instalação local está incompleta. Extraia o pacote ZIP e execute INSTALAR_ESTOQUE_CONTABIL.bat novamente.','Estoque Contábil') | Out-Null
  exit 1
}
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$env:PYTHONPATH = Join-Path $App 'src'
$env:OPS_CONFIG = Join-Path $App 'config\production.yaml'
$env:OPS_PROJECT_ROOT = $App
$env:OPS_ALL_BRAZIL_ROOT = ''
foreach ($drive in [char[]](67..90)) {
  foreach ($relative in @('Drives compartilhados\@All Brazil Materials','Shared drives\@All Brazil Materials')) {
    $candidate = "${drive}:\$relative"
    if (Test-Path -LiteralPath $candidate) { $env:OPS_ALL_BRAZIL_ROOT = $candidate; break }
  }
  if ($env:OPS_ALL_BRAZIL_ROOT) { break }
}
$env:N8N_CHAT_URL = 'https://n8n.gruposbf.com.br/webhook/df8be6d7-e39e-44c0-98b1-45db38a82109/chat'
$ready = $false
try { $ready = (Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8765/health' -TimeoutSec 1).StatusCode -eq 200 } catch {}
if (-not $ready) {
  Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','ops_contabil.dashboard_runtime:app','--host','127.0.0.1','--port','8765' -WorkingDirectory $App -RedirectStandardOutput (Join-Path $LogDir 'server.out.log') -RedirectStandardError (Join-Path $LogDir 'server.err.log') -WindowStyle Hidden
  for ($i=0; $i -lt 45; $i++) {
    try { if ((Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8765/health' -TimeoutSec 1).StatusCode -eq 200) { $ready = $true; break } } catch {}
    Start-Sleep -Seconds 1
  }
}
if (-not $ready) {
  Add-Type -AssemblyName PresentationFramework
  [System.Windows.MessageBox]::Show("O sistema não iniciou. Consulte $LogDir\server.err.log",'Estoque Contábil') | Out-Null
  exit 1
}
Start-Process 'http://127.0.0.1:8765/'
""",
        encoding="utf-8-sig",
    )
    vbs = LOCAL_ROOT / "ABRIR_ESTOQUE_CONTABIL.vbs"
    vbs.write_text(
        f'Set shell = CreateObject("WScript.Shell")\n'
        f'launcher = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\\OpsContabil\\ABRIR_ESTOQUE_CONTABIL.ps1")\n'
        f'shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & launcher & """", 0, False\n',
        # O Windows Script Host de algumas imagens corporativas rejeita BOM UTF-8
        # como caractere inválido na linha 1. O launcher usa somente ASCII e deve
        # começar diretamente por "Set", sem EF BB BF.
        encoding="ascii",
    )
    # Ícone próprio do atalho, fora da pasta app (que é trocada a cada atualização).
    icon = LOCAL_ROOT / "estoque_contabil.ico"
    bundled_icon = APP_ROOT / "src" / "ops_contabil" / "assets" / "estoque_contabil.ico"
    if bundled_icon.is_file():
        shutil.copyfile(bundled_icon, icon)
    if os.environ.get("OPS_INSTALL_NO_SHORTCUT", "").strip() != "1":
        powershell = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        ps = (
            "$desktop=[Environment]::GetFolderPath('Desktop');"
            "$shortcut=Join-Path $desktop 'Estoque Contábil.lnk';"
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($shortcut);"
            "$s.TargetPath='"
            + str(powershell).replace("'", "''")
            + "';$s.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \""
            + str(launcher).replace("'", "''")
            + "\"';$s.WorkingDirectory='"
            + str(LOCAL_ROOT).replace("'", "''")
            + "';$s.Description='Abrir Estoque Contábil (inicializador direto)';"
            + ("$s.IconLocation='" + str(icon).replace("'", "''") + ",0';" if icon.is_file() else "")
            + "$s.Save()"
        )
        run(["powershell.exe", "-NoProfile", "-Command", ps])
    return launcher


def install(progress) -> None:
    payload = payload_root()
    if not (payload / "src" / "ops_contabil" / "dashboard_runtime.py").is_file():
        raise RuntimeError("O pacote interno do instalador está incompleto.")

    progress(5, "Verificando o computador…")
    LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
    python = find_python()
    if not python:
        progress(12, "Baixando e instalando o Python…")
        python = install_python()

    progress(25, "Preparando o ambiente Python…")
    if not (VENV_ROOT / "Scripts" / "python.exe").is_file():
        run([str(python), "-m", "venv", str(VENV_ROOT)])
    venv_python = VENV_ROOT / "Scripts" / "python.exe"
    run([str(venv_python), "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip"])

    staging = RUNTIME_ROOT / f".app-update-{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
    progress(38, "Copiando a versão publicada…")
    shutil.copytree(payload, staging)

    progress(52, "Instalando e validando as dependências…")
    run([str(venv_python), "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", str(staging)])
    run(
        [
            str(venv_python),
            "-c",
            "import fastapi,duckdb,openpyxl,ops_contabil;print('dependencias-ok')",
        ]
    )

    progress(68, "Preparando a fotografia de dados dos relatórios…")
    if os.environ.get("OPS_INSTALL_TEST_MODE") != "1":
        stop_local_server()
    seed_database = staging / "seed" / "ops_contabil.duckdb"
    target_database = LOCAL_ROOT / "processed" / "ops_contabil.duckdb"
    run(
        [
            str(venv_python),
            "-m",
            "ops_contabil.seed_data",
            "apply",
            "--seed",
            str(seed_database),
            "--target",
            str(target_database),
        ]
    )

    progress(80, "Ativando a nova versão…")
    previous = RUNTIME_ROOT / "app.previous"
    if previous.exists():
        shutil.rmtree(previous)
    try:
        if APP_ROOT.exists():
            APP_ROOT.rename(previous)
        staging.rename(APP_ROOT)
    except Exception:
        if not APP_ROOT.exists() and previous.exists():
            previous.rename(APP_ROOT)
        raise

    progress(90, "Configurando o inicializador…")
    dist = APP_ROOT / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    bundled_manifest = APP_ROOT / MANIFEST_NAME
    if bundled_manifest.is_file():
        shutil.copy2(bundled_manifest, dist / MANIFEST_NAME)
    archive = dist / INSTALLER_ARCHIVE_NAME
    installer_source = Path(__file__).resolve().parent
    entry_source = installer_source / INSTALLER_ENTRY_NAME
    if not entry_source.is_file():
        raise RuntimeError(f"O pacote não contém {INSTALLER_ENTRY_NAME}.")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        package.write(entry_source, INSTALLER_ENTRY_NAME)
        package.write(Path(__file__).resolve(), "installer_main.py")
        if (dist / MANIFEST_NAME).is_file():
            package.write(dist / MANIFEST_NAME, MANIFEST_NAME)
        for source in sorted(payload.rglob("*")):
            if source.is_file():
                package.write(source, Path("payload") / source.relative_to(payload))
        package.writestr(
            "LEIA-ME.txt",
            "Estoque Contábil\n\n"
            "1. Extraia todo o conteúdo deste ZIP.\n"
            "2. Execute INSTALAR_ESTOQUE_CONTABIL.bat.\n"
            "3. O mesmo arquivo instala ou atualiza o sistema sem apagar dados locais mais novos.\n",
        )
    write_launcher()

    progress(97, "Executando a verificação final…")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(APP_ROOT / "src")
    env["OPS_CONFIG"] = str(APP_ROOT / "config" / "production.yaml")
    run(
        [
            str(venv_python),
            "-c",
            "from ops_contabil.settings_runtime import load_runtime_settings; load_runtime_settings(); print('runtime-ok')",
        ],
        env=env,
        cwd=APP_ROOT,
    )
    progress(100, "Instalação concluída. O sistema está pronto!")


class InstallerWindow:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(f"Instalador · {APP_NAME}")
        self.root.geometry("650x390")
        self.root.minsize(650, 390)
        self.root.configure(bg="#f4f7f5")
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.status = StringVar(value="Pronto para instalar ou atualizar o sistema.")
        self.percent = StringVar(value="0%")
        self._build()

    def _build(self) -> None:
        header = ttk.Frame(self.root, padding=(28, 24, 28, 16))
        header.pack(fill=X)
        Label(header, text="Estoque Contábil", font=("Segoe UI", 21, "bold"), fg="#005E27", bg="#f4f7f5").pack(anchor="w")
        Label(header, text="Instalação e atualização segura do ambiente local", font=("Segoe UI", 10), fg="#486156", bg="#f4f7f5").pack(anchor="w", pady=(4, 0))
        body = ttk.Frame(self.root, padding=(28, 8, 28, 18))
        body.pack(fill=BOTH, expand=True)
        top = ttk.Frame(body)
        top.pack(fill=X, pady=(0, 8))
        ttk.Label(top, textvariable=self.status).pack(side=LEFT)
        ttk.Label(top, textvariable=self.percent).pack(side="right")
        self.bar = ttk.Progressbar(body, maximum=100, mode="determinate")
        self.bar.pack(fill=X, pady=(0, 15))
        self.log = Text(body, height=8, font=("Consolas", 9), relief="flat", bg="#e9f1ec", fg="#173f2c", state="disabled")
        self.log.pack(fill=BOTH, expand=True)
        footer = ttk.Frame(self.root, padding=(28, 0, 28, 24))
        footer.pack(fill=X)
        self.action = Button(footer, text="Instalar / Atualizar", font=("Segoe UI", 10, "bold"), bg="#005E27", fg="white", activebackground="#00451d", activeforeground="white", relief="flat", padx=22, pady=9, command=self.start)
        self.action.pack(side="right")
        self.root.after(100, self.poll)

    def append(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(END, text + "\n")
        self.log.see(END)
        self.log.configure(state="disabled")

    def progress(self, value: int, status: str) -> None:
        self.events.put(("progress", (value, status)))

    def start(self) -> None:
        self.action.configure(state="disabled")
        self.append("Iniciando a preparação do computador…")

        def worker() -> None:
            try:
                install(self.progress)
                self.events.put(("done", None))
            except Exception as exc:  # noqa: BLE001 - a falha precisa ser exibida pela interface.
                LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
                with LOG_FILE.open("a", encoding="utf-8") as handle:
                    handle.write("\n" + traceback.format_exc() + "\n")
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def poll(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "progress":
                    value, status = payload
                    self.bar["value"] = value
                    self.percent.set(f"{value}%")
                    self.status.set(status)
                    self.append(status)
                elif event == "done":
                    self.action.configure(text="Concluir", state="normal", command=self.finish)
                    messagebox.showinfo(APP_NAME, "Instalação concluída. Um atalho foi criado na Área de Trabalho.")
                elif event == "error":
                    self.status.set("A instalação não foi concluída.")
                    self.action.configure(text="Tentar novamente", state="normal", command=self.start)
                    messagebox.showerror(APP_NAME, f"Não foi possível concluir a instalação.\n\n{payload}\n\nLog: {LOG_FILE}")
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def finish(self) -> None:
        launcher = LOCAL_ROOT / "ABRIR_ESTOQUE_CONTABIL.ps1"
        if launcher.is_file():
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-WindowStyle",
                    "Hidden",
                    "-File",
                    str(launcher),
                ],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    if "--silent" in sys.argv:
        def silent_progress(value: int, status: str) -> None:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(f"\n{value}% {status}\n")

        try:
            install(silent_progress)
        except Exception:  # noqa: BLE001 - o modo de teste precisa propagar o diagnóstico completo.
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write("\n" + traceback.format_exc() + "\n")
            raise SystemExit(1)
    else:
        InstallerWindow().run()
