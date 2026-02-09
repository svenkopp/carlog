from __future__ import annotations

import datetime as dt
import logging
import re
from urllib.parse import quote

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfLength, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .__init__ import SIGNAL_UPDATED


_LOGGER = logging.getLogger(__name__)
_RDW_URL = "https://opendata.rdw.nl/resource/vkij-7mwc.json?$query={query}"


def _normalize_license_plate(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"-", "", value).upper().strip()


def _fuel_stats(fuel_logs: list[dict]) -> dict:
    if len(fuel_logs) < 2:
        return {"avg_l_per_100km": None, "last": fuel_logs[-1] if fuel_logs else None}

    logs = sorted(fuel_logs, key=lambda x: x.get("ts", ""))
    total_l = 0.0
    total_km = 0.0

    for prev, cur in zip(logs[:-1], logs[1:]):
        dk = float(cur.get("odometer_km", 0)) - float(prev.get("odometer_km", 0))
        if dk <= 0:
            continue
        total_km += dk
        total_l += float(cur.get("liters", 0))

    avg = (total_l / total_km * 100.0) if total_km > 0 else None
    return {"avg_l_per_100km": avg, "last": logs[-1]}


def _last_maintenance(maint_logs: list[dict]) -> dict | None:
    if not maint_logs:
        return None
    logs = sorted(maint_logs, key=lambda x: x.get("ts", ""))
    return logs[-1]


def _parse_ts(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _maintenance_due(meta: dict, maint_type: str, maint_logs: list[dict], odometer_km: float | None) -> dict:
    defaults = meta.get("maintenance_defaults", {})
    rule = defaults.get(maint_type, {})
    interval_km = rule.get("interval_km")
    interval_days = rule.get("interval_days")

    last = _last_maintenance(maint_logs)
    now = dt.datetime.now(dt.timezone.utc)

    due_km = None
    due_date = None
    is_due = False

    if last and interval_km is not None and odometer_km is not None:
        due_at_km = float(last.get("odometer_km", 0)) + float(interval_km)
        due_km = max(0.0, due_at_km - float(odometer_km))
        if float(odometer_km) >= due_at_km:
            is_due = True

    if last and interval_days is not None:
        last_dt = _parse_ts(last["ts"])
        due_dt = last_dt + dt.timedelta(days=int(interval_days))
        due_date = due_dt.date().isoformat()
        if now >= due_dt:
            is_due = True

    return {
        "is_due": is_due,
        "km_remaining": due_km,
        "due_date": due_date,
        "last_done_km": last.get("odometer_km") if last else None,
        "last_done_ts": last.get("ts") if last else None,
        "label": rule.get("label", maint_type),
        "interval_km": interval_km,
        "interval_days": interval_days,
    }


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    car_id = entry.data["car_id"]
    name = entry.data["name"]
    license_plate = _normalize_license_plate(entry.data.get("license_plate"))

    async_add_entities(
        [
            CarOdometerSensor(hass, car_id, name),
            CarFuelAvgSensor(hass, car_id, name),
            CarEstimatedRangeSensor(hass, car_id, name),
            CarLastFuelSensor(hass, car_id, name),
            CarSaveStatusSensor(hass, car_id, name),
            CarMaintenanceDueSensor(hass, car_id, name, "oil"),
            CarMaintenanceDueSensor(hass, car_id, name, "tires"),
            CarMaintenanceDueSensor(hass, car_id, name, "brakes"),
            CarApkExpirySensor(hass, car_id, name, license_plate),
        ],
        update_before_add=True,
    )


class _CarBaseSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, car_id: str, car_name: str):
        self.hass = hass
        self.car_id = car_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, car_id)},
            "name": car_name,
            "manufacturer": "CarLog",
            "model": "Virtual Car",
        }
        self._unsub = None

    def _get_car(self) -> dict:
        return self.hass.data[DOMAIN]["data"].get("cars", {}).get(
            self.car_id, {"fuel": [], "maintenance": {}, "meta": {}, "ui": {}}
        )

    async def async_added_to_hass(self) -> None:
        self._unsub = async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    def _handle_update(self) -> None:
        self.async_write_ha_state()


class CarOdometerSensor(_CarBaseSensor):
    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS

    def __init__(self, hass, car_id, car_name):
        super().__init__(hass, car_id, car_name)
        self._attr_name = "Kilometerstand"
        self._attr_unique_id = f"{car_id}_odometer"

    @property
    def native_value(self):
        car = self._get_car()
        return car.get("meta", {}).get("odometer_km")


class CarFuelAvgSensor(_CarBaseSensor):
    _attr_icon = "mdi:gas-station"
    _attr_native_unit_of_measurement = "L/100km"

    def __init__(self, hass, car_id, car_name):
        super().__init__(hass, car_id, car_name)
        self._attr_name = "Gemiddeld verbruik"
        self._attr_unique_id = f"{car_id}_fuel_avg"

    @property
    def native_value(self):
        car = self._get_car()
        stats = _fuel_stats(car.get("fuel", []))
        avg = stats["avg_l_per_100km"]
        return round(avg, 2) if avg is not None else None

    @property
    def extra_state_attributes(self):
        car = self._get_car()
        return {"tankbeurten": len(car.get("fuel", []))}


