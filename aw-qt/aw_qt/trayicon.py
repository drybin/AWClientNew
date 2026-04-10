import logging
import os
import signal
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aw_core
from PyQt6 import QtCore
from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QWidget,
)

from .manager import Manager, Module

logger = logging.getLogger(__name__)


def get_env() -> Dict[str, str]:
    """
    Necessary for xdg-open to work properly when PyInstaller overrides LD_LIBRARY_PATH

    https://github.com/ActivityWatch/activitywatch/issues/208#issuecomment-417346407
    """
    env = dict(os.environ)  # make a copy of the environment
    lp_key = "LD_LIBRARY_PATH"  # for GNU/Linux and *BSD.
    lp_orig = env.get(lp_key + "_ORIG")
    if lp_orig is not None:
        env[lp_key] = lp_orig  # restore the original, unmodified value
    else:
        # This happens when LD_LIBRARY_PATH was not set.
        # Remove the env var as a last resort:
        env.pop(lp_key, None)
    return env


def open_url(url: str) -> None:
    if sys.platform == "linux":
        env = get_env()
        subprocess.Popen(["xdg-open", url], env=env)
    else:
        webbrowser.open(url)


def open_webui(root_url: str) -> None:
    logger.debug("Open dashboard %s", root_url)
    open_url(root_url)


def open_apibrowser(root_url: str) -> None:
    logger.debug("Open API browser %s/api", root_url)
    open_url(root_url + "/api")


def open_dir(d: str) -> None:
    """From: http://stackoverflow.com/a/1795849/965332"""
    if sys.platform == "win32":
        os.startfile(d)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", d])
    else:
        env = get_env()
        subprocess.Popen(["xdg-open", d], env=env)


class TrayIcon(QSystemTrayIcon):
    def __init__(
        self,
        manager: Manager,
        icon: QIcon,
        parent: Optional[QWidget] = None,
        testing: bool = False,
    ) -> None:
        QSystemTrayIcon.__init__(self, icon, parent)
        self._parent = parent  # QSystemTrayIcon also tries to save parent info but it screws up the type info
        self.setToolTip("CtrlDesk" + (" (testing)" if testing else ""))

        self.manager = manager
        self.testing = testing

        self.root_url = f"http://localhost:{5666 if self.testing else 5600}"
        self.activated.connect(self.on_activated)

        self._build_rootmenu()

    def on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            open_webui(self.root_url)

    def _build_rootmenu(self) -> None:
        menu = QMenu(self._parent)

        if self.testing:
            menu.addAction("Running in testing mode")  # .setEnabled(False)
            menu.addSeparator()

        # openWebUIIcon = QIcon.fromTheme("open")
        menu.addAction("Open Dashboard", lambda: open_webui(self.root_url))
        menu.addAction("Open API Browser", lambda: open_apibrowser(self.root_url))

        menu.addSeparator()

        modulesMenu = menu.addMenu("Modules")
        self._build_modulemenu(modulesMenu)

        menu.addSeparator()
        menu.addAction(
            "Open log folder", lambda: open_dir(aw_core.dirs.get_log_dir(None))
        )
        menu.addAction(
            "Open config folder", lambda: open_dir(aw_core.dirs.get_config_dir(None))
        )
        menu.addSeparator()

        exitIcon = QIcon.fromTheme(
            "application-exit", QIcon("media/application_exit.png")
        )
        # This check is an attempted solution to: https://github.com/ActivityWatch/activitywatch/issues/62
        # Seems to be in agreement with: https://github.com/OtterBrowser/otter-browser/issues/1313
        #   "it seems that the bug is also triggered when creating a QIcon with an invalid path"
        if exitIcon.availableSizes():
            menu.addAction(exitIcon, "Quit ActivityWatch", lambda: exit(self.manager))
        else:
            menu.addAction("Quit ActivityWatch", lambda: exit(self.manager))

        self.setContextMenu(menu)

        def show_module_failed_dialog(module: Module) -> None:
            box = QMessageBox(self._parent)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(f"Module {module.name} quit unexpectedly")
            box.setDetailedText(module.read_log(self.testing))

            restart_button = QPushButton("Restart", box)
            restart_button.clicked.connect(module.start)
            box.addButton(restart_button, QMessageBox.ButtonRole.AcceptRole)
            box.setStandardButtons(QMessageBox.StandardButton.Cancel)

            box.show()

        def rebuild_modules_menu() -> None:
            for action in modulesMenu.actions():
                if action.isEnabled():
                    module: Module = action.data()
                    alive = module.is_alive()
                    action.setChecked(alive)
            # TODO: Do it in a better way, singleShot isn't pretty...
            QtCore.QTimer.singleShot(2000, rebuild_modules_menu)

        QtCore.QTimer.singleShot(2000, rebuild_modules_menu)

        def check_module_status() -> None:
            unexpected_exits = self.manager.get_unexpected_stops()
            if unexpected_exits:
                for module in unexpected_exits:
                    show_module_failed_dialog(module)
                    module.stop()

            # TODO: Do it in a better way, singleShot isn't pretty...
            QtCore.QTimer.singleShot(2000, rebuild_modules_menu)

        QtCore.QTimer.singleShot(2000, check_module_status)

    def _build_modulemenu(self, moduleMenu: QMenu) -> None:
        moduleMenu.clear()

        def add_module_menuitem(module: Module) -> None:
            title = module.name
            ac = moduleMenu.addAction(title, lambda: module.toggle(self.testing))

            ac.setData(module)
            ac.setCheckable(True)
            ac.setChecked(module.is_alive())

        for location, modules in [
            ("bundled", self.manager.modules_bundled),
            ("system", self.manager.modules_system),
        ]:
            header = moduleMenu.addAction(location)
            header.setEnabled(False)

            for module in sorted(modules, key=lambda m: m.name):
                add_module_menuitem(module)


