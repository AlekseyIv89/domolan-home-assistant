"""Config flow для интеграции Domolan."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import DomolanApiClient
from .const import (
    DOMAIN,
    CONF_LOGIN,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# Разумные границы интервала опроса облачного API.
# Нижняя граница защищает от бана за частые запросы,
# верхняя — от «зависших» сенсоров, которые обновляются раз в сутки.
MIN_UPDATE_INTERVAL = 60
MAX_UPDATE_INTERVAL = 3600


def _interval_schema(default: int) -> vol.Schema:
    """Схема с валидацией интервала обновления (переиспользуется в user/options)."""
    return vol.Schema(
        {
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=default,
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL),
            ),
        }
    )


def _credentials_schema() -> vol.Schema:
    """Схема с логином и паролем для первичной настройки и reauth."""
    return vol.Schema(
        {
            vol.Required(CONF_LOGIN): str,
            vol.Required(CONF_PASSWORD): str,
        }
    )


class DomolanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Обработка первоначальной настройки интеграции."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Первый шаг: запрос учётных данных и интервала."""
        errors: dict[str, str] = {}

        if user_input is not None:
            login = user_input[CONF_LOGIN].strip()
            password = user_input[CONF_PASSWORD]
            interval = user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)

            # Уникальный идентификатор ставим ДО создания записи, но ПОСЛЕ
            # валидации ввода, и нормализуем регистр — иначе "User" и "user"
            # создадут две разные записи на одного человека.
            await self.async_set_unique_id(login.lower())
            self._abort_if_unique_id_configured()

            error = await self._async_try_auth(login, password)
            if error is None:
                return self.async_create_entry(
                    title=login,
                    data={
                        CONF_LOGIN: login,
                        CONF_PASSWORD: password,
                        CONF_UPDATE_INTERVAL: interval,
                    },
                )
            errors["base"] = error

        data_schema = self.add_suggested_values_to_schema(
            _credentials_schema().extend(_interval_schema(DEFAULT_UPDATE_INTERVAL).schema),
            user_input or {},
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Точка входа при истёкших учётных данных (вызывается HA автоматически)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Экран повторного ввода пароля при истёкшей сессии."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None

        if user_input is not None:
            login = entry.data[CONF_LOGIN]
            password = user_input[CONF_PASSWORD]

            error = await self._async_try_auth(login, password)
            if error is None:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_PASSWORD: password},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={CONF_LOGIN: entry.data[CONF_LOGIN]},
            errors=errors,
        )

    async def _async_try_auth(self, login: str, password: str) -> str | None:
        """
        Пробует аутентифицироваться.

        Возвращает ключ ошибки для формы (или None при успехе).
        Гарантированно закрывает сессию клиента — и при успехе, и при ошибке.
        """
        client = DomolanApiClient(self.hass, login, password)
        try:
            await client.authenticate()
        except ConfigEntryAuthFailed as err:
            _LOGGER.warning("Authentication rejected for %s: %s", login, err)
            return "invalid_auth"
        except (aiohttp.ClientConnectionError, aiohttp.ClientError) as err:
            _LOGGER.warning("Cannot connect to Domolan API: %s", err)
            return "cannot_connect"
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout while authenticating to Domolan API")
            return "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error during Domolan authentication")
            return "unknown"
        finally:
            await client.close()
        return None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> DomolanOptionsFlow:
        """Возвращает обработчик потока настроек."""
        return DomolanOptionsFlow()


class DomolanOptionsFlow(config_entries.OptionsFlow):
    """
    Обработчик изменения настроек.

    В HA 2025.x+ у этого класса НЕ должно быть __init__, принимающего config_entry.
    self.config_entry доступен автоматически.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Экран настроек: только интервал обновления."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL,
            self.config_entry.data.get(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
            ),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=_interval_schema(current_interval),
        )