class CarEstimatedRangeSensor(_CarBaseSensor):
    _attr_icon = "mdi:map-marker-distance"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS

    def __init__(self, hass, car_id, car_name):
        super().__init__(hass, car_id, car_name)
        self._attr_name = "Gemiddelde actieradius"
        self._attr_unique_id = f"{car_id}_range_estimated"

    @property
    def native_value(self):
        car = self._get_car()
        meta = car.get("meta", {})
        cap = meta.get("tank_capacity_l")
        if cap is None:
            return None

        stats = _fuel_stats(car.get("fuel", []))
        avg = stats["avg_l_per_100km"]
        if avg is None or avg <= 0:
            return None

        rng = float(cap) * 100.0 / float(avg)
        return round(rng, 0)

    @property
    def extra_state_attributes(self):
        car = self._get_car()
        meta = car.get("meta", {})
        cap = meta.get("tank_capacity_l")
        stats = _fuel_stats(car.get("fuel", []))
        avg = stats["avg_l_per_100km"]
        return {
            "tank_capacity_l": cap,
            "avg_l_per_100km": round(avg, 2) if avg is not None else None,
            "formula": "tank_capacity_l * 100 / avg_l_per_100km",
        }


class CarLastFuelSensor(_CarBaseSensor):
    _attr_icon = "mdi:receipt"
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS

    def __init__(self, hass, car_id, car_name):
        super().__init__(hass, car_id, car_name)
        self._attr_name = "Laatste tankbeurt liters"
        self._attr_unique_id = f"{car_id}_fuel_last_liters"

    @property
    def native_value(self):
        car = self._get_car()
        stats = _fuel_stats(car.get("fuel", []))
        last = stats["last"]
        return round(float(last.get("liters", 0)), 2) if last else None

    @property
    def extra_state_attributes(self):
        car = self._get_car()
        stats = _fuel_stats(car.get("fuel", []))
        last = stats["last"]
        if not last:
            return {}
        return {
            "odometer_km": last.get("odometer_km"),
            "ts": last.get("ts"),
            "price_total": last.get("price_total"),
        }


class CarMaintenanceDueSensor(_CarBaseSensor):
    _attr_icon = "mdi:wrench"

    def __init__(self, hass, car_id, car_name, maint_type: str):
        super().__init__(hass, car_id, car_name)
        self.maint_type = maint_type
        self._attr_name = f"{maint_type} onderhoud due"
        self._attr_unique_id = f"{car_id}_maint_due_{maint_type}"

    @property
    def native_value(self):
        car = self._get_car()
        meta = car.get("meta", {})
        odometer_km = meta.get("odometer_km")
        maint_logs = car.get("maintenance", {}).get(self.maint_type, [])
        due = _maintenance_due(meta, self.maint_type, maint_logs, odometer_km)
        return due["is_due"]

    @property
    def extra_state_attributes(self):
        car = self._get_car()
        meta = car.get("meta", {})
        odometer_km = meta.get("odometer_km")
        maint_logs = car.get("maintenance", {}).get(self.maint_type, [])
        return _maintenance_due(meta, self.maint_type, maint_logs, odometer_km)


class CarSaveStatusSensor(_CarBaseSensor):
    _attr_icon = "mdi:information-outline"

    def __init__(self, hass, car_id, car_name):
        super().__init__(hass, car_id, car_name)
        self._attr_name = "Opslaan status"
        self._attr_unique_id = f"{car_id}_save_status"

    def _rt(self) -> dict:
        return self.hass.data.get(DOMAIN, {}).get("runtime", {}).get(self.car_id, {})

    @property
    def native_value(self):
        return self._rt().get("state", "idle")

    @property
    def extra_state_attributes(self):
        rt = self._rt()
        return {"message": rt.get("message", ""), "ts": rt.get("ts")}


class CarApkExpirySensor(_CarBaseSensor):
    _attr_icon = "mdi:calendar-check"

    def __init__(self, hass, car_id, car_name, license_plate: str | None):
        super().__init__(hass, car_id, car_name)
        self._attr_name = "APK vervaldatum"
        self._attr_unique_id = f"{car_id}_apk_expiry"
        self._license_plate = license_plate
        self._attr_native_value = None
        self._attr_extra_state_attributes = {"license_plate": license_plate}
        self._last_fetch_at: dt.datetime | None = None
        self._fetch_interval = dt.timedelta(hours=24)

    @property
    def should_poll(self) -> bool:
        return True

    async def async_update(self) -> None:
        if not self._license_plate:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {"license_plate": None, "status": "license_plate_missing"}
            return

        now = dt.datetime.now(dt.timezone.utc)
        if self._last_fetch_at and (now - self._last_fetch_at) < self._fetch_interval:
            return

        query = quote(
            f'SELECT `kenteken`, `vervaldatum_keuring`, `vervaldatum_keuring_dt` WHERE '
            f'caseless_one_of(`kenteken`, "{self._license_plate}")'
        )
        url = _RDW_URL.format(query=query)
        session = async_get_clientsession(self.hass)

        try:
            response = await session.get(url, timeout=10)
            response.raise_for_status()
            payload = await response.json()
        except Exception as err:
            _LOGGER.warning("Could not load APK expiry for %s: %s", self._license_plate, err)
            self._attr_native_value = None
            self._attr_extra_state_attributes = {"license_plate": self._license_plate, "status": "fetch_error"}
            return

        if not payload:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {"license_plate": self._license_plate, "status": "not_found"}
            return

        row = payload[0]
        iso_value = row.get("vervaldatum_keuring_dt")
        if iso_value:
            self._attr_native_value = dt.date.fromisoformat(iso_value[:10])
        else:
            self._attr_native_value = None

        self._attr_extra_state_attributes = {
            "license_plate": self._license_plate,
            "kenteken": row.get("kenteken"),
            "vervaldatum_keuring": row.get("vervaldatum_keuring"),
            "status": "ok",
            "last_fetch": now.isoformat(),
        }
        self._last_fetch_at = now
