from __future__ import annotations

import os
import re
import socket
import subprocess
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml

from .db import connect
from .inventory import INVENTORY_COLUMNS, HIDDEN_UI_COLUMNS, ensure_inventory_schema
from .mb59 import ensure_mb59_schema
from .sources.all_brazil import MONTH_NAMES, resolve_all_brazil_root


SUPPORT_EMAIL = "transformacao_digital@gruposbf.com.br"


def _indicator(
    key: str,
    title: str,
    level: str,
    status: str,
    summary: str,
    details: str,
    fix: str,
) -> dict[str, str]:
    return {
        "key": key,
        "title": title,
        "level": level,
        "status": status,
        "summary": summary,
        "details": details,
        "fix": fix,
        "support_email": SUPPORT_EMAIL,
    }


def _sap_executable() -> Path | None:
    roots = [os.getenv("PROGRAMFILES"), os.getenv("PROGRAMFILES(X86)"), os.getenv("PROGRAMW6432")]
    candidates = [
        Path(root) / "SAP" / "FrontEnd" / "SAPgui" / "saplogon.exe"
        for root in roots
        if root
    ]
    return next((path for path in candidates if path.is_file()), None)


def _network_probe(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return False, "URL corporativa não configurada."
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        with socket.create_connection((host, port), timeout=3):
            pass
        return True, f"DNS e conexão TCP disponíveis para {host}:{port} ({len(addresses)} rota(s))."
    except OSError as exc:
        return False, f"Não foi possível alcançar {host}:{port}: {exc}"


def _active_vpn_adapters_from_ipconfig(output: str, pattern: re.Pattern[str]) -> list[str]:
    names: list[str] = []
    # Cada cabeçalho de adaptador começa sem recuo e termina em dois-pontos.
    # O ipconfig inclui uma linha vazia logo depois dele, portanto separar por
    # parágrafos faria o nome se perder do restante das propriedades.
    for block in re.split(r"(?m)(?=^[^\s\r\n].*:\s*$)", output):
        if not pattern.search(block):
            continue
        # Adaptadores desconectados não possuem endereço IP no bloco do ipconfig.
        if not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", block):
            continue
        heading = next((line.strip().rstrip(":") for line in block.splitlines() if line.strip()), "VPN")
        names.append(heading)
    return sorted(set(names))


def _vpn_probe(url: str) -> tuple[str, str, str]:
    """Detecta um túnel VPN ativo; nunca infere VPN apenas por acesso à internet."""
    if os.name != "nt":
        return (
            "warning",
            "Não verificada",
            "A detecção automática de VPN está disponível somente no Windows.",
        )

    default_pattern = (
        r"vpn|anyconnect|secure mobility|globalprotect|fortinet|forticlient|"
        r"palo alto|pangp|pulse secure|zscaler|netskope|wireguard|openvpn|juniper|"
        r"check point|sonicwall"
    )
    pattern = re.compile(os.getenv("OPS_VPN_ADAPTER_PATTERN", default_pattern), re.IGNORECASE)
    try:
        completed = subprocess.run(
            ["ipconfig.exe", "/all"],
            capture_output=True,
            text=False,
            timeout=6,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        output = completed.stdout.decode("mbcs", errors="replace")
        error_output = completed.stderr.decode("mbcs", errors="replace")
        if completed.returncode != 0 or not output.strip():
            detail = error_output.strip() or "O Windows não retornou o estado dos adaptadores."
            return "warning", "Não verificada", detail
    except (OSError, subprocess.TimeoutExpired, LookupError) as exc:
        return "warning", "Não verificada", f"Falha ao consultar a VPN no Windows: {exc}"

    names = _active_vpn_adapters_from_ipconfig(output, pattern)
    if not names:
        return (
            "critical",
            "Não detectada",
            "Nenhuma conexão VPN ativa ou adaptador corporativo conectado foi detectado no Windows.",
        )

    reachable, network_detail = _network_probe(url)
    detected = ", ".join(names)
    if reachable:
        return "healthy", "Conectada", f"VPN detectada ({detected}). {network_detail}"
    return (
        "warning",
        "VPN detectada; rede indisponível",
        f"VPN detectada ({detected}), mas o endpoint corporativo não respondeu. {network_detail}",
    )


def _n8n_probe(url: str) -> tuple[bool, str]:
    if not url:
        return False, "N8N_CHAT_URL não configurada."
    try:
        response = httpx.options(url, timeout=5.0, follow_redirects=True)
    except httpx.TimeoutException:
        return False, "O endpoint do Optimus excedeu 5 segundos."
    except httpx.RequestError as exc:
        return False, f"Falha de conexão com o endpoint do Optimus: {exc.__class__.__name__}."
    if 200 <= response.status_code < 400:
        return True, f"Endpoint acessível; resposta HTTP {response.status_code}."
    if response.status_code in {401, 403}:
        return False, f"O endpoint recusou o acesso (HTTP {response.status_code}). A VPN, a rota corporativa ou a publicação do webhook pode estar indisponível."
    if response.status_code == 404:
        return False, "O webhook respondeu HTTP 404; confirme se o workflow está ativo e publicado."
    return False, f"O endpoint respondeu HTTP {response.status_code}; o Optimus não foi considerado online."


def _period_source_status(connection: Any, period: str) -> dict[str, Any]:
    ensure_inventory_schema(connection)
    ensure_mb59_schema(connection)
    connection.execute(
        """create table if not exists all_brazil_imports (
            period varchar primary key, snapshot_date date, source_path varchar, source_sha256 varchar,
            inventory_keys bigint, matched_keys bigint, coverage_pct double, duplicate_keys bigint,
            conflict_keys bigint, schema_fingerprint varchar, imported_at timestamp default current_timestamp
        )"""
    )
    inventory = connection.execute(
        "select row_count, source_path, source_sheet, schema_fingerprint, imported_at from inventory_imports where period=?",
        [period],
    ).fetchone()
    mb59 = connection.execute(
        "select source_rows, lookup_rows, source_path, source_sheet, schema_fingerprint, imported_at from mb59_imports where period=?",
        [period],
    ).fetchone()
    all_brazil = connection.execute(
        """select snapshot_date, source_path, inventory_keys, matched_keys, coverage_pct,
                  duplicate_keys, conflict_keys, schema_fingerprint, imported_at
             from all_brazil_imports where period=?""",
        [period],
    ).fetchone()
    rows = connection.execute("select count(*) from inventory_rows where period=?", [period]).fetchone()[0]
    return {"inventory": inventory, "mb59": mb59, "all_brazil": all_brazil, "rows": int(rows or 0)}


def _format_stamp(value: object) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return "nunca"


def _bridge_indicators(settings: Any, user: dict[str, Any], backup: dict[str, Any] | None) -> list[dict[str, str]]:
    """Semáforos da ponte de dados pelo Drive compartilhado e do backup programado."""
    from .backup import FREQUENCY_DAYS
    from .drive_bridge import bridge_status, validate_folder

    indicators: list[dict[str, str]] = []
    is_admin = str(user.get("role") or "user") == "admin"
    try:
        status = bridge_status(settings)
    except Exception as exc:  # noqa: BLE001 - o diagnóstico nunca derruba o Health Center
        indicators.append(_indicator("bridge_folder", "Drive compartilhado", "critical", "Falha no diagnóstico", "Pasta Estoque_Cont da ponte de dados", str(exc), "Reinicie o sistema; se persistir, envie esta mensagem ao suporte."))
        return indicators

    root = status["root"]
    fix_folder = (
        "Abra o Google Drive para computador, confirme o acesso ao drive compartilhado Estoque_Cont e aguarde a "
        "sincronização. Um administrador pode indicar outra pasta em Configurações > Ponte de dados (contingência)."
    )
    if not root.get("available"):
        indicators.append(_indicator(
            "bridge_folder", "Drive compartilhado", "critical", "Inacessível", "Pasta Estoque_Cont da ponte de dados",
            f"A pasta da ponte não foi encontrada nesta máquina ({root.get('path') or 'nenhum Drive com Estoque_Cont'}). "
            "Os relatórios locais continuam funcionando, mas esta máquina não envia nem recebe atualizações.",
            fix_folder,
        ))
    else:
        try:
            validate_folder(Path(str(root["path"])))
            writable = True
        except ValueError:
            writable = False
        origin = {"configured": "configurada manualmente", "environment": "definida por OPS_BRIDGE_ROOT", "detected": "detectada automaticamente"}.get(str(root.get("source")), str(root.get("source")))
        if writable:
            level, state, detail = "healthy", "Conectado", f"{root['path']} ({origin}); leitura e gravação confirmadas."
        elif is_admin:
            level, state, detail = "warning", "Somente leitura", f"{root['path']} ({origin}) aceita leitura, mas não gravação: esta máquina recebe atualizações, porém não consegue enviar as cargas feitas aqui."
        else:
            level, state, detail = "healthy", "Conectado (leitura)", f"{root['path']} ({origin}); leitura confirmada, suficiente para receber as atualizações."
        indicators.append(_indicator("bridge_folder", "Drive compartilhado", level, state, "Pasta Estoque_Cont da ponte de dados", detail, fix_folder))

    # O status reflete a causa mais grave encontrada; nada é presumido a partir do último sucesso.
    problems: list[str] = []
    level, label = "healthy", "Em dia"

    def flag(new_level: str, new_label: str, problem: str) -> None:
        nonlocal level, label
        problems.append(problem)
        rank = {"healthy": 0, "warning": 1, "critical": 2}
        if rank[new_level] > rank[level]:
            level, label = new_level, new_label

    if not root.get("available"):
        flag("critical", "Suspensa (sem Drive)", "sem acesso à pasta do Drive: envio e recebimento estão suspensos nesta máquina")
    if status.get("pending_publish"):
        flag(
            "critical" if status.get("last_publish_error") else "warning",
            "Envio pendente",
            f"aguardando envio ao Drive: {', '.join(status['pending_publish'])}",
        )
    if status.get("last_publish_error"):
        flag("warning", "Erro no envio", f"último erro de envio: {status['last_publish_error']}")
    waiting = (status.get("last_sync_result") or {}).get("waiting") or []
    if waiting:
        flag("warning", "Aguardando o Drive", "aguardando o Google Drive terminar de baixar: " + ", ".join(str(item.get("period")) for item in waiting))
    if status.get("last_sync_error"):
        flag("warning", "Erro no recebimento", f"último erro de recebimento: {status['last_sync_error']}")
    last_sync = status.get("last_sync_at")
    try:
        stale = last_sync is None or datetime.now() - datetime.fromisoformat(str(last_sync)) > timedelta(minutes=15)
    except ValueError:
        stale = True
    if root.get("available") and stale:
        flag("warning", "Sem verificação recente", "nenhuma verificação do Drive nos últimos 15 minutos")
    periods = status.get("periods") or []
    synced = sum(1 for item in periods if item.get("situation") == "Sincronizada")
    counts = f"{synced} de {len(periods)} competência(s) sincronizada(s)"
    detail = (
        f"{counts}. Último envio: {_format_stamp(status.get('last_publish_at'))}. Última verificação: {_format_stamp(last_sync)}."
        + (" Pontos de atenção: " + "; ".join(problems) + "." if problems else " Nenhuma pendência.")
    )
    indicators.append(_indicator(
        "bridge_sync", "Sincronização de competências", level, label,
        "Envio e recebimento das competências pelo Drive", detail,
        "Verifique o Google Drive para computador e use Configurações > Ponte de dados > Sincronizar agora. Envios pendentes são refeitos automaticamente quando o Drive volta.",
    ))

    if is_admin and backup is not None:
        fix_backup = "Em Configurações > Backup programado, ative a rotina, confira a pasta e use Fazer backup agora para validar."
        if not backup.get("enabled"):
            indicators.append(_indicator("backup", "Backup programado", "warning", "Desativado", "Cópia de segurança do banco local", f"O backup programado está desativado. Pasta prevista: {backup.get('effective_folder')}.", fix_backup))
        else:
            last = backup.get("last_backup_at")
            try:
                age = datetime.now() - datetime.fromisoformat(str(last)) if last else None
            except ValueError:
                age = None
            limit = timedelta(days=FREQUENCY_DAYS.get(str(backup.get("frequency")), 1), hours=12)
            if backup.get("last_backup_error"):
                b_level, b_state = "critical", "Falha no último backup"
            elif age is None or age > limit:
                b_level, b_state = "warning", "Atrasado"
            else:
                b_level, b_state = "healthy", "Em dia"
            b_detail = f"Último backup: {_format_stamp(last)} em {backup.get('effective_folder')}." + (f" Erro: {backup['last_backup_error']}" if backup.get("last_backup_error") else "")
            indicators.append(_indicator("backup", "Backup programado", b_level, b_state, "Cópia de segurança do banco local", b_detail, fix_backup))
    return indicators


def _access_indicator(settings: Any, user: dict[str, Any]) -> dict[str, str]:
    """Semáforo da lista central de acessos (Estoque_Cont/acesso), com o estado real desta máquina."""
    from .access_sync import _parse, access_status

    def stamp(value: Any) -> str:
        parsed = _parse(value)
        return parsed.astimezone().strftime("%d/%m/%Y %H:%M") if parsed else "nunca"

    fix = (
        "Confirme o Google Drive para computador (drive Estoque_Cont) e a VPN: a lista é verificada no login e a cada "
        "2 minutos. Administradores acompanham em Configurações > Acesso corporativo."
    )
    try:
        status = access_status(settings)
    except Exception as exc:  # noqa: BLE001 - o diagnóstico nunca derruba o Health Center
        return _indicator("access_sync", "Controle de acessos", "critical", "Falha no diagnóstico", "Lista central de acessos no Drive", str(exc), fix)
    is_admin = str(user.get("role") or "user") == "admin"
    problems: list[str] = []
    level, label = "healthy", "Em dia"
    severity = {"healthy": 0, "warning": 1, "critical": 2}

    def flag(new_level: str, new_label: str, problem: str) -> None:
        nonlocal level, label
        problems.append(problem)
        if severity[new_level] > severity[level]:
            level, label = new_level, new_label

    last_sync = _parse(status.get("last_sync_at"))
    if status.get("expired"):
        flag("critical", "Bloqueado (sem verificação)" if not is_admin else "Prazo expirado",
             "mais de 7 dias sem consultar a lista: usuários comuns estão bloqueados nesta máquina")
    elif last_sync is None:
        flag("warning", "Ainda não verificada", "esta máquina ainda não conseguiu consultar a lista central")
    elif datetime.now(last_sync.tzinfo) - last_sync > timedelta(minutes=15):
        flag("warning", "Sem verificação recente", "nenhuma consulta à lista nos últimos 15 minutos")
    if not status.get("expired") and int(status.get("days_left") or 0) <= 2 and last_sync is not None and datetime.now(last_sync.tzinfo) - last_sync > timedelta(days=4):
        flag("warning", "Prazo próximo", f"restam {status.get('days_left')} dia(s) para o bloqueio por falta de verificação")
    if status.get("last_error"):
        flag("warning", "Erro na sincronização", f"último erro: {status['last_error']}")
    if is_admin and status.get("pending_publish"):
        flag("warning", "Envio pendente", "alterações de acesso feitas nesta máquina aguardando envio ao Drive")
    machines = status.get("machines") or []
    detail = (
        f"Última verificação: {stamp(status.get('last_sync_at'))}. "
        f"{len(machines)} máquina(s) de administrador publicando a lista. "
        f"Prazo sem verificação: até {stamp(status.get('expires_at'))} ({status.get('grace_days')} dias)."
        + (" Pontos de atenção: " + "; ".join(problems) + "." if problems else " Nenhuma pendência.")
    )
    return _indicator("access_sync", "Controle de acessos", level, label, "Lista central de acessos no Drive (Estoque_Cont\\acesso)", detail, fix)


def connectivity_indicators(n8n_url: str) -> list[dict[str, str]]:
    """Só VPN/rede e n8n: verificação leve, usada também pelo vigia do Optimus a cada 2 minutos."""
    network_level, network_status, network_detail = _vpn_probe(n8n_url)
    n8n_ok, n8n_detail = _n8n_probe(n8n_url)
    return [
        _indicator("network", "VPN / rede", network_level, network_status, "Túnel VPN e acesso à rede corporativa", network_detail, "Conecte a VPN corporativa e valide o acesso à intranet. Se a VPN estiver conectada e ainda não for detectada, informe ao suporte o nome do cliente ou adaptador para parametrização."),
        _indicator("n8n", "n8n / Optimus", "healthy" if n8n_ok else "critical", "Online" if n8n_ok else "Indisponível", "Webhook do agente contábil", n8n_detail, "Verifique se o workflow Optimus está ativo e se N8N_CHAT_URL aponta para o webhook de produção."),
    ]


def system_health(
    settings: Any,
    period: str,
    user: dict[str, Any],
    n8n_url: str,
    sap_jobs: list[dict[str, Any]] | None = None,
    backup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    indicators: list[dict[str, str]] = []

    sap = _sap_executable()
    latest_job = (sap_jobs or [None])[0]
    if sap:
        level, status = "healthy", "Disponível"
        detail = f"SAP Logon localizado em {sap}."
        if latest_job and latest_job.get("status") in {"FAILED", "ACTION_REQUIRED"}:
            level, status = "warning", "Atenção na última execução"
            detail += f" Última execução: {latest_job.get('message') or latest_job.get('status')}."
    else:
        level, status, detail = "critical", "Não localizado", "SAP Logon não foi localizado nos diretórios padrão desta máquina."
    indicators.append(_indicator("sap", "SAP GUI", level, status, "Instalação local e última execução", detail, "Instale ou repare o SAP GUI e confirme que SAP GUI Scripting está habilitado."))

    indicators.extend(connectivity_indicators(n8n_url))

    try:
        drive = resolve_all_brazil_root(settings)
        drive_ok = drive.is_dir()
        drive_detail = f"Pasta localizada nesta máquina: {drive}" if drive_ok else "Pasta All Brazil não localizada."
    except Exception as exc:
        drive_ok, drive_detail = False, str(exc)
    indicators.append(_indicator("drive", "Google Drive", "healthy" if drive_ok else "warning", "Sincronizado" if drive_ok else "Não localizado", "Fonte mensal All Brazil", drive_detail, "Abra o Google Drive para computador e confirme que @All Brazil Materials está disponível. Relatórios já compilados continuam acessíveis."))

    slides_template = next(settings.root.glob("TEMPLATE*Apresenta*Executiva.gslides"), None)
    slides_ready = bool(slides_template and n8n_ok)
    slides_detail = (
        f"Atalho do template localizado ({slides_template.name}) e orquestrador acessível. A credencial Google é validada somente ao gerar a apresentação."
        if slides_ready
        else "Template local e/ou orquestrador de apresentações não estão disponíveis."
    )
    indicators.append(_indicator("slides", "Google Slides", "warning" if slides_ready else "critical", "Verificação parcial" if slides_ready else "Configuração incompleta", "Template, rota e limite da verificação", slides_detail, "Gere uma apresentação pelo Optimus para validar a credencial Google, o template e a pasta de destino de ponta a ponta."))

    try:
        with connect(settings.path("database")) as connection:
            probe = connection.execute("select 1").fetchone()[0]
            sources = _period_source_status(connection, period)
        db_ok = probe == 1
        db_detail = f"Banco acessível em {settings.path('database')}; {sources['rows']:,} linhas em {period}."
    except Exception as exc:
        db_ok, db_detail, sources = False, str(exc), {"inventory": None, "mb59": None, "all_brazil": None, "rows": 0}
    indicators.append(_indicator("duckdb", "DuckDB", "healthy" if db_ok else "critical", "Operacional" if db_ok else "Falha", "Banco local compilado", db_detail, "Feche outras instâncias, verifique espaço e permissão no perfil local e reinicie o sistema."))

    present = sum(bool(sources.get(key)) for key in ("inventory", "mb59", "all_brazil"))
    source_level = "healthy" if present == 3 and sources.get("rows", 0) else "warning" if sources.get("rows", 0) else "critical"
    source_status = "Completas" if source_level == "healthy" else "Parciais" if source_level == "warning" else "Ausentes"
    source_detail = (
        f"{period}: ZMM119={'ok' if sources.get('inventory') else 'ausente'}, "
        f"MB59={'ok' if sources.get('mb59') else 'ausente'}, All Brazil={'ok' if sources.get('all_brazil') else 'ausente'}."
    )
    indicators.append(_indicator("sources", "Fontes", source_level, source_status, "ZMM119, MB59 e All Brazil da competência", source_detail, "Para recompor a competência, importe primeiro MB59, depois ZMM119 e reprocese os joins."))

    role = str(user.get("role") or "user")
    pages = list(user.get("pages") or [])
    permission_ok = bool(user.get("email")) and role in {"admin", "user"}
    permission_detail = f"{user.get('email')} · perfil {role} · {('todas as páginas' if role == 'admin' else len(pages))}."
    indicators.append(_indicator("permissions", "Permissões", "healthy" if permission_ok else "critical", "Válidas" if permission_ok else "Inválidas", "Sessão, perfil e páginas liberadas", permission_detail, "Peça a um administrador para revisar o cadastro em Configurações > Acesso corporativo."))

    if (settings.raw.get("bridge") or {}).get("enabled"):
        indicators.extend(_bridge_indicators(settings, user, backup))
        indicators.append(_access_indicator(settings, user))

    weights = {"healthy": 1.0, "warning": 0.5, "critical": 0.0}
    score = round(sum(weights[item["level"]] for item in indicators) / len(indicators) * 100)
    overall = "healthy" if score == 100 else "warning" if score >= 60 else "critical"
    return {
        "period": period,
        "checked_at": datetime.now().astimezone().isoformat(),
        "score": score,
        "overall_level": overall,
        "summary": "Todos os componentes verificados estão operacionais." if score == 100 else "Há itens que exigem atenção; abra cada semáforo para ver o diagnóstico.",
        "indicators": indicators,
    }


def governance_status(settings: Any, period: str) -> dict[str, Any]:
    with connect(settings.path("database")) as connection:
        sources = _period_source_status(connection, period)

    schema_document = yaml.safe_load((settings.root / "config" / "schemas.yaml").read_text(encoding="utf-8")) or {}
    schemas = schema_document.get("schemas") or {}
    mb59_columns = len((schemas.get("mb59_base") or {}).get("columns") or {})
    ab_columns = len((schemas.get("all_brazil_data") or {}).get("columns") or {})
    visible_inventory = len([key for key, _ in INVENTORY_COLUMNS if key not in HIDDEN_UI_COLUMNS])

    ab = sources.get("all_brazil")
    duplicates = int(ab[5] or 0) if ab else 0
    conflicts = int(ab[6] or 0) if ab else 0
    if not ab:
        uniqueness = ("warning", "Não verificado", "Nenhuma importação All Brazil registrada para a competência.")
    elif conflicts:
        uniqueness = ("critical", f"{conflicts} conflitos", f"Há {duplicates} chaves repetidas e {conflicts} com divergência nos campos usados. Os campos conflitantes ficam vazios; a publicação não é bloqueada.")
    elif duplicates:
        uniqueness = ("warning", "Consistente", f"Há {duplicates} chaves repetidas, mas nenhuma divergência nos campos usados pelo enriquecimento.")
    else:
        uniqueness = ("healthy", "Única", "Nenhuma chave repetida ou conflitante foi detectada.")

    as_of = date(*map(int, period.split("-")), 1).replace(day=monthrange(*map(int, period.split("-")))[1])
    snapshot_date = ab[0] if ab else None
    date_ok = bool(snapshot_date and snapshot_date <= as_of)
    controls = [
        {
            "title": "Ordem e contrato de colunas",
            "level": "warning",
            "badge": "Modelo híbrido",
            "detail": "MB59 e All Brazil são reconhecidos por nomes normalizados e aliases. A ZMM119 usa contrato posicional fixo A:R e bloqueia a carga se o layout mudar.",
        },
        {
            "title": "Campos obrigatórios",
            "level": "healthy" if sources.get("inventory") and sources.get("mb59") else "warning",
            "badge": "Validado" if sources.get("inventory") and sources.get("mb59") else "Parcial",
            "detail": "Campos obrigatórios ausentes bloqueiam cada importação antes de alterar a competência.",
        },
        {"title": "Consistência All Brazil", "level": uniqueness[0], "badge": uniqueness[1], "detail": uniqueness[2]},
        {
            "title": "Competência e data-base",
            "level": "healthy" if date_ok else "warning",
            "badge": "Válida" if date_ok else "Não verificada",
            "detail": f"Snapshot {snapshot_date or 'ausente'}; deve ser do mês e não posterior a {as_of.isoformat()}.",
        },
    ]
    source = None
    if ab:
        stored_file_name = Path(str(ab[1])).name
        selected_path = f"@All Brazil Materials / {period[:4]} / {period[5:7]} / {stored_file_name}"
        try:
            current_root = resolve_all_brazil_root(settings)
            selected_path = str(
                current_root
                / period[:4]
                / f"{int(period[5:7]):02d}. {MONTH_NAMES[int(period[5:7])]}"
                / stored_file_name
            )
        except Exception:
            pass
        source = {
            "snapshot_date": str(ab[0]),
            "path": selected_path,
            "file_name": stored_file_name,
            "coverage_pct": float(ab[4] or 0),
            "duplicate_keys": duplicates,
            "conflict_keys": conflicts,
        }
    return {
        "period": period,
        "controls": controls,
        "source": source,
        "structures": [
            {"title": "Posição de Estoque", "detail": "Base compilada · ZMM119 A:R + campos derivados", "badge": f"{visible_inventory} visíveis"},
            {"title": "MB59_BASE GR", "detail": "BASE · resolução por nomes e aliases", "badge": f"{mb59_columns} campos"},
            {"title": "All Brazil", "detail": "Data · resolução por nomes e aliases", "badge": f"{ab_columns} campos"},
        ],
        "operational": [
            {"title": "Extração SAP", "detail": "Execução exclusiva de administradores; relatórios compilados permanecem disponíveis aos usuários.", "badge": "Controlada", "level": "healthy"},
            {"title": "Regras de dados", "detail": "Empresa 7170, rastreabilidade e contratos das fontes aplicados no processamento.", "badge": "Ativas", "level": "healthy" if sources.get("inventory") else "warning"},
            {"title": "Optimus", "detail": "Acesso contextual depende da permissão Optimus e do endpoint n8n.", "badge": "Configurado", "level": "healthy"},
        ],
    }