def exit(manager: Manager) -> None:
    logger.info("Shutting down ActivityWatch services…")
    manager.stop_all()
    # Terminate entire process group, just in case.
    # os.killpg(0, signal.SIGINT)

    QApplication.quit()


def _frozen_install_bases() -> List[Path]:
    """Roots where PyInstaller may place media/ (never rely on __file__ alone — it can be wrong in PYZ)."""
    bases: List[Path] = []
    if not getattr(sys, "frozen", False):
        return bases
    exe_dir = Path(sys.executable).resolve().parent
    bases.append(exe_dir)
    bases.append(exe_dir / "_internal")
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bases.append(Path(meipass))
    seen: Set[str] = set()
    out: List[Path] = []
    for b in bases:
        try:
            key = str(b.resolve())
        except OSError:
            key = str(b)
        if key not in seen:
            seen.add(key)
            out.append(b)
    return out


def _try_icon_from_path(p: Path) -> Optional[QIcon]:
    if not p.is_file():
        return None
    if p.suffix.lower() == ".ico":
        ic = QIcon(str(p))
        return ic if not ic.isNull() else None
    pm = QPixmap(str(p))
    if pm.isNull():
        return None
    ic = QIcon(pm)
    return ic if not ic.isNull() else None


def _discover_logo_file_frozen() -> Optional[Path]:
    """Walk install tree shallowly for media/logo/* (handles odd flatten / CI layouts)."""
    for base in _frozen_install_bases():
        logo_dir = base / "media" / "logo"
        if not logo_dir.is_dir():
            continue
        for name in ("logo.ico", "logo.png", "logo-128.png"):
            p = logo_dir / name
            if p.is_file():
                return p
    # e.g. logo.ico copied next to exe by mistake
    for base in _frozen_install_bases():
        for name in ("logo.ico", "logo.png"):
            p = base / name
            if p.is_file():
                return p
    return None


