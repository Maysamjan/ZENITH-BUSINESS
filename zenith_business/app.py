"""Application bootstrap and entry point (Prompt 01 §4, Stage 02 §2).

Startup responsibilities are clearly separated into small steps so future stages
can extend them at well-defined extension points.

Production startup order (Stage 02):
    1. resolve + create data directories
    2. load configuration
    3. initialize logging
    4. install global exception handler
    5. [extension point] license verification  -> dev provider only
    6. open database + run migrations + health check
    7. build the application context (repositories + services + session)
    8. create QApplication + apply theme
    9. AUTHENTICATION GATE (initial setup / login) — never straight to dashboard
   10. create + show MainWindow for the authenticated user
"""

from __future__ import annotations

import sys

from zenith_business.core.config import AppConfig, load_config
from zenith_business.core.error_handler import install_global_exception_handler
from zenith_business.core.identity import IDENTITY
from zenith_business.core.logging_setup import get_logger, setup_logging
from zenith_business.core.paths import resolve_paths
from zenith_business.database import Database, check_health
from zenith_business.security.licensing import DevelopmentLicenseProvider
from zenith_business.services.context import ApplicationContext, open_application_context


class Bootstrap:
    """Headless startup steps, separated from Qt so they are unit-testable.

    Running the GUI is a thin wrapper around this (see :func:`run`). Tests can
    drive :meth:`initialize` without creating a QApplication, obtaining a fully
    migrated :class:`ApplicationContext`.
    """

    def __init__(self) -> None:
        self.config: AppConfig | None = None
        self.database: Database | None = None
        self.context: ApplicationContext | None = None
        self.license_provider = DevelopmentLicenseProvider()

    def initialize(self) -> AppConfig:
        """Perform non-GUI startup steps and return the loaded config."""
        # 1. data directories
        paths = resolve_paths().ensure()

        # 2. configuration
        self.config = load_config(paths)

        # 3. logging
        setup_logging(paths.logs_dir, self.config.logging)
        logger = get_logger("app")
        logger.info(
            "Starting %s (%s build) — config=%s",
            IDENTITY.full_title,
            IDENTITY.channel,
            paths.config_file,
        )

        # 4. global exception handling
        install_global_exception_handler()

        # 5. license verification — extension point (dev provider only)
        logger.info("License state: %s", self.license_provider.current_state().summary)

        # 6. open the production database, run migrations, health-check
        self.database = Database(paths.database_file)
        self.context = open_application_context(
            self.database, backups_dir=paths.backups_dir
        )
        health = check_health(self.database)
        if health.ok:
            logger.info("Database ready (SQLite %s), schema migrated.", health.sqlite_version)
        else:
            logger.error("Database health degraded: %s", health.message)

        # 7. initial-setup / authentication state is evaluated by the GUI gate.
        logger.info(
            "Initial setup required: %s", self.context.is_setup_required
        )

        return self.config

    def shutdown(self) -> None:
        """Release resources acquired during startup."""
        logger = get_logger("app")
        if self.database is not None:
            self.database.close()
        logger.info("%s shut down cleanly", IDENTITY.product)


def run(argv: list[str] | None = None) -> int:
    """Create the Qt application, gate on authentication, then show the shell."""
    from PyQt6.QtWidgets import QApplication, QDialog

    from zenith_business.ui.auth.auth_window import AuthWindow
    from zenith_business.ui.design.theme import build_stylesheet
    from zenith_business.ui.main_window import MainWindow

    boot = Bootstrap()
    config = boot.initialize()
    context = boot.context
    assert context is not None

    from zenith_business.core.fonts import apply_base_font

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(IDENTITY.product)
    app.setApplicationDisplayName(IDENTITY.product)
    app.setApplicationVersion(IDENTITY.version)
    app.setOrganizationName(IDENTITY.company)
    apply_base_font(app)  # bundled Vazirmatn — consistent EN + Dari typography
    app.setStyleSheet(build_stylesheet())

    logger = get_logger("app")
    try:
        # Authentication gate → main window loop. Signing out returns here so the
        # login screen appears again without restarting the process.
        while True:
            gate = AuthWindow(context, config)
            if gate.exec() != QDialog.DialogCode.Accepted or gate.authenticated_user is None:
                logger.info("Authentication gate dismissed; exiting.")
                return 0

            relogin = {"requested": False}

            def _logout() -> None:
                context.auth.logout()
                relogin["requested"] = True
                window.close()

            window = MainWindow(
                config,
                database=context.db,
                license_provider=boot.license_provider,
                current_user=gate.authenticated_user,
                on_logout=_logout,
            )
            if config.ui.start_maximized:
                window.showMaximized()
            else:
                window.show()
            app.exec()

            if not relogin["requested"]:
                return 0
    finally:
        boot.shutdown()


def main() -> None:
    """Console-script entry point."""
    raise SystemExit(run())


if __name__ == "__main__":
    main()
