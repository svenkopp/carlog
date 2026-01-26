from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .__init__ import SIGNAL_UPDATED


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    car_id = entry.data["car_id"]
    name = entry.data["name"]
    async_add_entities([CarSavingBinarySensor(hass, car_id, name)], update_before_add=True)


class CarSavingBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:content-save"

    def __init__(self, hass: HomeAssistant, car_id: str, car_name: str):
        self.hass = hass
        self.car_id = car_id
        self._attr_name = "Opslaan bezig"
        self._attr_unique_id = f"{car_id}_saving"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, car_id)},
            "name": car_name,
            "manufacturer": "CarLog",
            "model": "Virtual Car",
        }
        self._unsub = None

    def _rt(self) -> dict:
        return self.hass.data.get(DOMAIN, {}).get("runtime", {}).get(self.car_id, {})

    @property
    def is_on(self) -> bool:
        return bool(self._rt().get("saving", False))

    @property
    def extra_state_attributes(self):
        rt = self._rt()
        return {
            "state": rt.get("state", "idle"),
            "message": rt.get("message", ""),
            "ts": rt.get("ts"),
        }

    async def async_added_to_hass(self) -> None:
        self._unsub = async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    def _handle_update(self) -> None:
        self.async_write_ha_state()
