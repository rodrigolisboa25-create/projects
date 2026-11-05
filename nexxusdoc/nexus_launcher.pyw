"""Inicia o NexxusDoc em segundo plano, sem janela de console, e abre o navegador.

Executado pelo atalho da Area de Trabalho com pythonw.exe:
- se o NexxusDoc ja estiver rodando, apenas abre o navegador;
- se a porta estiver ocupada por outro sistema, avisa em vez de disputar a porta;
- abre o navegador somente quando o servidor responde (sem tela de erro na abertura);
- encerra o servidor sozinho apos um periodo sem uso (navegador fechado).
"""

from __future__ import annotations

import ctypes
import json
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "nexus.log"
# pythonw nao tem console: stdout/stderr precisam ir para um arquivo antes de importar o uvicorn.
_log = open(LOG_FILE, "w" if LOG_FILE.is_file() and LOG_FILE.stat().st_size > 2_000_000 else "a",
            encoding="utf-8", buffering=1)
sys.stdout = sys.stderr = _log

from dotenv import dotenv_values  # noqa: E402

CONFIG = dotenv_values(ROOT / ".env", encoding="utf-8-sig")  # tolera .env salvo com BOM pelo Bloco de Notas
HOST = "127.0.0.1"
PORT = int(CONFIG.get("NEXUS_PORT") or 8790)
IDLE_SECONDS = int(CONFIG.get("NEXUS_IDLE_MINUTES") or 30) * 60
URL = f"http://{HOST}:{PORT}/"
TITLE = "NexxusDoc - Normas e Procedimentos"
# Sem o Google Drive para computador (instalado em modo nuvem): a tela sincroniza a copia local da pasta pela ponte do
# Apps Script, que precisa da conta Google do Grupo SBF no navegador.
CLOUD_MODE = (CONFIG.get("NEXUS_MODO") or "").strip().casefold() == "nuvem"


def open_browser() -> None:
    """Abre SEMPRE no Chrome quando instalado (pedido do usuario em 05/11/2026; antes so no modo nuvem, e o Edge, navegador
    padrao, abria nas demais): e nele que esta a conta Google do Grupo SBF (foto do avatar e pontes do Apps Script).
    Sem Chrome, o navegador padrao."""
    import os
    import subprocess
    for base in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""),
                 os.environ.get("LOCALAPPDATA", "")):
        chrome = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
        if base and chrome.is_file():
            subprocess.Popen([str(chrome), URL])
            return
    webbrowser.open(URL)


def wait_for_drive(folder: Path, seconds: int = 90) -> bool:
    """A pasta do Drive sumiu (Google Drive para computador fechado): tenta abrir o programa e espera a pasta voltar."""
    import os
    import subprocess
    if folder.is_dir():
        return True
    for base in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", "")):
        found = sorted((Path(base) / "Google" / "Drive File Stream").glob("*/GoogleDriveFS.exe")) if base else []
        if found:
            print("Pasta do Drive indisponivel: abrindo o Google Drive para computador.", flush=True)
            subprocess.Popen([str(found[-1])])
            break
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if folder.is_dir():
            return True
        time.sleep(2)
    return False


