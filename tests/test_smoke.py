from typer.testing import CliRunner

from raiox.cli import app
from raiox.config import get_settings


def test_cli_help():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Raio-X OPME" in result.output


def test_settings_load():
    s = get_settings(offline=False)
    assert s.analysis.min_purchases_per_uf >= 1
    assert s.bcb.ipca_series == 433
