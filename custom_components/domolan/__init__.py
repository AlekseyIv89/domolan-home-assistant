"""Интеграция Domolan для Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import DomolanApiClient
from .const import (
    CONF_LOGIN,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .coordinator import DomolanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции из записи конфигурации."""
    hass.data.setdefault(DOMAIN, {})

    # ── Читаем параметры записи ──────────────────────────────────────────
    login: str = entry.data[CONF_LOGIN]
    password: str = entry.data[CONF_PASSWORD]
    update_interval: int = entry.options.get(
        CONF_UPDATE_INTERVAL,
        entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
    )

    _LOGGER.debug(
        "Настройка Domolan: login=%s, интервал=%s мин.",
        login,
        update_interval,
    )

    # ── Создаём клиент и проходим аутентификацию ─────────────────────────
    client = DomolanApiClient(hass, login, password)
    try:
        await client.authenticate()
    except Exception as err:  # noqa: BLE001
        _LOGGER.error("Не удалось аутентифицироваться в Domolan: %s", err)
        await client.close()
        return False

    # ── Создаём координатор и делаем первый опрос ────────────────────────
    coordinator = DomolanDataUpdateCoordinator(
        hass, client, update_interval
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:  # noqa: BLE001
        _LOGGER.error("Первый опрос данных Domolan не удался: %s", err)
        await client.close()
        return False

    # ── Сохраняем всё в hass.data ────────────────────────────────────────
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    # ── Загружаем платформы (sensor.py) ──────────────────────────────────
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Слушаем изменения опций (например, интервала обновления) ─────────
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info("Интеграция Domolan успешно запущена")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data:
            client = data.get("client")
            if client:
                await client.close()
        _LOGGER.info("Интеграция Domolan выгружена")

    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Перезагружаем запись при изменении опций (например, интервала)."""
    _LOGGER.debug("Опции Domolan изменились, перезагружаем запись")
    await hass.config_entries.async_reload(entry.entry_id)