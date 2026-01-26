from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .__init__ import SIGNAL_UPDATED


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    car_id = entry.data["car_id"]
    name = entry.data["name"]
    async_add_entities(
        [
            CarUiNumber(hass, car_id, name, "odometer_km", "Kilometerstand (invoer)", 0, 999999, 1, "km", "mdi:speedometer"),
            CarUiNumber(hass, car_id, name, "liters", "Liters (invoer)", 0, 200, 0.1, "L", "mdi:gas-station"),
            CarUiNumber(hass, car_id, name, "price_total", "Totaalprijs (invoer)", 0, 9999, 0.01, "EUR", "mdi:currency-eur"),
            CarTankCapacityNumber(hass, car_id, name),
        ],
        update_before_add=True,
    )


class CarUiNumber(NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, car_id: str, car_name: str, key: str, title: str,
                 min_v: float, max_v: float, step: float, unit: str | None, icon: str):
        self.hass = hass
        self.car_id = car_id
        self.key = key
        self._attr_name = title
        self._attr_unique_id = f"{car_id}_ui_{key}"
        self._attr_native_min_value = min_v
        self._attr_native_max_value = max_v
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
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
        return self._car().setdefault("ui", {}).get(self.key)

    async def async_set_native_value(self, value: float) -> None:
        car = self._car()
        car.setdefault("ui", {})[self.key] = float(value)
        await self.hass.data[DOMAIN]["store"].async_save(self.hass.data[DOMAIN]["data"])
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self._unsub = async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    def _handle_update(self) -> None:
        self.async_write_ha_state()


class CarTankCapacityNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:gas-station-outline"
    _attr_native_unit_of_measurement = "L"
    _attr_native_min_value = 0
    _attr_native_max_value = 200
    _attr_native_step = 0.1

    def __init__(self, hass: HomeAssistant, car_id: str, car_name: str):
        self.hass = hass
        self.car_id = car_id
        self._attr_name = "Tankinhoud"
        self._attr_unique_id = f"{car_id}_tank_capacity_l"
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
        cap = self._car().setdefault("meta", {}).get("tank_capacity_l")
        return float(cap) if cap is not None else None

    async def async_set_native_value(self, value: float) -> None:
        car = self._car()
        car.setdefault("meta", {})["tank_capacity_l"] = float(value)
        await self.hass.data[DOMAIN]["store"].async_save(self.hass.data[DOMAIN]["data"])
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self._unsub = async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    def _handle_update(self) -> None:
        self.async_write_ha_state()
