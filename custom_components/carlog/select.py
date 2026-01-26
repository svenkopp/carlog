from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .__init__ import SIGNAL_UPDATED

MAINT_OPTIONS = ["oil", "tires", "brakes", "other"]


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    car_id = entry.data["car_id"]
    name = entry.data["name"]
    async_add_entities([CarUiMaintType(hass, car_id, name)], update_before_add=True)


class CarUiMaintType(SelectEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:wrench"
    _attr_options = MAINT_OPTIONS

    def __init__(self, hass: HomeAssistant, car_id: str, car_name: str):
        self.hass = hass
        self.car_id = car_id
        self._attr_name = "Onderhoudstype (invoer)"
        self._attr_unique_id = f"{car_id}_ui_maint_type"
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
    def current_option(self) -> str:
        return self._car().setdefault("ui", {}).get("maint_type", "oil")

    async def async_select_option(self, option: str) -> None:
        car = self._car()
        car.setdefault("ui", {})["maint_type"] = option
        await self.hass.data[DOMAIN]["store"].async_save(self.hass.data[DOMAIN]["data"])
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self._unsub = async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    def _handle_update(self) -> None:
        self.async_write_ha_state()
