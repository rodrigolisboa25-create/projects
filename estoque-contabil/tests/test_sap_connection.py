from pathlib import Path
from types import SimpleNamespace
import time
import zipfile

import pytest

from ops_contabil.extractors.sap_gui import (
    SapGuiError,
    SapGuiRobot,
    load_sap_connection_names,
    resolve_sap_connection_name,
)


def test_reads_only_sapgui_entries_from_landscape(tmp_path: Path) -> None:
    landscape = tmp_path / "SAPUILandscape.xml"
    landscape.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
        <Landscape>
          <Services>
            <Service name="S/4HANA - PRD (SSO)" type="SAPGUI" />
            <Service name="Portal web" type="HTTP" />
            <Service description="ERP Produção" type="SAPGUI" />
          </Services>
        </Landscape>
        """,
        encoding="utf-8",
    )

    assert load_sap_connection_names([landscape]) == [
        "S/4HANA - PRD (SSO)",
        "ERP Produção",
    ]


def test_selects_unique_production_sso_connection() -> None:
    names = [
        "S/4HANA - QAS",
        "ERP - ECC PRD",
        "S/4HANA - PRD",
        "S/4HANA - PRD (SSO)",
    ]

    assert resolve_sap_connection_name(connection_names=names) == "S/4HANA - PRD (SSO)"


def test_user_override_accepts_unique_partial_name() -> None:
    names = ["ERP - ECC PRD", "S/4HANA - PRD (SSO)"]

    assert resolve_sap_connection_name("PRD (SSO)", names) == "S/4HANA - PRD (SSO)"


def test_ambiguous_unclassified_connections_require_override() -> None:
    with pytest.raises(SapGuiError, match="Informe a conexão desejada"):
        resolve_sap_connection_name(connection_names=["Financeiro", "Materiais"])


def test_save_dialog_presses_generate_instead_of_enter(tmp_path: Path) -> None:
    class Button:
        pressed = False

        def press(self) -> None:
            self.pressed = True

    path_control = SimpleNamespace(text="C:\\TEMP")
    file_control = SimpleNamespace(text="EXPORT.XLSX")
    button = Button()
    window = SimpleNamespace()
    robot = SapGuiRobot()
    robot._try_find = lambda control_id: {
        "wnd[1]": window,
        "wnd[1]/tbar[0]/btn[0]": button,
    }.get(control_id)
    robot._find_by_technical_name = lambda _root, name, _types: {
        "DY_PATH": path_control,
        "DY_FILENAME": file_control,
    }.get(name)

    output = tmp_path / "ZMM119_2026-09.xlsx"
    assert robot._save_dialog(output) is True
    assert path_control.text == str(tmp_path)
    assert file_control.text == output.name
    assert button.pressed is True
    assert any(path.name == "EXPORT.XLSX" for path in robot._observed_export_paths)
    assert output in robot._observed_export_paths


def test_adopts_valid_export_from_path_observed_in_sap_dialog(tmp_path: Path) -> None:
    sap_folder = tmp_path / "sap-temp"
    sap_folder.mkdir()
    exported = sap_folder / "EXPORT_20260925_122507.XLSX"
    with zipfile.ZipFile(exported, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("xl/workbook.xml", "<workbook />")

    official = tmp_path / "official" / "ZMM119_2026-09.xlsx"
    robot = SapGuiRobot()
    robot._observed_export_paths.append(exported)

    assert robot._adopt_recent_export(official, time.time() - 2) is True
    assert official.is_file()
    assert SapGuiRobot._is_valid_recent_xlsx(official, time.time() - 3)


def _write_valid_xlsx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("xl/workbook.xml", "<workbook />")


def _offline_robot(timeout_seconds: int, exported: Path) -> SapGuiRobot:
    robot = SapGuiRobot(timeout_seconds=timeout_seconds)
    robot._observed_export_paths.append(exported)
    robot._native_dialog_visible = lambda _titles: True  # nunca consulta a barra de status via COM
    robot._sap_status_bar_text = lambda: ""
    robot._sap_reported_export_paths = lambda: []
    return robot


def test_partial_export_is_never_copied_while_sap_is_writing(tmp_path: Path, monkeypatch) -> None:
    import ops_contabil.extractors.sap_gui as sap_gui

    exported = tmp_path / "EXPORT_20260929_110132.XLSX"
    exported.write_bytes(b"PK\x03\x04" + b"\x00" * 200_000)  # ZIP ainda sem diretório central
    official = tmp_path / "official" / "ZMM119_2026-09.xlsx"
    copies: list[Path] = []
    real_copy = sap_gui.shutil.copy2
    monkeypatch.setattr(sap_gui.shutil, "copy2", lambda src, dst: copies.append(Path(src)) or real_copy(src, dst))
    robot = SapGuiRobot()
    robot._observed_export_paths.append(exported)

    assert robot._adopt_recent_export(official, time.time() - 2) is False
    assert copies == []
    assert not official.exists()

    _write_valid_xlsx(exported)
    assert robot._adopt_recent_export(official, time.time() - 2) is True
    assert copies == [exported]


def test_wait_keeps_going_while_sap_is_still_transferring(tmp_path: Path) -> None:
    import threading

    exported = tmp_path / "EXPORT_20260929_110132.XLSX"
    exported.write_bytes(b"PK\x03\x04")
    official = tmp_path / "official" / "ZMM119_2026-09.xlsx"
    robot = _offline_robot(1, exported)

    def slow_sap_download() -> None:
        for _ in range(8):  # ~3,2 s de transferência, bem acima do prazo de 1 s sem progresso
            time.sleep(0.4)
            with exported.open("ab") as handle:
                handle.write(b"\x00" * 50_000)
        _write_valid_xlsx(exported)

    writer = threading.Thread(target=slow_sap_download)
    started = time.monotonic()
    writer.start()
    try:
        assert robot._wait_file_stable(official, time.time() - 5) == official
    finally:
        writer.join()
    assert time.monotonic() - started > 3
    assert SapGuiRobot._is_valid_xlsx_archive(official)


def test_wait_still_fails_when_sap_stops_making_progress(tmp_path: Path) -> None:
    exported = tmp_path / "EXPORT_20260929_110132.XLSX"
    exported.write_bytes(b"PK\x03\x04" + b"\x00" * 1000)
    official = tmp_path / "official" / "ZMM119_2026-09.xlsx"
    robot = _offline_robot(1, exported)

    started = time.monotonic()
    with pytest.raises(SapGuiError, match="sem progresso"):
        robot._wait_file_stable(official, time.time() - 5)
    assert time.monotonic() - started < 10


def test_parallel_robots_never_claim_the_same_sap_session() -> None:
    class Children:
        def __init__(self, values):
            self.values = values
            self.Count = len(values)

        def __call__(self, index: int):
            return self.values[index]

    class Session:
        Id = "ses[0]"
        Busy = False
        Info = SimpleNamespace(SystemName="S4P")

        @staticmethod
        def findById(control_id: str):
            return object() if control_id == "wnd[0]/tbar[0]/okcd" else None

    session = Session()
    connection = SimpleNamespace(
        Id="con[0]",
        Description="S/4HANA - PRD (SSO)",
        Name="S4P",
        Children=Children([session]),
    )
    engine = SimpleNamespace(Children=Children([connection]))
    first = SapGuiRobot()
    second = SapGuiRobot()
    first.engine = engine
    second.engine = engine

    try:
        assert first._claim_ready_session() == (connection, session)
        assert second._claim_ready_session() is None
        first._release_session_reservation()
        assert second._claim_ready_session() == (connection, session)
    finally:
        first._release_session_reservation()
        second._release_session_reservation()