def _local_module(name: str):
    """Modulo da PROPRIA instalacao (copia ja verificada). Nunca executa codigo direto da pasta do Drive."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"{name}_local", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def follow_moved_folder(source: Path) -> Path:
    """Se a pasta do projeto mudou de lugar no Drive (PASTA_MOVIDA.json na pasta antiga), aponta a instalacao
    para a nova pasta e grava no .env, sem reinstalar. So aceita uma pasta que tenha publicacao assinada valida."""
    notice = source / "PASTA_MOVIDA.json"
    if not notice.is_file():
        return source
    target = json.loads(notice.read_text(encoding="utf-8")).get("nova_pasta", "")
    found = _local_module("instalador_nexus").locate_shared_root([target])
    if found and _local_module("assinatura").verified_manifest(found) is None:
        print(f"PASTA_MOVIDA.json aponta para {found}, que nao tem publicacao assinada valida: ignorado.", flush=True)
        return source
    if not found:
        print(f"Pasta do projeto movida para {target}, mas ela nao esta acessivel neste computador.", flush=True)
        message("O NexxusDoc mudou de pasta no Google Drive (SeuProjeto > NexxusDoc).\n\n"
                "Para continuar recebendo dados e atualizações: no navegador, abra 'Compartilhados comigo', clique com o "
                "botão direito na pasta SeuProjeto > Organizar > Adicionar atalho > Meu Drive. Depois abra o NexxusDoc de novo.")
        return source
    env_path = ROOT / ".env"
    lines = [line for line in env_path.read_text(encoding="utf-8-sig").splitlines()
             if not line.startswith("SHARED_PROJECT_ROOT=")]
    env_path.write_text("\n".join([*lines, f"SHARED_PROJECT_ROOT={found}"]) + "\n", encoding="utf-8")
    CONFIG["SHARED_PROJECT_ROOT"] = str(found)
    print(f"Pasta do projeto atualizada para {found}", flush=True)
    return found


INSTALLED_VERSION = ROOT / "publicacao_instalada.json"


def auto_update() -> None:
    """Atualiza esta instalacao a partir da pasta compartilhada do Drive, somente com publicacao ASSINADA.

    O administrador publica com a chave que fica na Area de Trabalho dele (publicar.py); aqui so sao aplicados
    arquivos que conferem com o manifesto assinado (publicacao.json + publicacao.sig). Alteracao feita direto no
    Drive, publicacao incompleta ou versao mais antiga que a instalada: nada e aplicado e o sistema abre na versao
    atual. Nenhum codigo da pasta do Drive e executado antes da verificacao.
    """
    import hashlib
    import subprocess

    source = follow_moved_folder(Path(CONFIG.get("SHARED_PROJECT_ROOT") or ""))
    if not (source / "publicacao.json").is_file():
        return
    signing = _local_module("assinatura")
    manifest = signing.verified_manifest(source)
    if manifest is None:
        print("Atualizacao ignorada: a publicacao no Drive nao tem assinatura valida do administrador.", flush=True)
        return
    try:
        installed = json.loads(INSTALLED_VERSION.read_text(encoding="utf-8")).get("versao", "")
    except (OSError, ValueError):
        installed = ""
    if installed and manifest.get("versao", "") < installed:
        print(f"Atualizacao ignorada: publicacao {manifest.get('versao')} e mais antiga que a instalada ({installed}).", flush=True)
        return
    # Le cada arquivo uma vez e confere o conteudo lido (o mesmo que sera gravado) com o manifesto.
    staged, wrong = [], []
    for relative, expected in manifest["arquivos"].items():
        path = source / relative
        if ".." in Path(relative).parts or Path(relative).is_absolute():
            wrong.append(relative)
            continue
        data = path.read_bytes() if path.is_file() else None
        if data is None or hashlib.sha256(data).hexdigest() != expected:
            wrong.append(relative)
            continue
        dst = ROOT / relative
        if not dst.is_file() or hashlib.sha256(dst.read_bytes()).hexdigest() != expected:
            staged.append((relative, data))
    if wrong:
        print(f"Atualizacao ignorada: {len(wrong)} arquivo(s) do Drive diferentes da publicacao assinada "
              f"(alteracao nao publicada ou indevida): {', '.join(wrong[:10])}", flush=True)
        return
    changed = []
    for relative, data in staged:
        dst = ROOT / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        temp = dst.with_name(dst.name + ".novo")
        temp.write_bytes(data)
        temp.replace(dst)
        changed.append(relative)
    INSTALLED_VERSION.write_text(json.dumps({"versao": manifest.get("versao", "")}), encoding="utf-8")
    if changed:
        print(f"Atualizado a partir do Drive (publicacao assinada {manifest.get('versao')}): "
              f"{', '.join(changed[:20])}", flush=True)
    if "requirements.txt" in changed:
        subprocess.run([sys.executable.replace("pythonw.exe", "python.exe"), "-m", "pip", "--disable-pip-version-check",
                        "install", "-q", "-r", str(ROOT / "requirements.txt")],
                       check=False, stdout=_log, stderr=_log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def message(text: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, text, TITLE, 0x10)


def nexus_running() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}api/health", timeout=1.5) as response:
            return json.loads(response.read()).get("app") == "nexus"
    except Exception:
        return False


def port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex((HOST, PORT)) == 0


def wait_and_open(timeout: float = 90, browser: bool = True) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if nexus_running():
            if browser:
                open_browser()
            return True
        time.sleep(0.3)
    return False


# "Atualizar" na tela (05/11/2026): o servidor em uso abre um novo iniciador com --reiniciar e sai. O novo espera o
# antigo terminar (mutex e porta livres), aplica a publicacao assinada como numa abertura normal e sobe o servidor
# sem abrir outra aba: a tela que pediu a atualizacao recarrega sozinha.
RESTART = "--reiniciar" in sys.argv
MUTEX_NAME = "Local\\GrupoSBF.NexxusDoc.NormasProcedimentos"


def relaunch() -> None:
    import subprocess
    flags = getattr(subprocess, "DETACHED_PROCESS", 0x8) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--reiniciar"], cwd=str(ROOT), close_fds=True,
                     creationflags=flags)
    print("Reiniciando para aplicar a versao nova (pedido pela tela).", flush=True)


def take_mutex(wait_seconds: float) -> bool:
    """Um unico servidor por usuario. Ao reiniciar, espera o servidor antigo liberar o mutex."""
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    deadline = time.monotonic() + wait_seconds
    while True:
        handle = kernel.CreateMutexW(None, False, MUTEX_NAME)
        if kernel.GetLastError() != 183:  # ERROR_ALREADY_EXISTS
            return True
        kernel.CloseHandle(handle)
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)


def main() -> None:
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando NexxusDoc em {URL}"
          + (" (reinicio para atualizar)" if RESTART else ""), flush=True)
    # Um unico servidor por usuario; cliques repetidos no atalho so abrem o navegador.
    if not take_mutex(60 if RESTART else 0):
        if RESTART:
            message("O NexxusDoc não conseguiu reiniciar para atualizar. Feche o navegador e abra o atalho de novo.")
        elif not wait_and_open():
            message("O NexxusDoc já está iniciando, mas não respondeu. Tente abrir o atalho novamente em alguns segundos.")
        return
    if RESTART:
        deadline = time.monotonic() + 30
        while port_in_use() and time.monotonic() < deadline:
            time.sleep(0.5)
    if nexus_running():
        open_browser()
        return
    if port_in_use():
        message(f"A porta {PORT} está sendo usada por outro programa.\n\n"
                f"Altere NEXUS_PORT no arquivo:\n{ROOT / '.env'}\n\ne abra o atalho novamente.")
        return
    shared = Path(CONFIG.get("SHARED_PROJECT_ROOT") or "")
    if CLOUD_MODE:
        shared.mkdir(parents=True, exist_ok=True)  # copia local da pasta (a tela baixa os dados na primeira abertura)
    elif CONFIG.get("SHARED_PROJECT_ROOT") and not wait_for_drive(shared):
        message("A pasta do NexxusDoc no Google Drive não está disponível neste computador.\n\n"
                "Abra o Google Drive para computador, confira se ele está conectado com a sua conta do Grupo SBF e "
                "sincronizando, e abra o NexxusDoc de novo.\n\n"
                "Se este computador não tiver mais o Google Drive para computador, execute o instalador do NexxusDoc "
                "de novo: ele passa a usar o Drive pela nuvem.")
        return
    try:
        auto_update()
    except Exception as exc:  # atualizacao nunca impede a abertura
        print(f"Atualizacao automatica ignorada: {exc!r}", flush=True)

    import uvicorn

    sys.path.insert(0, str(ROOT))
    from app import app

    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT, access_log=False, log_level="info"))

    def open_when_ready() -> None:
        if not wait_and_open(browser=not RESTART):
            message(f"O NexxusDoc não iniciou. Consulte o log em:\n{LOG_DIR / 'nexus.log'}")

    def restart() -> None:
        relaunch()
        server.should_exit = True

    app.state.reiniciar = restart

    def stop_when_idle() -> None:
        while not server.should_exit:
            time.sleep(30)
            if time.monotonic() - app.state.last_activity > IDLE_SECONDS:
                print("Encerrando por inatividade.", flush=True)
                server.should_exit = True

    threading.Thread(target=open_when_ready, daemon=True).start()
    threading.Thread(target=stop_when_idle, daemon=True).start()
    server.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pythonw nao mostra traceback; registra e avisa o usuario.
        import traceback
        traceback.print_exc()
        message(f"Falha ao iniciar o NexxusDoc: {exc}\n\nDetalhes em:\n{LOG_DIR / 'nexus.log'}")
