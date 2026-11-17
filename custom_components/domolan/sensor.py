"""Сенсоры для интеграции Domolan."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Настройка сенсоров при загрузке интеграции."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [
            BalanceSensor(coordinator, entry),
            CreditSensor(coordinator, entry),
            DaysBeforeBlockSensor(coordinator, entry),
            BlockedSensor(coordinator, entry),
            TariffNameSensor(coordinator, entry),
            TariffPriceSensor(coordinator, entry),
            TariffSpeedSensor(coordinator, entry),
            TariffActiveSinceSensor(coordinator, entry),
            StaticIpSensor(coordinator, entry),
            PrepaidSensor(coordinator, entry),
        ]
    )


class DomolanBaseSensor(CoordinatorEntity, SensorEntity):
    """Базовый класс для всех сенсоров Domolan."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        unit: str | None = None,
        icon: str | None = None,
        state_class: SensorStateClass | None = None,
        device_class: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_state_class = state_class
        if device_class:
            self._attr_device_class = device_class

        # Привязка к устройству (запись конфигурации)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Domolan",
            "manufacturer": "Domolan",
            "model": "Internet Account",
        }

    @property
    def native_value(self) -> Any:
        """Значение сенсора из нормализованных данных координатора."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._key)


# ─── Баланс ──────────────────────────────────────────────────────────────

class BalanceSensor(DomolanBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="balance",
            name="Баланс",
            unit="RUB",
            icon="mdi:cash",
            state_class=SensorStateClass.TOTAL,
        )


class CreditSensor(DomolanBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="credit",
            name="Кредитный лимит",
            unit="RUB",
            icon="mdi:credit-card",
            state_class=SensorStateClass.TOTAL,
        )


# ─── Блокировка ──────────────────────────────────────────────────────────

class DaysBeforeBlockSensor(DomolanBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="days_before_block",
            name="Дней до блокировки",
            unit="дней",
            icon="mdi:calendar-clock",
            state_class=SensorStateClass.MEASUREMENT,
        )


class BlockedSensor(DomolanBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="blocked",
            name="Интернет заблокирован",
            icon="mdi:lock",
        )

    @property
    def native_value(self) -> str | None:
        """Человекочитаемое значение: 'Да' / 'Нет'."""
        if not self.coordinator.data:
            return None
        return "Да" if self.coordinator.data.get("blocked") else "Нет"

    @property
    def icon(self) -> str:
        """Динамическая иконка в зависимости от состояния."""
        if self.coordinator.data and self.coordinator.data.get("blocked"):
            return "mdi:lock"
        return "mdi:lock-open"


# ─── Тариф ───────────────────────────────────────────────────────────────

class TariffNameSensor(DomolanBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="tariff_name",
            name="Тариф",
            icon="mdi:tag",
        )


class TariffPriceSensor(DomolanBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="tariff_price",
            name="Стоимость тарифа",
            unit="RUB",
            icon="mdi:cash-multiple",
            state_class=SensorStateClass.TOTAL,
        )


class TariffSpeedSensor(DomolanBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="tariff_speed",
            name="Скорость",
            unit="Mbit/s",
            icon="mdi:speedometer",
        )


class TariffActiveSinceSensor(DomolanBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="tariff_active_since",
            name="Тариф активен с",
            icon="mdi:calendar-start",
        )


# ─── Дополнительно ───────────────────────────────────────────────────────

class StaticIpSensor(DomolanBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="static_ip",
            name="Статический IP",
            icon="mdi:ip",
        )

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        return "Да" if self.coordinator.data.get("static_ip") else "Нет"

    @property
    def icon(self) -> str:
        if self.coordinator.data and self.coordinator.data.get("static_ip"):
            return "mdi:ip"
        return "mdi:ip-outline"


class PrepaidSensor(DomolanBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="prepaid",
            name="Предоплатный тариф",
            icon="mdi:wallet",
        )

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        return "Да" if self.coordinator.data.get("prepaid") else "Нет"

    @property
    def icon(self) -> str:
        if self.coordinator.data and self.coordinator.data.get("prepaid"):
            return "mdi:wallet"
        return "mdi:wallet-outline"