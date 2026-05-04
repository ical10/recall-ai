from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_first_migration_revision_is_0001_initial() -> None:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    scripts = ScriptDirectory.from_config(cfg)
    heads = scripts.get_heads()
    assert list(heads) == ["0001_initial"]


def test_first_migration_creates_three_tables() -> None:
    initial = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0001_initial.py"
    text = initial.read_text()
    assert 'op.create_table(\n        "users"' in text
    assert 'op.create_table(\n        "vocab_items"' in text
    assert 'op.create_table(\n        "reviews"' in text