def _load_tray_window_icon() -> QIcon:
    """Resolve tray icon for dev, PyInstaller onedir/onefile (incl. _internal), macOS .app."""
    icon = QIcon("icons:logo.png")
    if not icon.isNull() and icon.availableSizes():
        return icon

    if sys.platform == "win32":
        filenames = ("logo.ico", "logo.png", "logo-128.png")
    else:
        filenames = ("logo.png", "logo-128.png")

    # Dev / source tree (unfrozen)
    scriptdir = Path(__file__).resolve().parent
    for root in (
        scriptdir.parent,
        scriptdir.parent.parent / "Resources" / "aw_qt",
    ):
        logo_dir = root / "media" / "logo"
        for name in filenames:
            p = logo_dir / name
            ic = _try_icon_from_path(p)
            if ic is not None:
                logger.info("Tray icon loaded from %s", p)
                return ic

    # Frozen: use install roots only (not __file__ — wrong for PYZ modules)
    for base in _frozen_install_bases():
        logo_dir = base / "media" / "logo"
        for name in filenames:
            p = logo_dir / name
            ic = _try_icon_from_path(p)
            if ic is not None:
                logger.info("Tray icon loaded from %s", p)
                return ic

    discovered = _discover_logo_file_frozen()
    if discovered is not None:
        ic = _try_icon_from_path(discovered)
        if ic is not None:
            logger.info("Tray icon loaded (discovered) from %s", discovered)
            return ic

    # PyInstaller sets the .exe icon from logo.ico — Qt can load it from the binary on Windows.
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        ic_exe = QIcon(str(exe_path))
        if not ic_exe.isNull():
            logger.info("Tray icon loaded from application executable resource: %s", exe_path)
            return ic_exe

    if getattr(sys, "frozen", False):
        logger.warning(
            "Tray icon: no media/logo file and no exe icon; tried bases %s",
            _frozen_install_bases(),
        )
    else:
        logger.warning("Tray icon: no media/logo under aw-qt dev tree")
    return icon


def _icon_for_windows_shell_tray(icon: QIcon) -> QIcon:
    """Windows ShellNotify uses small HICONs; QIcon(.exe) can report isNull()==False but return null 16px pixmaps."""
    if sys.platform != "win32":
        return icon
    out = QIcon()
    for s in (16, 20, 24, 32):
        pm = icon.pixmap(s, s)
        if not pm.isNull():
            out.addPixmap(pm)
    if not out.isNull():
        return out
    for s in (128, 64, 48, 256, 32):
        pm = icon.pixmap(s, s)
        if pm.isNull():
            continue
        for ts in (16, 20, 24, 32):
            sm = pm.scaled(
                ts,
                ts,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            out.addPixmap(sm)
        if not out.isNull():
            return out
    return icon


def run(manager: Manager, testing: bool = False) -> Any:
    logger.info("Creating trayicon...")

    # Before any QWidget / QApplication — required for correct taskbar/shell integration on Windows.
    QCoreApplication.setApplicationName("CtrlDesk")
    QCoreApplication.setOrganizationName("CtrlDesk")
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "GFPC.CtrlDesk.aw-qt.1"
            )
        except Exception as e:
            logger.debug("SetCurrentProcessExplicitAppUserModelID: %s", e)

    # Tray pixmaps on HiDPI Windows
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    # This is needed for the icons to get picked up with PyInstaller
    scriptdir = Path(__file__).parent

    # When run from source:
    #   __file__ is aw_qt/trayicon.py
    #   scriptdir is ./aw_qt
    #   logodir is ./media/logo
    QtCore.QDir.addSearchPath("icons", str(scriptdir.parent / "media/logo/"))

    # When run from .app:
    #   __file__ is ./Contents/MacOS/aw-qt
    #   scriptdir is ./Contents/MacOS
    #   logodir is ./Contents/Resources/aw_qt/media/logo
    QtCore.QDir.addSearchPath(
        "icons", str(scriptdir.parent.parent / "Resources/aw_qt/media/logo/")
    )

    # logger.info(f"search paths: {QtCore.QDir.searchPaths('icons')}")

    # Without this, Ctrl+C will have no effect
    signal.signal(signal.SIGINT, lambda *args: exit(manager))
    # Ensure cleanup happens on SIGTERM
    signal.signal(signal.SIGTERM, lambda *args: exit(manager))

    timer = QtCore.QTimer()
    timer.start(100)  # You may change this if you wish.
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.

    # root widget
    widget = QWidget()

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(
            widget,
            "Systray",
            "I couldn't detect any system tray on this system. Either get one or run the ActivityWatch modules from the console.",
        )
        sys.exit(1)

    if sys.platform == "darwin":
        icon = QIcon("icons:black-monochrome-logo.png")
        # Allow macOS to use filters for changing the icon's color
        icon.setIsMask(True)
    else:
        icon = _load_tray_window_icon()
        if sys.platform == "win32":
            icon = _icon_for_windows_shell_tray(icon)

    trayIcon = TrayIcon(manager, icon, widget, testing=testing)
    trayIcon.show()

    QApplication.setQuitOnLastWindowClosed(False)

    logger.info("Initialized aw-qt and trayicon successfully")
    # Run the application, blocks until quit
    return app.exec()
