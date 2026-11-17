"""API-клиент для интеграции Domolan с использованием curl_cffi."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from curl_cffi import requests as curl_requests
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from .const import (
    URL_CSRF_TOKEN,
    URL_LOGIN,
    URL_CONFIRM_LOGIN,
    URL_DATA,
    CSRF_FIELD,
    CSRF_HEADER,
)

_LOGGER = logging.getLogger(__name__)


class DomolanApiClient:
    def __init__(self, hass, login: str, password: str) -> None:
        self.hass = hass
        self.login = login
        self.password = password
        # Сессия curl_cffi с имитацией Chrome
        self.session = curl_requests.Session(impersonate="chrome")
        self.csrf_token: str | None = None
        self.user_id: str | None = None
        self._auth_lock = asyncio.Lock()

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    def _auth_headers(self, json_body: bool = False) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.csrf_token:
            headers[CSRF_HEADER] = self.csrf_token
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    async def _get_csrf_token(self) -> None:
        def _sync_get():
            return self.session.get(
                URL_CSRF_TOKEN, headers=self._auth_headers()
            )

        resp = await self.hass.async_add_executor_job(_sync_get)
        if resp.status_code != 200:
            raise HomeAssistantError(f"CSRF request failed: {resp.status_code}")

        data = resp.json()
        if not isinstance(data, dict):
            raise HomeAssistantError(f"Unexpected CSRF payload: {data!r:.200}")
        token = data.get(CSRF_FIELD)
        if not token:
            raise HomeAssistantError(f"CSRF field '{CSRF_FIELD}' missing")
        self.csrf_token = token
        _LOGGER.debug("CSRF-токен получен (длина %d)", len(token))

    async def _login(self) -> str:
        """Шаг 2: Логин."""
        _LOGGER.debug("Начало _login для пользователя %s", self.login)
        payload = {"login": self.login, "password": self.password}

        def _sync_post():
            return self.session.post(
                URL_LOGIN,
                json=payload,
                headers=self._auth_headers(json_body=True),
            )

        resp = await self.hass.async_add_executor_job(_sync_post)
        _LOGGER.debug("Ответ _login: HTTP %s", resp.status_code)
        resp.raise_for_status()

        body = resp.text.strip()
        if not body:
            raise ValueError("Empty response from login endpoint")
        self.user_id = body
        _LOGGER.debug("Успешный вход, ID пользователя: %s", self.user_id)
        return self.user_id

    async def _confirm_login(self) -> str:
        """Шаг 3: Подтверждение логина."""
        _LOGGER.debug("Начало _confirm_login для ID %s", self.user_id)

        def _sync_get():
            return self.session.get(
                URL_CONFIRM_LOGIN, headers=self._auth_headers()
            )

        resp = await self.hass.async_add_executor_job(_sync_get)
        _LOGGER.debug("Ответ _confirm_login: HTTP %s", resp.status_code)
        resp.raise_for_status()

        data = resp.json()
        self.user_id = data.get("id", self.user_id)
        _LOGGER.debug("Логин подтверждён, ID: %s", self.user_id)
        return self.user_id

    async def _authenticate_unlocked(self) -> None:
        self.csrf_token = None
        self.user_id = None
        await self._get_csrf_token()
        await self._login()
        await self._confirm_login()
        _LOGGER.info("Аутентификация завершена")

    async def authenticate(self) -> None:
        async with self._auth_lock:
            await self._authenticate_unlocked()

    @staticmethod
    def _normalize_data(raw: dict) -> dict[str, Any]:
        tariff_id = raw.get("tariffId")
        tariffs = raw.get("tariffs") or {}
        tariff_info = tariffs.get(str(tariff_id), {}) if tariff_id is not None else {}

        speed_raw = tariff_info.get("speed")
        tariff_speed = speed_raw.get("0") if isinstance(speed_raw, dict) else speed_raw

        blocked = (
            DomolanApiClient._to_bool(raw.get("blocked"))
            or DomolanApiClient._to_bool(raw.get("blockedByLowBalance"))
        )

        return {
            "balance": raw.get("balance"),
            "credit": raw.get("credit"),
            "days_before_block": raw.get("daysBeforeBlock"),
            "tariff_name": tariff_info.get("name"),
            "tariff_price": tariff_info.get("price"),
            "tariff_speed": tariff_speed,
            "tariff_active_since": raw.get("tariffActiveSince"),
            "blocked": blocked,
            "static_ip": raw.get("staticIp"),
            "prepaid": DomolanApiClient._to_bool(raw.get("prepaid")),
        }

    async def get_data(self) -> dict[str, Any]:
        def _sync_get_data():
            return self.session.get(URL_DATA, headers=self._auth_headers())

        resp = await self.hass.async_add_executor_job(_sync_get_data)

        if resp.status_code in (401, 403):
            _LOGGER.warning(
                "Сессия истекла (HTTP %s), переаутентификация", resp.status_code
            )
            async with self._auth_lock:
                await self._authenticate_unlocked()

            resp = await self.hass.async_add_executor_job(_sync_get_data)
            if resp.status_code in (401, 403):
                raise ConfigEntryAuthFailed("Domolan: auth failed after re-login")

        resp.raise_for_status()
        raw = resp.json()

        result = self._normalize_data(raw)
        _LOGGER.debug(
            "Данные: баланс=%s, дней=%s, тариф=%s, blocked=%s",
            result["balance"],
            result["days_before_block"],
            result["tariff_name"],
            result["blocked"],
        )
        return result

    async def close(self) -> None:
        # curl_cffi Session не требует явного закрытия,
        # но метод оставлен для совместимости с кодом интеграции.
        pass
