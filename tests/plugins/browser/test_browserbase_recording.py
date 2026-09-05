"""Network-disabled Browserbase session-recording payload contracts."""

from __future__ import annotations

import copy
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _response(status_code: int = 201) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.ok = status_code < 400
    response.text = f"synthetic HTTP {status_code}"
    response.json.return_value = {
        "id": "synthetic-browserbase-session",
        "connectUrl": "wss://synthetic.browserbase.invalid/devtools/browser/test",
    }
    return response


def _configure_browserbase_recording(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    record_session: bool | None,
    *,
    proxies: bool | None = None,
    keep_alive: bool | None = None,
) -> None:
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    settings = {
        key: value
        for key, value in {
            "record_session": record_session,
            "proxies": proxies,
            "keep_alive": keep_alive,
        }.items()
        if value is not None
    }
    if settings:
        yaml_settings = "".join(
            f"    {key}: {str(value).lower()}\n" for key, value in settings.items()
        )
        (hermes_home / "config.yaml").write_text(
            f"browser:\n  browserbase:\n{yaml_settings}", encoding="utf-8"
        )


def _set_synthetic_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BROWSERBASE_API_KEY", "synthetic-browserbase-key")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "synthetic-browserbase-project")


def _create_session_payloads(responses: list[MagicMock]) -> list[dict[str, Any]]:
    from plugins.browser.browserbase.provider import BrowserbaseBrowserProvider

    payloads: list[dict[str, Any]] = []
    response_iterator = iter(responses)

    def capture_payload(*args: Any, **kwargs: Any) -> MagicMock:
        payloads.append(copy.deepcopy(kwargs["json"]))
        return next(response_iterator)

    with patch(
        "plugins.browser.browserbase.provider.requests.post", side_effect=capture_payload
    ):
        BrowserbaseBrowserProvider().create_session("synthetic-task")

    return payloads


def test_configured_false_disables_browserbase_provider_recording(tmp_path, monkeypatch):
    _configure_browserbase_recording(tmp_path, monkeypatch, record_session=False)
    _set_synthetic_credentials(monkeypatch)

    payload = _create_session_payloads([_response()])[0]

    assert payload["browserSettings"]["recordSession"] is False


def test_missing_browserbase_recording_config_defaults_to_enabled(tmp_path, monkeypatch):
    _configure_browserbase_recording(tmp_path, monkeypatch, record_session=None)
    _set_synthetic_credentials(monkeypatch)

    payload = _create_session_payloads([_response()])[0]

    assert payload["browserSettings"]["recordSession"] is True


def test_configured_false_disables_browserbase_proxies(tmp_path, monkeypatch):
    _configure_browserbase_recording(
        tmp_path, monkeypatch, record_session=None, proxies=False
    )
    _set_synthetic_credentials(monkeypatch)
    monkeypatch.setenv("BROWSERBASE_PROXIES", "true")

    payload = _create_session_payloads([_response()])[0]

    assert "proxies" not in payload


def test_configured_false_disables_browserbase_keep_alive(tmp_path, monkeypatch):
    _configure_browserbase_recording(
        tmp_path, monkeypatch, record_session=None, keep_alive=False
    )
    _set_synthetic_credentials(monkeypatch)
    monkeypatch.setenv("BROWSERBASE_KEEP_ALIVE", "true")

    payload = _create_session_payloads([_response()])[0]

    assert "keepAlive" not in payload


def test_advanced_stealth_coexists_with_browserbase_recording(tmp_path, monkeypatch):
    _configure_browserbase_recording(tmp_path, monkeypatch, record_session=None)
    _set_synthetic_credentials(monkeypatch)
    monkeypatch.setenv("BROWSERBASE_ADVANCED_STEALTH", "true")

    payload = _create_session_payloads([_response()])[0]

    assert payload["browserSettings"] == {
        "advancedStealth": True,
        "recordSession": True,
    }


def test_sequential_402_retries_preserve_browserbase_recording_setting(
    tmp_path, monkeypatch
):
    _configure_browserbase_recording(tmp_path, monkeypatch, record_session=False)
    _set_synthetic_credentials(monkeypatch)

    payloads = _create_session_payloads([_response(402), _response(402), _response()])

    assert payloads == [
        {
            "projectId": "synthetic-browserbase-project",
            "browserSettings": {"recordSession": False},
            "keepAlive": True,
            "proxies": True,
        },
        {
            "projectId": "synthetic-browserbase-project",
            "browserSettings": {"recordSession": False},
            "proxies": True,
        },
        {
            "projectId": "synthetic-browserbase-project",
            "browserSettings": {"recordSession": False},
        },
    ]
