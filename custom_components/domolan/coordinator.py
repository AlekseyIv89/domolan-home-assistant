"""DataUpdateCoordinator для интеграции Domolan."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class DomolanDataUpdateCoordinator(DataUpdateCoordinator):
    """
    Координатор, который периодически опрашивает /api/user/data
    и раздаёт данные сенсорам.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client,
        update_interval_minutes: int = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        self.client = client

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=update_interval_minutes),
        )

    async def _async_update_data(self) -> dict:
        """
        Вызывается координатором по расписанию.
        Дёргает клиент, который делает GET /api/user/data.
        """
        try:
            data = await self.client.get_data()
            _LOGGER.debug(
                "Данные обновлены: баланс=%s, дней до блокировки=%s, blocked=%s",
                data.get("balance"),
                data.get("days_before_block"),
                data.get("blocked"),
            )
            return data
        except Exception as err:
            _LOGGER.exception("Ошибка при обновлении данных Domolan")
            raise UpdateFailed(f"Ошибка обновления данных: {err}") from err