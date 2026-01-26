from __future__ import annotations

import datetime as dt

from homeassistant.components.date import DateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .__init__ import SIGNAL_UPDATED


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    car_id = entry.data["car_id"]
    name = entry.data["name"]
    async_add_entities([CarUiMaintDate(hass, car_id, name)], update_before_add=True)


class CarUiMaintDate(DateEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar"

    def __init__(self, hass: HomeAssistant, car_id: str, car_name: str):
        self.hass = hass
        self.car_id = car_id
        self._attr_name = "Onderhoudsdatum (optioneel)"
        self._attr_unique_id = f"{car_id}_ui_maint_date"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, car_id)},
            "name": car_name,
            "manufacturer": "CarLog",
            "model": "Virtual Car",
        }
        self._unsub = None

    def _car(self) -> dict:
        return self.hass.data[DOMAIN]["data"]["cars"].setdefault(
            self.car_id, {"fuel": [], "maintenance": {}, "meta": {}, "ui": {}}
        )

    @property
    def native_value(self):
        s = self._car().setdefault("ui", {}).get("maint_date")
        if not s:
            return None
        y, m, d = [int(x) for x in s.split("-")]
        return dt.date(y, m, d)

    async def async_set_value(self, value) -> None:
        car = self._car()
        car.setdefault("ui", {})["maint_date"] = value.isoformat() if value else None
        await self.hass.data[DOMAIN]["store"].async_save(self.hass.data[DOMAIN]["data"])
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self._unsub = async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    def _handle_update(self) -> None:
        self.async_write_ha_state()
