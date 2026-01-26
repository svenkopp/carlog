from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .__init__ import set_runtime_status


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    car_id = entry.data["car_id"]
    name = entry.data["name"]
    async_add_entities(
        [
            CarLogFuelButton(hass, car_id, name),
            CarLogMaintButton(hass, car_id, name),
        ],
        update_before_add=True,
    )


class _BaseButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, car_id: str, car_name: str, title: str, icon: str, uid_suffix: str):
        self.hass = hass
        self.car_id = car_id
        self._attr_name = title
        self._attr_icon = icon
        self._attr_unique_id = f"{car_id}_{uid_suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, car_id)},
            "name": car_name,
            "manufacturer": "CarLog",
            "model": "Virtual Car",
        }

    def _car(self) -> dict:
        return self.hass.data[DOMAIN]["data"]["cars"].setdefault(
            self.car_id, {"fuel": [], "maintenance": {}, "meta": {}, "ui": {}}
        )


class CarLogFuelButton(_BaseButton):
    def __init__(self, hass: HomeAssistant, car_id: str, car_name: str):
        super().__init__(hass, car_id, car_name, "Log tankbeurt", "mdi:gas-station", "btn_log_fuel")

    async def async_press(self) -> None:
        car = self._car()
        ui = car.setdefault("ui", {})

        km = ui.get("odometer_km")
        liters = ui.get("liters", 0.0)
        price = ui.get("price_total", 0.0)

        # Validatie
        if km is None:
            set_runtime_status(self.hass, self.car_id, False, "error", "Kilometerstand ontbreekt")
            return

        try:
            km_f = float(km)
            liters_f = float(liters)
        except (TypeError, ValueError):
            set_runtime_status(self.hass, self.car_id, False, "error", "Ongeldige km-stand of liters")
            return

        if liters_f <= 0:
            set_runtime_status(self.hass, self.car_id, False, "error", "Liters moet groter zijn dan 0")
            return

        # Check: km én liters moeten beide anders zijn dan vorige tankbeurt
        fuel_logs = car.get("fuel", [])
        if fuel_logs:
            last = sorted(fuel_logs, key=lambda x: x.get("ts", ""))[-1]
            try:
                last_km = float(last.get("odometer_km", -1))
                last_l = float(last.get("liters", -1))
                if abs(km_f - last_km) < 0.0001 or abs(liters_f - last_l) < 0.0001:
                    set_runtime_status(
                        self.hass,
                        self.car_id,
                        False,
                        "error",
                        "Niet opgeslagen: km én liters moeten beide anders zijn dan vorige tankbeurt",
                    )
                    return
            except Exception:
                # Als parsing faalt: niet blokkeren
                pass

        set_runtime_status(self.hass, self.car_id, True, "saving", "Bezig met opslaan…")

        data = {"car_id": self.car_id, "odometer_km": km_f, "liters": liters_f}
        if price and float(price) > 0:
            data["price_total"] = float(price)

        try:
            await self.hass.services.async_call(DOMAIN, "log_fuel", data, blocking=True)
        except Exception as e:
            set_runtime_status(self.hass, self.car_id, False, "error", f"Opslaan mislukt: {e}")
            return

        # Reset invoer na succesvolle opslag
        ui["liters"] = 0.0
        ui["price_total"] = 0.0
        await self.hass.data[DOMAIN]["store"].async_save(self.hass.data[DOMAIN]["data"])

        set_runtime_status(self.hass, self.car_id, False, "saved", "Opgeslagen ✅")


class CarLogMaintButton(_BaseButton):
    def __init__(self, hass: HomeAssistant, car_id: str, car_name: str):
        super().__init__(hass, car_id, car_name, "Log onderhoud", "mdi:wrench", "btn_log_maint")

    async def async_press(self) -> None:
        car = self._car()
        ui = car.setdefault("ui", {})

        km = ui.get("odometer_km")
        maint_type = ui.get("maint_type", "oil")
        note = ui.get("note", "")
        date_str = ui.get("maint_date")  # "YYYY-MM-DD" of None

        if km is None:
            set_runtime_status(self.hass, self.car_id, False, "error", "Kilometerstand ontbreekt")
            return

        try:
            km_f = float(km)
        except (TypeError, ValueError):
            set_runtime_status(self.hass, self.car_id, False, "error", "Ongeldige kilometerstand")
            return

        set_runtime_status(self.hass, self.car_id, True, "saving", "Bezig met opslaan…")

        data = {"car_id": self.car_id, "type": maint_type, "odometer_km": km_f, "note": note}
        if date_str:
            data["date"] = date_str

        try:
            await self.hass.services.async_call(DOMAIN, "log_maintenance", data, blocking=True)
        except Exception as e:
            set_runtime_status(self.hass, self.car_id, False, "error", f"Opslaan mislukt: {e}")
            return

        # Reset notitie & datum, km/type laten staan
        ui["note"] = ""
        ui["maint_date"] = None
        await self.hass.data[DOMAIN]["store"].async_save(self.hass.data[DOMAIN]["data"])

        set_runtime_status(self.hass, self.car_id, False, "saved", "Opgeslagen ✅")
