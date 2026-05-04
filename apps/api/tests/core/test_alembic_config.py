import configparser
from pathlib import Path

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"
ALEMBIC_DIR = Path(__file__).parents[2] / "alembic"


def test_alembic_ini_exists():
    assert ALEMBIC_INI.exists(), "alembic.ini must exist at apps/api/alembic.ini"


def test_alembic_ini_is_valid_config():
    cfg = configparser.ConfigParser()
    cfg.read(ALEMBIC_INI)
    assert cfg.has_section("alembic"), "alembic.ini must have [alembic] section"
    assert cfg.get("alembic", "script_location") == "alembic"
    assert cfg.get("alembic", "sqlalchemy.url") == "", (
        "sqlalchemy.url must be blank (set by env.py)"
    )


def test_alembic_env_exists():
    assert (ALEMBIC_DIR / "env.py").exists(), "alembic/env.py must exist"


def test_alembic_mako_exists():
    assert (ALEMBIC_DIR / "script.py.mako").exists(), "alembic/script.py.mako must exist"


def test_alembic_env_defines_required_functions():
    source = (ALEMBIC_DIR / "env.py").read_text()
    assert "def run_migrations_offline" in source
    assert "def run_migrations_online" in source
    assert "def do_run_migrations" in source


def test_alembic_env_uses_settings_and_async_engine():
    source = (ALEMBIC_DIR / "env.py").read_text()
    assert "get_settings" in source
    assert "async_engine_from_config" in source
    assert "Base.metadata" in source


def test_alembic_mako_contains_revision_variables():
    source = (ALEMBIC_DIR / "script.py.mako").read_text()
    assert "${up_revision}" in source
    assert "${down_revision" in source
    assert "def upgrade" in source
    assert "def downgrade" in source


def test_alembic_env_wires_alembic_context():
    source = (ALEMBIC_DIR / "env.py").read_text()
    assert "context.is_offline_mode" in source
    assert "context.configure" in source
    assert "context.run_migrations" in source
    assert "set_main_option" in source


def test_alembic_env_online_uses_asyncio_run():
    source = (ALEMBIC_DIR / "env.py").read_text()
    assert "asyncio.run" in source


def test_alembic_env_configures_logging_from_ini():
    source = (ALEMBIC_DIR / "env.py").read_text()
    assert "fileConfig" in source
    assert "config_file_name" in source


def test_alembic_env_offline_uses_compare_type_and_literal_binds():
    source = (ALEMBIC_DIR / "env.py").read_text()
    assert "compare_type=True" in source
    assert "literal_binds=True" in source


def test_alembic_env_online_uses_async_engine_and_run_sync():
    source = (ALEMBIC_DIR / "env.py").read_text()
    assert "async_engine_from_config" in source
    assert "run_sync" in source


def test_alembic_env_do_run_migrations_uses_connection_type():
    source = (ALEMBIC_DIR / "env.py").read_text()
    assert "Connection" in source
    assert "# type: ignore" not in source
