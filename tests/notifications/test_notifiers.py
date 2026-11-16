import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from construction_pm.notifications.notifiers import ConsoleNotifier, TelegramNotifier


def test_console_notifier_prints_and_reports_success():
    printed = []

    result = ConsoleNotifier(printer=printed.append).notify("Петренко", "Привіт")

    assert result.delivered and result.error is None
    assert printed == ["[сповіщення → Петренко] Привіт"]


def fake_response(status=200):
    resp = MagicMock()
    resp.status = status
    resp.__enter__.return_value = resp
    return resp


@pytest.fixture
def no_sleep():
    with patch("construction_pm.notifications.notifiers.time.sleep") as sleep:
        yield sleep


def test_telegram_sends_json_to_bot_api(no_sleep):
    with patch("urllib.request.urlopen", return_value=fake_response()) as urlopen:
        result = TelegramNotifier("TOKEN", timeout_s=5).notify("12345", "Етап «Фундамент»")

    assert result.delivered
    req = urlopen.call_args.args[0]
    assert req.full_url == "https://api.telegram.org/botTOKEN/sendMessage"
    assert json.loads(req.data) == {"chat_id": "12345", "text": "Етап «Фундамент»"}
    assert urlopen.call_args.kwargs["timeout"] == 5


def test_telegram_retries_then_succeeds(no_sleep):
    side = [urllib.error.URLError("down"), fake_response()]
    with patch("urllib.request.urlopen", side_effect=side) as urlopen:
        result = TelegramNotifier("T").notify("1", "x")

    assert result.delivered
    assert urlopen.call_count == 2


def test_telegram_gives_up_after_attempts_and_returns_error(no_sleep):
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")) as urlopen:
        result = TelegramNotifier("T", attempts=3).notify("1", "x")

    assert not result.delivered
    assert "timed out" in result.error
    assert urlopen.call_count == 3


def test_telegram_non_200_is_reported(no_sleep):
    with patch("urllib.request.urlopen", return_value=fake_response(status=500)):
        result = TelegramNotifier("T", attempts=1).notify("1", "x")

    assert result == result.__class__(delivered=False, error="HTTP 500")


def test_d2_network_os_error_is_returned_as_result_not_raised(no_sleep):
    """Регресійний тест D2: ConnectionResetError (OSError, не URLError) не повинен «вилітати» з notify()."""
    with patch("urllib.request.urlopen", side_effect=ConnectionResetError("reset by peer")):
        result = TelegramNotifier("T", attempts=2).notify("1", "x")

    assert not result.delivered
    assert "reset by peer" in result.error


def test_d3_no_sleep_after_last_failed_attempt(no_sleep):
    """Регресійний тест D3: після останньої невдалої спроби чекати не потрібно."""
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        TelegramNotifier("T", attempts=3).notify("1", "x")

    assert no_sleep.call_count == 2
