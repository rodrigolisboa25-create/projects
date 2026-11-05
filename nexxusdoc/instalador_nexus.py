"""Completa a instalacao local iniciada por INSTALAR_NEXXUSDOC.bat.

Funciona de dois jeitos:
- a partir do pacote INSTALAR_NEXXUSDOC.zip (baixado em Configuracoes > Instalador e extraido em qualquer pasta):
  os arquivos do sistema vem da subpasta "pacote" e a pasta compartilhada do Google Drive e localizada sozinha
  (pelo arquivo marcador) ou escolhida pela pessoa;
- a partir da propria pasta compartilhada do projeto (modo antigo).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import shutil
import string
import subprocess
import sys
import tempfile


FILES = (
    "app.py",
    "budget_engine.py",      # pagina Budget: motor do orcamento, importacao e exportacao
    "budget_modelo.xlsx",    # planilha MODELO oficial do Budget (exportacao e "comecar pelo modelo")
    "budget_anterior_padrao.json",  # Budget e Forecast do ano anterior mes a mes (Ferramenta de Controle)
    "nexus_launcher.pyw",
    "assinatura.py",
    "instalador_nexus.py",
    "n8n_acesso.json",
    "nuvem_acesso.json",
    "questionnaire.json",
    "modelos_referencias_por_area.json",
    # Bases curadas (so leitura): vao assinadas com o codigo, para ninguem altera-las direto no Drive.
    "conhecimento_interno_por_area.json",
    "pgl_processos.json",
    "base_manuais.json",
    "requirements.txt",
    "README.md",
    ".env.example",
)
DIRECTORIES = ("static", "assets", "workflows")
DATA_DIRECTORIES = ("documentos_gerados", "levantamentos", "entrevistas", "base_conhecimento")
DEFAULT_PORT = "8790"
# Porta do Estoque Contabil (OpsContabil). O NexxusDoc nunca deve usa-la.
RESERVED_PORTS = {"8764", "8765"}
OBSOLETE_KEYS = ("N8N_CHAT_URL", "OPS_API_HOST", "OPS_API_PORT")
# Arquivo que identifica a pasta compartilhada do NexxusDoc no Google Drive (dados, acessos e atualizacoes).
MARKER = "NEXXUSDOC_PASTA_COMPARTILHADA.txt"
PACKAGE_DIR = "pacote"
PACKAGE_INFO = "instalacao.json"
DRIVE_ROOTS = ("Meu Drive", "My Drive", "Drives compartilhados", "Shared drives")
# Onde a pasta costuma ficar quando a pessoa adiciona o atalho da SeuProjeto ao "Meu Drive".
KNOWN_RELATIVE = (Path("Sua Area") / "Nexxus" / "NexxusDoc", Path("Nexxus") / "NexxusDoc",
                  Path("SeuProjeto") / "NexxusDoc", Path("NexxusDoc"))
# O Google Drive para computador guarda o conteudo de atalhos ("Adicionar atalho ao Drive") em
# X:\.shortcut-targets-by-id\<id da pasta>\<nome>; o id da SeuProjeto e o mesmo para todos os usuarios.
SHORTCUT_TARGETS = ".shortcut-targets-by-id"
NEWORG_ID = "CONFIGURE_DRIVE_FOLDER_ID"
# Sem o Google Drive para computador: copia local da pasta Nexxus com a mesma estrutura do Drive (os enderecos de
# pasta guardados nos documentos usam "Drives compartilhados" + caminho), sincronizada pela tela do NexxusDoc.
# Fica fora da pasta de instalacao e com nome curto: caminhos longos (anexos) estouram o limite do Windows.
CLOUD_DIR = "NexxusDoc"
CLOUD_RELATIVE = Path("Drives compartilhados") / "Sua Area" / "Nexxus" / "NexxusDoc"
CLOUD_ACCESS = "nuvem_acesso.json"


def drive_letters() -> list[Path]:
    letters = []
    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:\\")
        try:
            if any((root / name).is_dir() for name in DRIVE_ROOTS):
                letters.append(root)
        except OSError:
            continue
    return letters


def shortcut_candidates() -> list[Path]:
    """Pastas alcancadas por atalhos do Drive: alvo conhecido da SeuProjeto, outros alvos e arquivos .lnk do Meu Drive."""
    found = []
    for root in drive_letters():
        targets = root / SHORTCUT_TARGETS
        if NEWORG_ID != "CONFIGURE_DRIVE_FOLDER_ID":
            found.append(targets / NEWORG_ID / "SeuProjeto" / "NexxusDoc")
        try:
            for by_id in targets.iterdir():
                for folder in by_id.iterdir():
                    found += [folder, folder / "NexxusDoc"]
        except OSError:
            pass
        for name in ("Meu Drive", "My Drive"):
            for link in ("SeuProjeto.lnk", "NexxusDoc.lnk"):
                target = lnk_target(root / name / link)
                if target:
                    found += [target, target / "NexxusDoc"]
    return found


def system_exe(name: str) -> str:
    """Caminho completo do programa do Windows (seguranca, 05/11/2026): sem caminho, o Windows procura primeiro na pasta
    atual, e um powershell.exe/cscript.exe colocado na pasta do Drive seria executado no lugar do verdadeiro."""
    system32 = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32"
    return str(system32 / "WindowsPowerShell" / "v1.0" / name if name == "powershell.exe" else system32 / name)


def lnk_target(link: Path) -> Path | None:
    """Destino de um atalho .lnk do Windows (o Drive para computador cria um para cada atalho do Meu Drive)."""
    if not link.is_file():
        return None
    # O caminho vai por variavel de ambiente, nunca dentro do comando: um nome de atalho com apostrofo nao injeta nada.
    script = "(New-Object -ComObject WScript.Shell).CreateShortcut($env:NEXUS_LNK).TargetPath"
    result = subprocess.run([system_exe("powershell.exe"), "-NoProfile", "-Command", script], capture_output=True, text=True,
                            check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                            env={**os.environ, "NEXUS_LNK": str(link)})
    target = result.stdout.strip()
    return Path(target) if target else None


def is_shared_root(path: Path | None) -> bool:
    try:
        return bool(path) and (path / MARKER).is_file() and (path / "instalador_nexus.py").is_file()
    except OSError:
        return False


def drive_bases() -> list[Path]:
    """Pastas raiz do Google Drive para computador (G:\\Meu Drive, G:\\Drives compartilhados...) em qualquer letra."""
    bases = []
    for letter in string.ascii_uppercase:
        for name in DRIVE_ROOTS:
            base = Path(f"{letter}:\\") / name
            try:
                if base.is_dir():
                    bases.append(base)
            except OSError:
                continue
    return bases


def locate_shared_root(hints: list[str] | None = None, budget_seconds: float = 20) -> Path | None:
    """Procura a pasta compartilhada: caminhos conhecidos primeiro, depois uma busca rasa e com tempo limitado
    no Drive (listar pastas no Google Drive para computador e lento)."""
    import time

    deadline = time.monotonic() + budget_seconds
    for hint in hints or []:
        path = Path(hint) if hint else None
        if is_shared_root(path):
            return path
    for path in shortcut_candidates():
        if is_shared_root(path):
            return path
    bases = drive_bases()
    for base in bases:
        for relative in KNOWN_RELATIVE:
            if is_shared_root(base / relative):
                return base / relative
    for base in bases:  # ate 3 niveis abaixo de cada raiz (atalhos e pastas renomeadas)
        level = [base]
        for _ in range(3):
            following = []
            for folder in level:
                if time.monotonic() > deadline:
                    return None
                try:
                    children = [child for child in folder.iterdir() if child.is_dir()]
                except OSError:
                    continue
                for child in children:
                    if is_shared_root(child):
                        return child
                following += children
            level = following[:400]
    return None


def ask_shared_root() -> Path | None:
    """Ultimo recurso: a pessoa aponta a pasta NexxusDoc no Google Drive."""
    try:
        import tkinter
        from tkinter import filedialog, messagebox
    except ImportError:
        return None
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        for _ in range(3):
            chosen = filedialog.askdirectory(title="Selecione a pasta NexxusDoc no Google Drive (SeuProjeto > NexxusDoc)")
            if not chosen:
                return None
            if is_shared_root(Path(chosen)):
                return Path(chosen)
            messagebox.showwarning("NexxusDoc", "Esta não é a pasta do NexxusDoc (o arquivo "
                                   f"{MARKER} não foi encontrado nela). Escolha a pasta NexxusDoc dentro da SeuProjeto.")
    finally:
        root.destroy()
    return None


def package_source(here: Path) -> Path:
    """Arquivos do sistema: subpasta 'pacote' (ZIP extraido) ou a propria pasta (pasta compartilhada)."""
    package = here / PACKAGE_DIR
    return package if (package / "app.py").is_file() else here


def _say(text: str) -> None:
    """Mensagem de andamento: na janela do instalador vai para "Ver detalhes"; no modo texto, para o console."""
    print(text, flush=True)


def resolve_shared_root(here: Path, package: Path, ask=None) -> Path | None:
    """Pasta compartilhada no Google Drive para computador. None = modo nuvem (sem o Drive para computador, ou a pessoa
    nao apontou a pasta): o NexxusDoc usa o Drive pela nuvem, se o pacote trouxer o acesso da ponte."""
    if is_shared_root(here):
        return here
    hints = []
    try:
        hints.append(json.loads((package / PACKAGE_INFO).read_text(encoding="utf-8")).get("pasta_compartilhada", ""))
    except (OSError, ValueError):
        pass
    _say("Procurando a pasta NexxusDoc no Google Drive...")
    cloud_ready = (package / CLOUD_ACCESS).is_file()
    shared = locate_shared_root(hints)
    if not shared and cloud_ready and not drive_bases():
        _say("Este computador não tem o Google Drive para computador: o NexxusDoc vai usar o Drive pela nuvem.")
        return None
    shared = shared or (ask or ask_shared_root)()
    if not shared and cloud_ready:
        _say("Pasta do Drive não indicada: o NexxusDoc vai usar o Drive pela nuvem.")
        return None
    if not shared:
        raise RuntimeError(
            "A pasta NexxusDoc do Google Drive não foi encontrada neste computador.\n"
            "1) Confirme que o Google Drive para computador está aberto e sincronizando;\n"
            "2) no navegador, abra a pasta SeuProjeto, clique com o botão direito > Organizar > Adicionar atalho > Meu Drive;\n"
            "3) aguarde a pasta aparecer no Explorador de Arquivos e execute o instalador novamente.")
    return shared


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def set_env_value(lines: list[str], key: str, value: str) -> None:
    matching = [index for index, line in enumerate(lines) if line.startswith(f"{key}=")]
    if matching:
        lines[matching[0]] = f"{key}={value}"
        for index in reversed(matching[1:]):
            del lines[index]
    else:
        lines.append(f"{key}={value}")


def env_value(lines: list[str], key: str) -> str:
    for line in lines:
        if line.startswith(f"{key}="):
            return line.partition("=")[2].strip()
    return ""


def write_env(source: Path, install: Path, cloud: bool = False) -> None:
    env_path = install / ".env"
    if not env_path.exists():
        shutil.copy2(install / ".env.example", env_path)
    lines = env_path.read_text(encoding="utf-8-sig").splitlines()
    example = (install / ".env.example").read_text(encoding="utf-8-sig").splitlines()
    # Migra instalacoes antigas: N8N_CHAT_URL/OPS_API_PORT colidiam com o Estoque Contabil.
    n8n_url = env_value(lines, "NEXUS_N8N_URL") or env_value(lines, "N8N_CHAT_URL") or env_value(example, "NEXUS_N8N_URL")
    port = env_value(lines, "NEXUS_PORT")
    lines = [line for line in lines if not line.startswith(tuple(f"{key}=" for key in OBSOLETE_KEYS))]
    set_env_value(lines, "NEXUS_N8N_URL", n8n_url)
    set_env_value(lines, "NEXUS_PORT", port if port and port not in RESERVED_PORTS else DEFAULT_PORT)
    if not env_value(lines, "NEXUS_IDLE_MINUTES"):
        set_env_value(lines, "NEXUS_IDLE_MINUTES", "30")
    set_env_value(lines, "SHARED_PROJECT_ROOT", str(source))
    # Modo nuvem: a copia local faz o papel do Drive (inclusive para as pastas de destino dos PDFs).
    cloud_roots = str(cloud_base() / "Drives compartilhados")
    if cloud:
        set_env_value(lines, "NEXUS_MODO", "nuvem")
        set_env_value(lines, "NEXUS_SAVE_ROOTS", cloud_roots)
    else:
        lines = [line for line in lines if not line.startswith("NEXUS_MODO=")
                 and not (line.startswith("NEXUS_SAVE_ROOTS=") and env_value([line], "NEXUS_SAVE_ROOTS") == cloud_roots)]
    if not env_value(lines, "SESSION_SECRET"):
        set_env_value(lines, "SESSION_SECRET", secrets.token_urlsafe(48))
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def usable_python(python: Path) -> bool:
    if not python.is_file():
        return False
    result = subprocess.run(
        [str(python), "-c", "import sys; sys.exit(0 if sys.version_info[:2] in ((3, 11), (3, 12), (3, 13)) else 1)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _base_python() -> str:
    """Python que roda o instalador (na janela e o pythonw.exe; para criar o ambiente vale o python.exe ao lado)."""
    exe = Path(sys.executable)
    console = exe.with_name("python.exe")
    return str(console if exe.name.lower() == "pythonw.exe" and console.is_file() else exe)


def prepare_venv(install: Path) -> Path:
    venv = install / ".venv"
    python = venv / "Scripts" / "python.exe"
    if not usable_python(python):
        _say("Criando ambiente Python local...")
        if venv.exists():
            if venv.resolve().parent != install.resolve():
                raise RuntimeError("Pasta do ambiente Python fora da instalacao local.")
            run(_base_python(), "-m", "venv", "--clear", str(venv))
        else:
            run(_base_python(), "-m", "venv", str(venv))
    return python


def install_dependencies(install: Path, step=None) -> None:
    """pip install com a saida linha a linha (a janela mostra cada componente e avanca a barra)."""
    python = prepare_venv(install)
    _say("Instalando dependencias do sistema...")
    process = subprocess.Popen([str(python), "-m", "pip", "--disable-pip-version-check", "install", "-r",
                                str(install / "requirements.txt")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace",
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    tail: list[str] = []
    for line in process.stdout or []:
        line = line.rstrip()
        if not line:
            continue
        _say(line)
        tail = [*tail, line][-15:]
        if step:
            step(line)
    if process.wait():
        raise RuntimeError("A instalação dos componentes Python falhou.\n" + "\n".join(tail[-6:]))


def create_launcher(install: Path) -> Path:
    # Alternativa manual ao atalho; pythonw.exe nao abre janela de console.
    launcher = install / "INICIAR_NORMAS.bat"
    launcher.write_text(
        '@echo off\r\n'
        'start "" "%~dp0.venv\\Scripts\\pythonw.exe" "%~dp0nexus_launcher.pyw"\r\n',
        encoding="ascii",
        newline="",
    )
    return launcher


# Ícone do atalho. Ao trocar o logotipo, use um NOME novo: o Windows guarda o ícone em cache pelo caminho, e só a troca
# de caminho faz o atalho mostrar o desenho novo (refresh_shortcut_icon aponta os atalhos já criados).
SHORTCUT_ICON = "nexxusdoc_nexo.ico"


def _shortcut_icon(install: Path) -> Path:
    icon = install / "static" / "assets" / SHORTCUT_ICON
    return icon if icon.is_file() else install / "static" / "assets" / "nexxusdoc.ico"


def refresh_shortcut_icon(install: Path) -> bool:
    """Aponta os atalhos NexxusDoc desta instalação (Área de Trabalho e menu Iniciar) para o ícone atual, uma vez por
    troca de ícone (marca em logs/icone_atalho.txt), e pede ao Windows para atualizar o cache de ícones."""
    icon, pythonw = _shortcut_icon(install), install / ".venv" / "Scripts" / "pythonw.exe"
    mark = install / "logs" / "icone_atalho.txt"
    if not icon.is_file() or (mark.is_file() and mark.read_text(encoding="utf-8").strip() == icon.name):
        return False
    script = (
        'Set shell = CreateObject("WScript.Shell")\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\n'
        'For Each folder In Array(shell.SpecialFolders("Desktop"), shell.SpecialFolders("Programs"))\n'
        '    path = folder & "\\NexxusDoc.lnk"\n'
        '    If fso.FileExists(path) Then\n'
        '        Set link = shell.CreateShortcut(path)\n'
        '        If LCase(link.TargetPath) = LCase(WScript.Arguments(0)) Then\n'
        '            link.IconLocation = WScript.Arguments(1) & ",0"\n'
        '            link.Save\n'
        '        End If\n'
        '    End If\n'
        'Next\n'
    )
    hidden = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with tempfile.TemporaryDirectory(prefix="nexus-atalho-") as temp:
        vbs = Path(temp) / "icone.vbs"
        vbs.write_text(script, encoding="ascii")
        subprocess.run([system_exe("cscript.exe"), "//nologo", str(vbs), str(pythonw), str(icon)], check=True,
                       creationflags=hidden)
    subprocess.run([system_exe("ie4uinit.exe"), "-show"], check=False, creationflags=hidden)
    mark.parent.mkdir(parents=True, exist_ok=True)
    mark.write_text(icon.name, encoding="utf-8")
    return True


def create_desktop_shortcut(install: Path) -> None:
    icon = _shortcut_icon(install)
    pythonw = install / ".venv" / "Scripts" / "pythonw.exe"
    for required in (icon, pythonw):
        if not required.is_file():
            raise FileNotFoundError(f"Arquivo necessario para o atalho nao encontrado: {required}")
    script = (
        'Set shell = CreateObject("WScript.Shell")\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\n'
        'desktop = shell.SpecialFolders("Desktop")\n'
        'For Each old In Array("Nexus - Normas e Procedimentos.lnk", "NexxusDoc - Normas e Procedimentos.lnk")\n'
        '    If fso.FileExists(desktop & "\\" & old) Then fso.DeleteFile desktop & "\\" & old\n'
        'Next\n'
        'Set link = shell.CreateShortcut(desktop & "\\NexxusDoc.lnk")\n'
        'link.TargetPath = WScript.Arguments(0)\n'
        'link.Arguments = Chr(34) & WScript.Arguments(1) & Chr(34)\n'
        'link.WorkingDirectory = WScript.Arguments(2)\n'
        'link.IconLocation = WScript.Arguments(3) & ",0"\n'
        'link.WindowStyle = 7\n'
        'link.Description = "Abrir o NexxusDoc - Normas e Procedimentos Grupo SBF"\n'
        'link.Save\n'
    )
    with tempfile.TemporaryDirectory(prefix="nexus-installer-") as temp:
        vbs = Path(temp) / "atalho.vbs"
        vbs.write_text(script, encoding="ascii")
        run(system_exe("cscript.exe"), "//nologo", str(vbs), str(pythonw), str(install / "nexus_launcher.pyw"),
            str(install), str(icon))


def stop_running_nexus() -> None:
    """Encerra o servidor NexxusDoc em execucao para que a nova versao seja carregada."""
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
        "Where-Object { $_.CommandLine -like '*GrupoSBF*NormasProcedimentos*' -and "
        "($_.CommandLine -like '*nexus_launcher.pyw*' -or $_.CommandLine -like '*app.py*') } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    )
    subprocess.run([system_exe("powershell.exe"), "-NoProfile", "-Command", script], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def cloud_base() -> Path:
    """Copia local do Drive no modo nuvem (%LOCALAPPDATA%/NexxusDoc)."""
    return install_dir().parent.parent / CLOUD_DIR


def install_dir() -> Path:
    localappdata = os.environ.get("LOCALAPPDATA")
    if not localappdata:
        raise RuntimeError("LOCALAPPDATA nao esta definido para este usuario Windows.")
    return Path(localappdata) / "GrupoSBF" / "NormasProcedimentos"


# Etapas da instalacao (a janela mostra a lista e marca cada uma).
STEPS = (("pacote", "Conferir o pacote"),
         ("drive", "Achar a pasta no Google Drive"),
         ("copia", "Copiar a versão publicada"),
         ("python", "Preparar o Python"),
         ("componentes", "Instalar os componentes"),
         ("atalho", "Criar o atalho"),
         ("final", "Verificação final"))


def main(progress=None, ask=None) -> Path:
    """Instala ou atualiza. progress(etapa, percentual, texto) alimenta a janela; ask() pede a pasta do Drive."""
    report = progress or (lambda step, percent, text: _say(f"[{percent:3d}%] {text}"))
    here = Path(__file__).resolve().parent
    install = install_dir()
    if here == install.resolve():
        raise RuntimeError("Execute o instalador a partir do pacote ZIP extraido ou da pasta compartilhada.")
    report("pacote", 4, "Conferindo o pacote…")
    package = package_source(here)
    for name in FILES:
        if not (package / name).is_file():
            raise FileNotFoundError(f"Arquivo do sistema nao encontrado no pacote: {package / name}")
    for name in DIRECTORIES:
        if not (package / name).is_dir():
            raise FileNotFoundError(f"Pasta do sistema nao encontrada no pacote: {package / name}")
    report("drive", 10, "Procurando a pasta no Drive…")
    shared = resolve_shared_root(here, package, ask)
    cloud = shared is None
    if cloud:
        shared = cloud_base() / CLOUD_RELATIVE
        (cloud_base() / "Drives compartilhados" / "Sua Area" / "Nexxus" / "Docs").mkdir(parents=True, exist_ok=True)
        report("drive", 20, "Sem o Drive para computador: pela nuvem")
    _say(f"Pasta compartilhada: {shared}" + (" (cópia local, sincronizada pela nuvem)" if cloud else ""))

    report("copia", 24, "Copiando os arquivos…")
    install.mkdir(parents=True, exist_ok=True)
    stop_running_nexus()
    for name in FILES:
        shutil.copy2(package / name, install / name)
    for name in DIRECTORIES:
        shutil.copytree(package / name, install / name, dirs_exist_ok=True)
    for name in DATA_DIRECTORIES:
        (shared / name).mkdir(parents=True, exist_ok=True)
    write_env(shared, install, cloud)

    report("python", 34, "Preparando o Python…")
    prepare_venv(install)
    report("componentes", 42, "Instalando os componentes…")
    seen = {"count": 0}

    def pip_line(line: str) -> None:
        # Cada componente avanca a barra de 42% a 86%.
        if line.startswith(("Collecting", "Requirement already satisfied")):
            seen["count"] += 1
            name = line.split()[1] if line.startswith("Collecting") else line.split(":", 1)[-1].split()[0]
            name = re.split(r"[<>=!~\[,;]", name)[0]  # so o nome, sem a faixa de versao
            report("componentes", min(84, 42 + seen["count"]), f"Instalando: {name}")
        elif line.startswith("Installing collected packages"):
            report("componentes", 86, "Gravando os componentes…")
    install_dependencies(install, pip_line)

    report("atalho", 90, "Criando o atalho…")
    create_launcher(install)
    create_desktop_shortcut(install)
    # Atualiza o cache de icones do Windows para o atalho mostrar o logo novo imediatamente.
    subprocess.run([system_exe("ie4uinit.exe"), "-show"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    report("final", 96, "Verificando…")
    venv_python = install / ".venv" / "Scripts" / "python.exe"
    check = subprocess.run([str(venv_python), "-c", "import fastapi, uvicorn, reportlab, pypdf, docx, openpyxl, pptx, httpx"],
                           capture_output=True, text=True, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if check.returncode:
        raise RuntimeError("Os componentes foram instalados, mas a verificação final falhou.\n" + check.stderr[-600:])
    _say(f"NexxusDoc instalado em: {install}")
    _say(f"Dados compartilhados em: {shared}")
    report("final", 100, "Pronto!")
    return install


# ---------------------------------------------------------------------------
# Janela do instalador (no modelo do Estoque Contabil, com a identidade do NexxusDoc): etapas marcadas, barra com
# percentual, "Ver detalhes" com o registro e, no fim, "Abrir o NexxusDoc". A instalacao roda numa thread; a janela
# so recebe os eventos (Tk nao pode ser tocado fora da thread principal).
# ---------------------------------------------------------------------------
BRAND = {"green": "#003D18", "lime": "#AFD037", "cream": "#EEF3D3", "bg": "#0F1A14", "panel": "#16221C",
         "line": "#2A3B32", "text": "#E7EEE9", "muted": "#9DB0A4", "error": "#FF8A7A"}


class InstallerWindow:
    def __init__(self) -> None:
        import queue
        import tkinter as tk
        try:  # texto nitido em telas com escala (125%, 150%)
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        self.tk, self.events = tk, queue.Queue()
        self.root = tk.Tk()
        self.root.title("Instalador · NexxusDoc")
        self.root.configure(bg=BRAND["bg"])
        icon = package_source(Path(__file__).resolve().parent) / "static" / "assets" / SHORTCUT_ICON
        try:  # icone do NexxusDoc na barra de titulo e na barra de tarefas (no lugar da pena do Python)
            self.root.iconbitmap(default=str(icon))
        except Exception:
            pass
        # Janela compacta: largura fixa (acompanha a escala do Windows) e altura do proprio conteudo.
        scale = max(1.0, float(self.root.tk.call("tk", "scaling")) / 1.3333)
        self.wrap = int(340 * scale)
        self.shown, self.target, self.state, self.log_lines = 0.0, 0.0, "pronto", []
        self.current = None
        self.pulse_on = False
        self._build()
        self.root.update_idletasks()
        width, height = int(460 * scale), self.root.winfo_reqheight()
        left = max(0, (self.root.winfo_screenwidth() - width) // 2)
        top = max(0, (self.root.winfo_screenheight() - height) // 3)
        self.root.geometry(f"{width}x{height}+{left}+{top}")
        self.root.minsize(width, height)
        self.root.after(60, self._tick)

    # ----------------------------------------------------------------- layout
    def _build(self) -> None:
        tk, b = self.tk, BRAND
        here = Path(__file__).resolve().parent
        head = tk.Frame(self.root, bg=b["green"], padx=20, pady=14)
        head.pack(fill="x")
        logo = package_source(here) / "static" / "assets" / "nexxusdoc.png"
        try:
            image = tk.PhotoImage(file=str(logo))
            factor = max(1, image.width() // 40)
            self.logo = image.subsample(factor, factor)
            tk.Label(head, image=self.logo, bg=b["green"]).pack(side="left", padx=(0, 12))
        except Exception:
            self.logo = None
        titles = tk.Frame(head, bg=b["green"])
        titles.pack(side="left", fill="x")
        tk.Label(titles, text="NexxusDoc", font=("Segoe UI Semibold", 13), fg="white", bg=b["green"]).pack(anchor="w")
        tk.Label(titles, text="Instalação e atualização  ·  Grupo SBF", font=("Segoe UI", 8),
                 fg=b["lime"], bg=b["green"]).pack(anchor="w")

        # Rodape primeiro (preso embaixo): os botoes ficam sempre visiveis, mesmo com o registro aberto.
        foot = tk.Frame(self.root, bg=b["bg"], padx=20, pady=12)
        foot.pack(fill="x", side="bottom")
        body = tk.Frame(self.root, bg=b["bg"], padx=20, pady=12)
        body.pack(fill="both", expand=True)
        self.rows = {}
        steps = tk.Frame(body, bg=b["panel"], padx=14, pady=8, highlightthickness=1, highlightbackground=b["line"])
        steps.pack(fill="x")
        for key, label in STEPS:
            row = tk.Frame(steps, bg=b["panel"])
            row.pack(fill="x", pady=1)
            canvas = tk.Canvas(row, width=20, height=20, bg=b["panel"], highlightthickness=0)
            canvas.pack(side="left")
            text = tk.Label(row, text=label, font=("Segoe UI", 8), fg=b["muted"], bg=b["panel"], anchor="w")
            text.pack(side="left", padx=(10, 0))
            self.rows[key] = (canvas, text)
            self._mark(key, "pendente")

        top = tk.Frame(body, bg=b["bg"])
        top.pack(fill="x", pady=(12, 6))
        self.status = tk.Label(top, text="Pronto para instalar ou atualizar.",
                               font=("Segoe UI", 9), fg=b["text"], bg=b["bg"], anchor="w", justify="left",
                               wraplength=self.wrap)
        self.status.pack(side="left", fill="x", expand=True)
        self.percent = tk.Label(top, text="0%", font=("Segoe UI Semibold", 11), fg=b["lime"], bg=b["bg"])
        self.percent.pack(side="right")
        self.bar = tk.Canvas(body, height=12, bg=b["line"], highlightthickness=0)
        self.bar.pack(fill="x")

        self.details_btn = tk.Label(body, text="Ver detalhes", font=("Segoe UI", 8, "underline"), fg=b["lime"],
                                    bg=b["bg"], cursor="hand2")
        self.details_btn.pack(anchor="w", pady=(10, 4))
        self.details_btn.bind("<Button-1>", lambda _e: self._toggle_details())
        self.log = tk.Text(body, height=6, font=("Consolas", 8), bg="#0B130F", fg="#C6D5CF", relief="flat",
                           insertbackground=b["lime"], state="disabled", wrap="word")

        self.where = tk.Label(foot, text="Instala só para você, neste computador.", font=("Segoe UI", 8),
                              fg=b["muted"], bg=b["bg"], anchor="w", justify="left")
        self.where.pack(side="left", fill="x", expand=True)
        self.close_btn = tk.Button(foot, text="Fechar", font=("Segoe UI", 9), fg=b["text"], bg=b["panel"],
                                   activebackground=b["line"], activeforeground="white", relief="flat", padx=16, pady=6,
                                   bd=0, cursor="hand2", command=self.root.destroy)
        self.close_btn.pack(side="right", padx=(10, 0))
        self.action = tk.Button(foot, text="Instalar / Atualizar", font=("Segoe UI Semibold", 9), fg="#0D1A12",
                                bg=b["lime"], activebackground="#C4E05A", activeforeground="#0D1A12", relief="flat",
                                padx=18, pady=6, bd=0, cursor="hand2", command=self.start)
        self.action.pack(side="right")

    def _mark(self, key: str, status: str) -> None:
        """Marca desenhada (sem emoji): pendente = circulo vazio; em andamento = circulo lime pulsando; feito = visto."""
        canvas, label = self.rows[key]
        b = BRAND
        canvas.delete("all")
        if status == "feito":
            canvas.create_oval(2, 2, 20, 20, fill=b["lime"], outline=b["lime"])
            canvas.create_line(6.5, 11.5, 9.8, 14.8, 15.5, 7.5, fill="#0D1A12", width=2.4, capstyle="round", joinstyle="round")
            label.configure(fg=b["text"], font=("Segoe UI", 8))
        elif status == "andamento":
            canvas.create_oval(2, 2, 20, 20, outline=b["lime"], width=2)
            canvas.create_oval(7, 7, 15, 15, fill=b["lime"] if self.pulse_on else b["green"], outline="", tags="dot")
            label.configure(fg="white", font=("Segoe UI Semibold", 8))
        elif status == "erro":
            canvas.create_oval(2, 2, 20, 20, outline=b["error"], width=2)
            canvas.create_line(7.5, 7.5, 14.5, 14.5, fill=b["error"], width=2.2)
            canvas.create_line(14.5, 7.5, 7.5, 14.5, fill=b["error"], width=2.2)
            label.configure(fg=b["error"], font=("Segoe UI Semibold", 8))
        else:
            canvas.create_oval(3, 3, 19, 19, outline=b["line"], width=2)
            label.configure(fg=b["muted"], font=("Segoe UI", 8))
        canvas.scale("all", 0, 0, 0.82, 0.82)  # marca proporcional a letra menor
        canvas.move("all", 1.5, 1.5)

    def _toggle_details(self) -> None:
        if self.log.winfo_ismapped():
            self.log.pack_forget()
            self.details_btn.configure(text="Ver detalhes")
        else:
            self.log.pack(fill="both", expand=True)
            self.details_btn.configure(text="Ocultar detalhes")
        # a janela cresce ou volta ao tamanho compacto junto com o registro
        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_width(), 1)
        self.root.geometry(f"{self.root.winfo_width()}x{self.root.winfo_reqheight()}")

    def _append(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # --------------------------------------------------------------- animacao
    def _tick(self) -> None:
        import queue
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "progress":
                    step, value, text = data
                    order = [k for k, _ in STEPS]
                    for key in order[:order.index(step)]:
                        self._mark(key, "feito")
                    self.current = step
                    self._mark(step, "feito" if value >= 100 else "andamento")
                    self.target = float(value)
                    self.status.configure(text=text, fg=BRAND["text"])
                elif kind == "log":
                    self._append(data)
                elif kind == "ask":
                    data()
                elif kind == "done":
                    self._finish_ok()
                elif kind == "error":
                    self._finish_error(data)
        except queue.Empty:
            pass
        # barra suave ate o alvo, com brilho correndo enquanto instala
        self.shown += (self.target - self.shown) * 0.12
        width = max(1, self.bar.winfo_width())
        self.bar.delete("all")
        filled = width * self.shown / 100
        self.bar.create_rectangle(0, 0, filled, 12, fill=BRAND["lime"], outline="")
        if self.state == "instalando" and filled > 30:
            x = (self.root.tk.call("clock", "milliseconds") // 6) % int(filled + 60) - 60
            self.bar.create_rectangle(max(0, x), 0, min(filled, x + 60), 12, fill="#D6EE7A", outline="")
        self.percent.configure(text=f"{int(round(self.shown))}%")
        # ponto da etapa atual pulsando
        if self.state == "instalando" and self.current:
            self.pulse_on = (self.root.tk.call("clock", "milliseconds") // 450) % 2 == 0
            canvas = self.rows[self.current][0]
            if canvas.find_withtag("dot"):
                canvas.itemconfigure("dot", fill=BRAND["lime"] if self.pulse_on else BRAND["green"])
        self.root.after(33, self._tick)

    # ---------------------------------------------------------------- acoes
    def progress(self, step: str, value: int, text: str) -> None:
        self.events.put(("progress", (step, value, text)))
        self.events.put(("log", f"[{value:3d}%] {text}"))

    def ask_folder(self):
        """Chamado pela thread da instalacao: abre o seletor de pasta na thread da janela e espera a resposta."""
        import threading
        done, answer = threading.Event(), {}

        def show() -> None:
            from tkinter import filedialog, messagebox
            for _ in range(3):
                chosen = filedialog.askdirectory(parent=self.root, title="Selecione a pasta NexxusDoc no Google Drive")
                if not chosen:
                    break
                if is_shared_root(Path(chosen)):
                    answer["path"] = Path(chosen)
                    break
                messagebox.showwarning("NexxusDoc", f"Esta não é a pasta do NexxusDoc (o arquivo {MARKER} não está nela).",
                                       parent=self.root)
            done.set()

        self.events.put(("ask", show))
        done.wait()
        return answer.get("path")

    def start(self) -> None:
        import threading
        import traceback
        global _say
        self.state, self.target, self.shown = "instalando", 0.0, 0.0
        for key, _ in STEPS:
            self._mark(key, "pendente")
        self.action.configure(state="disabled", text="Instalando…", bg="#7E9632")
        self.close_btn.configure(state="disabled")
        _say = lambda text: self.events.put(("log", str(text)))  # noqa: E731

        def work() -> None:
            try:
                main(self.progress, self.ask_folder)
                self.events.put(("done", None))
            except Exception as exc:
                log = install_dir() / "logs" / "instalador.log"
                try:
                    log.parent.mkdir(parents=True, exist_ok=True)
                    with log.open("a", encoding="utf-8") as handle:
                        handle.write("\n" + traceback.format_exc())
                except OSError:
                    pass
                self.events.put(("error", f"{exc}\n\nRegistro: {log}"))

        threading.Thread(target=work, daemon=True).start()

    def _finish_ok(self) -> None:
        self.state = "concluido"
        for key, _ in STEPS:
            self._mark(key, "feito")
        self.status.configure(text="Instalado. O atalho está na Área de Trabalho.", fg=BRAND["lime"])
        self.action.configure(state="normal", text="Abrir o NexxusDoc", bg=BRAND["lime"], command=self.open_app)
        self.close_btn.configure(state="normal")

    def _finish_error(self, message: str) -> None:
        self.state = "erro"
        if self.current:
            self._mark(self.current, "erro")
        self.status.configure(text="Não foi possível concluir. Veja os detalhes abaixo.", fg=BRAND["error"])
        self._append("ERRO: " + message)
        if not self.log.winfo_ismapped():
            self._toggle_details()
        self.action.configure(state="normal", text="Tentar novamente", bg=BRAND["lime"], command=self.start)
        self.close_btn.configure(state="normal")

    def open_app(self) -> None:
        install = install_dir()
        subprocess.Popen([str(install / ".venv" / "Scripts" / "pythonw.exe"), str(install / "nexus_launcher.pyw")],
                         cwd=str(install), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    if "--janela" in sys.argv:
        try:
            InstallerWindow().run()
        except ImportError:  # Python sem Tkinter: segue no modo texto
            sys.argv.remove("--janela")
    if "--janela" not in sys.argv:
        try:
            main()
            print("Atalho criado na Area de Trabalho.")
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"ERRO: {exc}", file=sys.stderr)
            sys.exit(1)
