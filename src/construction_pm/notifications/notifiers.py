"""Реалізації INotifier: консольна (за замовчуванням) і Telegram Bot API."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from construction_pm.workforce_core.ports import DeliveryResult, INotifier

log = logging.getLogger(__name__)


class ConsoleNotifier(INotifier):
    """Виводить повідомлення в журнал/консоль. Використовується для демонстрації та розробки."""

    def __init__(self, printer=print) -> None:
        self._print = printer

    def notify(self, recipient: str, text: str) -> DeliveryResult:
        self._print(f"[сповіщення → {recipient}] {text}")
        return DeliveryResult(delivered=True)


class TelegramNotifier(INotifier):
    """Надсилає повідомлення через Telegram Bot API (HTTPS).

    NFR: тайм-аут 5 с, до 3 спроб; помилка повертається як DeliveryResult, а не виняток.
    """

    API_BASE = "https://api.telegram.org"

    def __init__(
        self, token: str, timeout_s: float = 5.0, attempts: int = 3, api_base: str = API_BASE
    ) -> None:
        self._url = f"{api_base.rstrip('/')}/bot{token}/sendMessage"
        self._timeout = timeout_s
        self._attempts = attempts

    def notify(self, recipient: str, text: str) -> DeliveryResult:
        body = json.dumps({"chat_id": recipient, "text": text}).encode()
        last_error = "unknown"
        for attempt in range(1, self._attempts + 1):
            req = urllib.request.Request(self._url, data=body, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                    if resp.status == 200:
                        return DeliveryResult(delivered=True)
                    last_error = f"HTTP {resp.status}"
            except OSError as exc:  # URLError, TimeoutError, ConnectionResetError тощо
                last_error = str(exc)
            log.info("Спроба %d/%d не вдалася: %s", attempt, self._attempts, last_error)
            if attempt < self._attempts:
                time.sleep(0.5 * attempt)
        return DeliveryResult(delivered=False, error=last_error)
