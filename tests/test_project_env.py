import os
from pathlib import Path

from tradingagents.config.env import load_project_env
from tradingagents.execution import IBKRConnectionConfig, IBKRPaperRiskConfig


def test_project_env_overrides_stale_shell_values(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / ".env").write_text("TRADINGAGENTS_IBKR_ACCOUNT=DU014\n", encoding="utf-8")
    monkeypatch.setenv("TRADINGAGENTS_IBKR_ACCOUNT", "DU005")

    load_project_env(project)

    assert os.environ["TRADINGAGENTS_IBKR_ACCOUNT"] == "DU014"


def test_project_env_can_preserve_existing_values(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / ".env").write_text("TRADINGAGENTS_IBKR_ACCOUNT=DU014\n", encoding="utf-8")
    monkeypatch.setenv("TRADINGAGENTS_IBKR_ACCOUNT", "DU005")

    load_project_env(project, override=False)

    assert os.environ["TRADINGAGENTS_IBKR_ACCOUNT"] == "DU005"


def test_project_ibkr_paper_account_is_du007(monkeypatch):
    monkeypatch.delenv("TRADINGAGENTS_IBKR_ACCOUNT", raising=False)
    monkeypatch.delenv("TRADINGAGENTS_IBKR_ALLOWED_ACCOUNTS", raising=False)

    load_project_env(Path(__file__).resolve())

    assert IBKRConnectionConfig.from_env().account == "DU007"
    assert IBKRPaperRiskConfig.from_env().allowed_accounts == ("DU007",)
