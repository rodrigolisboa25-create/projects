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
from .gr_collection import collection_status
from .inventory import INVENTORY_COLUMNS, HIDDEN_UI_COLUMNS, ensure_inventory_schema
from .conference import latest_run as conference_latest_run
from .conference import short_facts as conference_facts
from .master_base import master_base_status
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
        _indicator("network", "VPN / rede", network_level, network_status, "Túnel VPN e acesso à rede corporativa (necessária só para o Optimus; as extrações SAP não dependem da VPN)", network_detail, "Conecte a VPN corporativa e valide o acesso à intranet. Se a VPN estiver conectada e ainda não for detectada, informe ao suporte o nome do cliente ou adaptador para parametrização."),
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


def _conference_summary(run: dict[str, Any], facts: dict[str, Any]) -> str:
    """Uma linha para o controle automático: arquivo, quando, linhas e valor total (os % ficam no selo)."""
    rows = (facts.get("rows") or {}).get("comparadas") or 0
    totals = facts.get("totals") or {}
    when = str(run.get("finished_at") or run.get("created_at") or "")[:16].replace("T", " ")
    difference = float(totals.get("diferenca") or 0)
    value = ("valor total igual" if abs(difference) < 0.01 else
             f"diferença no valor total de R$ {difference:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))
    rows_text = f"{int(rows):,}".replace(",", ".")
    return f"{facts.get('file_name')} · {when} · {rows_text} linhas comparadas · {value}. Detalhes no card Agente de conferência, abaixo."


def _next_period(period: str) -> str:
    year, month = map(int, period.split("-"))
    return f"{year + month // 12}-{month % 12 + 1:02d}"


def _collection_control(settings: Any, period: str, has_mb59: bool) -> dict[str, Any]:
    """Controle da coleção dos pedidos (Base GR / SQVI DOC_COMPRA): carga e cobertura dos pedidos da MB59 do mês."""
    title = "Season e Year dos pedidos (Base GR / SQVI)"
    where = "Extrações SAP > etapa 3 \"Season e Year\""
    status = collection_status(settings, period)
    coverage = status["coverage"]
    if not has_mb59:
        return {"title": title, "level": "warning", "badge": "Sem MB59",
                "detail": f"A MB59 do mês ainda não foi carregada; depois dela, carregue a Base GR ou o export da SQVI em {where}."}
    if not status["mb59_ready"]:
        return {"title": title, "level": "warning", "badge": "Regra anterior",
                "detail": "Competência carregada antes da regra por SKU: o PASSO A PASSO segue a MB59 por CE & MAT. "
                          f"Ao carregar a Base GR ou o export da SQVI em {where}, a MB59 já salva é reprocessada sozinha."}
    orders = f"{coverage['mb59_orders']:,}".replace(",", ".")
    if not status["imported"]:
        return {"title": title, "level": "warning", "badge": "Não carregada",
                "detail": f"A MB59 do mês tem {orders} pedidos (sem intercompany) e ainda não há coleção carregada: o passo 1 traz só a "
                          "Product Offer End Dt, e Season e Year seguem para o mês anterior e o All Brazil. "
                          f"Carregue em {where}."}
    try:
        loaded_at = datetime.fromisoformat(status["imported_at"]).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        loaded_at = status["imported_at"][:16]
    pct = coverage["pct"]
    missing = coverage["without_collection"]
    covered = f"{coverage['with_collection']:,}".replace(",", ".")
    detail = (f"{status['source_label']} ({status['file_name']}) carregada em {loaded_at}"
              f"{' por ' + status['imported_by'] if status.get('imported_by') else ''}: "
              f"{covered} de {orders} pedidos da MB59 com coleção.")
    if missing:
        sample = ", ".join(coverage["missing_sample"][:5])
        detail += (f" {missing} sem coleção (os SKUs desses pedidos seguem para o mês anterior e o All Brazil), "
                   f"por exemplo {sample}.")
    return {"title": title, "level": "healthy" if not missing else "warning",
            "badge": f"{str(pct).replace('.', ',')}% dos pedidos" if pct is not None else "Carregada", "detail": detail}


def governance_status(settings: Any, period: str) -> dict[str, Any]:
    with connect(settings.path("database")) as connection:
        sources = _period_source_status(connection, period)
        try:
            mapping_rules = int(connection.execute("select count(*) from mapping_rules").fetchone()[0])
        except Exception:  # noqa: BLE001 - tabela ainda não criada
            mapping_rules = 0

    schema_document =yaml.safe_load((settings.root / "config" / "schemas.yaml").read_text(encoding="utf-8")) or {}
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

    collection = collection_status(settings, period)
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
        _collection_control(settings, period, bool(sources.get("mb59"))),
        {
            "title": "Competência e data-base",
            "level": "healthy" if date_ok else "warning",
            "badge": "Válida" if date_ok else "Não verificada",
            "detail": f"Snapshot {snapshot_date or 'ausente'}; deve ser do mês e não posterior a {as_of.isoformat()}.",
        },
    ]
    # Ponto de atenção: posição oficial carregada só como base mestre (não é competência nem aparece nos relatórios).
    for master in master_base_status(settings):
        try:
            loaded_at = datetime.fromisoformat(master["imported_at"]).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            loaded_at = master["imported_at"][:16]
        brl = f"{master['fiscal_total']:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        rows_text = f"{master['rows']:,}".replace(",", ".")
        controls.insert(0, {
            "title": f"Ponto de atenção: base mestre de {master['period']}",
            "level": "warning",
            "wide": True,  # ocupa a linha inteira do quadro de controles
            "badge": "Em uso" if master["in_use"] else "Substituída",
            "detail": (
                f"A Posição de Estoque oficial de {master['period']} ({master['file_name']}, aba {master['source_sheet']}, "
                f"{rows_text} linhas, Vlr Tot Fisc R$ {brl}) foi carregada em {loaded_at}"
                f"{' por ' + master['imported_by'] if master['imported_by'] else ''} como base mestre. "
                "Ela não é uma competência e não aparece na Base de estoque nem nos relatórios: serve só como "
                f"posição do mês anterior no PASSO A PASSO de {_next_period(master['period'])} "
                "(Season e Product Offer End Dt por CE & MAT, Year pelo Material; origem \"Mês anterior · base mestre\")."
                + ("" if master["in_use"] else
                   f" Uma carga posterior da posição de {master['period']} no sistema já a substituiu.")
            ),
        })
    # Conferência com o fechamento manual (agente de conferência): o último resultado da competência.
    try:
        run = conference_latest_run(settings, period)
    except Exception:  # noqa: BLE001 - tabela ainda não criada nesta máquina
        run = None
    if run and run.get("status") == "COMPLETED" and run.get("summary"):
        facts = conference_facts(run)
        fields = facts.get("fields") or {}
        worst = min((item["iguais_pct"] for item in fields.values()), default=100.0)
        controls.append({
            "title": "Conferência com o fechamento manual",
            "level": "healthy" if worst >= 99.5 else "warning",
            "wide": True,
            "badge": " · ".join(f"{item['label']} {item['iguais_pct']:.1f}%".replace(".", ",") for item in fields.values()),
            # Resumo de uma linha; a explicação completa fica no card "Agente de conferência" e no chat do Optimus.
            "detail": _conference_summary(run, facts),
        })
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
        # Como cada base se liga à Posição de Estoque: exatamente os campos usados nos joins
        # (inventory.import_zmm119_xlsx, sources.all_brazil, mb59.enrich_inventory_pass_step e mappings.apply_mapping_rules).
        "structures": [
            {"title": "Posição de Estoque (ZMM119)", "detail": "Base da competência: as outras bases se ligam a ela pelas chaves abaixo.",
             "badge": f"{visible_inventory} colunas", "steps": [
                 "Origem: ZMM119 do SAP lida pela posição das colunas A:R — Empresa, Centro, Material, Texto breve material, UM básica, NCM, "
                 "Utilização livre, Bloqueado, Custo Médio Empresa, Custo Fiscal, Total, Vlr ICMS ST, Vlr IPI, Tipo, Vlr Tot Emp, Vlr Tot Fisc, "
                 "Custo Médio Comercial e Vlr Total CC.",
                 "Filtro: só as linhas da Empresa 7170.",
                 "Chaves criadas para os joins: CE & MAT = Centro + Material (por exemplo, 1081 + 397690-018-10.5 = 1081397690-018-10.5); "
                 "Estilo-Cor = 10 primeiros caracteres do Material (397690-018); Estilo = 6 primeiros.",
             ]},
            {"title": "All Brazil → Division, Origem e Lifecycle", "detail": f"Aba Data do cadastro mestre · {ab_columns} colunas reconhecidas por nome.",
             "badge": f"{float(ab[4] or 0):.1f}% cobertura".replace(".", ",") if ab else "Sem carga", "level": "healthy" if ab else "warning", "steps": [
                 "Arquivo: o ALL_BRAZIL_DD_MM mais recente da pasta do mês, com data menor ou igual à data-base (nunca um arquivo anterior do mesmo mês).",
                 "Chave 1: Material da Base de Estoque (maiúsculas, sem espaços) = Material Nbr do All Brazil.",
                 "Chave 2, só se o Material completo não existir no All Brazil: Estilo-Cor (10 primeiros caracteres do Material) = Material Nbr.",
                 "Centro: nunca participa da chave.",
                 "Campos trazidos: Division Description → Division Description; Material Origin Des. → Material Origin Des.; "
                 "Lifecycle Descrip. → Lifecycle Descrip.; Lifecycle (depois substituído pela regra do Mapping).",
                 "Conflito: Material Nbr repetido com valores diferentes deixa vazio só o campo divergente (ver Consistência All Brazil).",
             ]},
            {"title": "MB59 (PASSO A PASSO) → Season, Year e Product Offer End Dt", "detail": f"Aba BASE da MB59_BASE GR · {mb59_columns} colunas reconhecidas por nome.",
             "badge": "Material · pedido", "level": "healthy" if sources.get("mb59") else "warning", "steps": [
                 "1º Base GR do mês (MB59) pelo Material completo, todos os centros: Product Offer End Dt = Data de lançamento; "
                 "Season e Year = coleção do pedido de compra da entrada (Código coleção e Ano coleção da SQVI DOC_COMPRA, "
                 "carregados em Extrações SAP pela Base GR ou pelo export da SQVI).",
                 "2º Base de Estoque do mês anterior (ou a base mestre daquele mês, quando houver uma mais nova que a carga do "
                 "sistema) → 3º All Brazil pelo Material (ou Estilo-Cor), sem Centro: Collection Code → Season, Collection Year → "
                 "Year, Product Offer End Dt → Product Offer End Dt → 4º preenchimento manual na Base de estoque.",
                 "Regra vigente (padrão validado com o fechamento de 09/2026; ajustável só por aprovação de administrador no Agente "
                 "de conferência): Product Offer End Dt e Season — 1º Base GR do mês pelo Material completo (primeira entrada do "
                 "Material na ordem do arquivo; Season da primeira entrada cujo pedido tem coleção) → 2º mês anterior pelo CE & MAT → "
                 "3º All Brazil. Year — 1º coleção do pedido de importação (48…) da primeira entrada do Material → 2º mês anterior "
                 "pelo Material (qualquer centro) → 3º All Brazil. Anos anteriores a 2022 ficam \"<2022\".",
                 "Sem valor nas três fontes: o campo fica vazio e a linha aparece em \"Somente pendências de joins\" na Base de estoque.",
             ]},
            {"title": "Base GR / SQVI DOC_COMPRA → Season e Year dos pedidos",
             "detail": "Arquivo .xlsx da etapa 3 de Extrações SAP, lido pelos nomes das colunas: qualquer aba (a BASE é lida primeiro), "
                       "cabeçalho nas 15 primeiras linhas; ordem, maiúsculas e acentos não importam; colunas a mais são ignoradas.",
             "badge": "Carregada" if collection["imported"] else "Pendente", "level": "healthy" if collection["imported"] else "warning",
             "steps": [
                 "Formato 1, Base GR (uma linha por entrada): obrigatórias Material, Pedido, Season (FA, HO, SP ou SU) e Year (4 dígitos); "
                 "recomendadas Fornecedor (descarta intercompany 7008002 e 7008004) e Data de lançamento (confere a competência).",
                 "Formato 2, export da SQVI DOC_COMPRA (uma linha por pedido): obrigatórias Doc.compra (ou Nº do documento de compras), "
                 "Código coleção e Ano coleção; Empr opcional (só a 7170 é usada). É o formato mais enxuto: basta uma aba com essas 3 colunas. "
                 "Uma planilha só com Pedido, Season e Year não é reconhecida (use os nomes da SQVI).",
                 "Recusado, sem alterar nada: Season buscada pelo SKU na aba PE (e não pelo pedido), Season/Year com #N/D ou fórmula não "
                 "calculada, lançamentos de outra competência ou nenhum pedido válido. A mensagem diz o motivo.",
                 "Chave: Pedido do arquivo = pedido de compra das entradas da MB59 do mês (por Material); uma coleção por pedido (coleções diferentes: vale a mais frequente e o conflito é informado). Pedidos da MB59 sem "
                 "coleção no arquivo seguem para a Base de Estoque do mês anterior e o All Brazil.",
             ]},
            {"title": "Mapping → Local, STATUS OPERAÇÃO, Lifecycle e AGING", "detail": "Regras editáveis da página Mapping, compartilhadas entre as máquinas.",
             "badge": f"{mapping_rules} regras", "steps": [
                 "Planta e local: Centro da Base = Planta → Local (coluna Local atual).",
                 "Status da operação: Centro = Planta → STATUS OPERAÇÃO.",
                 "Lifecycle: Lifecycle Descrip. = Lifecycle Descrip. da regra (sem diferenciar maiúsculas) → Lifecycle.",
                 "Faixas de aging: Days = data-base − Product Offer End Dt; AGING = faixa com o maior \"Dias iniciais\" menor ou igual a Days; "
                 "Days negativo → 0) Futures.",
             ]},
            {"title": "Campos calculados (sem join)", "detail": "Fórmulas aplicadas depois dos joins, linha a linha.", "badge": "Fórmulas", "steps": [
                 "Season/Coleção: Season + Year (por exemplo, FA2026; com Year \"<2022\", FA<2022).",
                 "Tudo que for antes de 2022 deixar <2022: o próprio Year, ou <2022 quando o Year é menor que 2022. O texto \"<2022\" "
                 "da posição oficial é mantido como Year (aparece \"<2022\" na grade, na exportação e no filtro Year da Visão).",
                 "CE UNIT e Custo Fiscal UNIT.: Vlr Tot Emp ÷ Utilização livre e Vlr Tot Fisc ÷ Utilização livre.",
                 "FOB, II e Outros Custos: 50%, 35% e 15% do Vlr Tot Fisc.",
             ]},
        ],
        "operational": [
            {"title": "Extração SAP", "detail": "Execução exclusiva de administradores; relatórios compilados permanecem disponíveis aos usuários.", "badge": "Controlada", "level": "healthy"},
            {"title": "Regras de dados", "detail": "Empresa 7170, rastreabilidade e contratos das fontes aplicados no processamento.", "badge": "Ativas", "level": "healthy" if sources.get("inventory") else "warning"},
            {"title": "Optimus", "detail": "Acesso contextual depende da permissão Optimus e do endpoint n8n.", "badge": "Configurado", "level": "healthy"},
        ],
    }
