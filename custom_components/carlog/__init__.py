from __future__ import annotations

import datetime as dt
import re

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, DEFAULT_MAINTENANCE_TYPES

SIGNAL_UPDATED = f"{DOMAIN}_updated"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.TEXT,
    Platform.SELECT,
    Platform.DATE,
    Platform.BUTTON,
]


def _ensure_car(data: dict, car_id: str) -> dict:
    cars = data.setdefault("cars", {})
    return cars.setdefault(car_id, {"fuel": [], "maintenance": {}, "meta": {}, "ui": {}})


def _normalize_license_plate(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"-", "", value).upper().strip()


def _ensure_ui_defaults(car: dict) -> None:
    ui = car.setdefault("ui", {})
    ui.setdefault("odometer_km", car.get("meta", {}).get("odometer_km"))
    ui.setdefault("liters", 0.0)
    ui.setdefault("price_total", 0.0)
    ui.setdefault("note", "")
    ui.setdefault("maint_type", "oil")
    ui.setdefault("maint_date", None)  # "YYYY-MM-DD" or None


def _find_by_ts(items: list[dict], ts: str) -> int | None:
    for i, it in enumerate(items):
        if it.get("ts") == ts:
            return i
    return None


def set_runtime_status(hass: HomeAssistant, car_id: str, saving: bool, state: str, message: str | None = None) -> None:
    """Runtime-only status for UI feedback (not persistent)."""
    rt = hass.data.setdefault(DOMAIN, {}).setdefault("runtime", {})
    car_rt = rt.setdefault(car_id, {})
    car_rt["saving"] = saving
    car_rt["state"] = state  # idle/saving/saved/error
    car_rt["message"] = message or ""
    car_rt["ts"] = dt.datetime.now(dt.timezone.utc).isoformat()
    async_dispatcher_send(hass, SIGNAL_UPDATED)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    hass.data[DOMAIN]["store"] = store
    hass.data[DOMAIN]["data"] = await store.async_load() or {"cars": {}}
    hass.data[DOMAIN].setdefault("runtime", {})

    async def _save() -> None:
        await store.async_save(hass.data[DOMAIN]["data"])
        async_dispatcher_send(hass, SIGNAL_UPDATED)

    async def handle_log_fuel(call: ServiceCall) -> None:
        car_id = call.data["car_id"]
        km = float(call.data["odometer_km"])
        liters = float(call.data["liters"])
        price_total = call.data.get("price_total")
        ts = dt.datetime.now(dt.timezone.utc).isoformat()

        car = _ensure_car(hass.data[DOMAIN]["data"], car_id)
        _ensure_ui_defaults(car)

        car["fuel"].append(
            {
                "ts": ts,
                "odometer_km": km,
                "liters": liters,
                "price_total": float(price_total) if price_total is not None else None,
            }
        )

        car.setdefault("meta", {})["odometer_km"] = km
        car.setdefault("ui", {})["odometer_km"] = km

        await _save()

    async def handle_log_maintenance(call: ServiceCall) -> None:
        car_id = call.data["car_id"]
        maint_type = call.data["type"]
        km = float(call.data["odometer_km"])
        note = call.data.get("note", "")
        date_str = call.data.get("date")  # optional YYYY-MM-DD

        now_utc = dt_util.utcnow()

        if date_str:
            local_tz = dt_util.as_local(now_utc).tzinfo
            y, m, d = [int(x) for x in date_str.split("-")]
            local_dt = dt.datetime(y, m, d, 12, 0, 0, tzinfo=local_tz)
            ts_dt_utc = local_dt.astimezone(dt.timezone.utc)
            ts = ts_dt_utc.isoformat()
            update_odometer = ts_dt_utc >= now_utc
        else:
            ts = dt.datetime.now(dt.timezone.utc).isoformat()
            update_odometer = True

        car = _ensure_car(hass.data[DOMAIN]["data"], car_id)
        _ensure_ui_defaults(car)

        mt = car.setdefault("maintenance", {}).setdefault(maint_type, [])
        mt.append({"ts": ts, "odometer_km": km, "note": note})

        if update_odometer:
            car.setdefault("meta", {})["odometer_km"] = km
            car.setdefault("ui", {})["odometer_km"] = km

        await _save()

    async def handle_delete_fuel_entry(call: ServiceCall) -> None:
        car_id = call.data["car_id"]
        ts = call.data.get("ts")

        car = _ensure_car(hass.data[DOMAIN]["data"], car_id)
        fuel = car.get("fuel", [])
        if not fuel:
            return

        if ts:
            idx = _find_by_ts(fuel, ts)
            if idx is None:
                return
            fuel.pop(idx)
        else:
            fuel.sort(key=lambda x: x.get("ts", ""))
            fuel.pop(-1)

        await _save()

    async def handle_update_fuel_entry(call: ServiceCall) -> None:
        car_id = call.data["car_id"]
        ts = call.data["ts"]

        car = _ensure_car(hass.data[DOMAIN]["data"], car_id)
        fuel = car.get("fuel", [])

        idx = _find_by_ts(fuel, ts)
        if idx is None:
            return

        entry = fuel[idx]

        if call.data.get("odometer_km") is not None:
            entry["odometer_km"] = float(call.data["odometer_km"])
            car.setdefault("meta", {})["odometer_km"] = entry["odometer_km"]
            car.setdefault("ui", {})["odometer_km"] = entry["odometer_km"]

        if call.data.get("liters") is not None:
            entry["liters"] = float(call.data["liters"])

        if "price_total" in call.data:
            pt = call.data.get("price_total")
            entry["price_total"] = float(pt) if pt is not None else None

        await _save()

    async def handle_delete_maintenance_entry(call: ServiceCall) -> None:
        car_id = call.data["car_id"]
        maint_type = call.data["type"]
        ts = call.data.get("ts")

        car = _ensure_car(hass.data[DOMAIN]["data"], car_id)
        mt = car.setdefault("maintenance", {}).setdefault(maint_type, [])
        if not mt:
            return

        if ts:
            idx = _find_by_ts(mt, ts)
            if idx is None:
                return
            mt.pop(idx)
        else:
            mt.sort(key=lambda x: x.get("ts", ""))
            mt.pop(-1)

        await _save()

    async def handle_update_maintenance_entry(call: ServiceCall) -> None:
        car_id = call.data["car_id"]
        maint_type = call.data["type"]
        ts = call.data["ts"]

        car = _ensure_car(hass.data[DOMAIN]["data"], car_id)
        mt = car.setdefault("maintenance", {}).setdefault(maint_type, [])

        idx = _find_by_ts(mt, ts)
        if idx is None:
            return

        entry = mt[idx]

        now_utc = dt_util.utcnow()
        update_odometer = True

        date_str = call.data.get("date")
        if date_str:
            local_tz = dt_util.as_local(now_utc).tzinfo
            y, m, d = [int(x) for x in date_str.split("-")]
            local_dt = dt.datetime(y, m, d, 12, 0, 0, tzinfo=local_tz)
            ts_dt_utc = local_dt.astimezone(dt.timezone.utc)
            entry["ts"] = ts_dt_utc.isoformat()
            update_odometer = ts_dt_utc >= now_utc

        if call.data.get("odometer_km") is not None:
            entry["odometer_km"] = float(call.data["odometer_km"])
            if update_odometer:
                car.setdefault("meta", {})["odometer_km"] = entry["odometer_km"]
                car.setdefault("ui", {})["odometer_km"] = entry["odometer_km"]

        if "note" in call.data:
            entry["note"] = call.data.get("note", "")

        await _save()

    hass.services.async_register(DOMAIN, "log_fuel", handle_log_fuel)
    hass.services.async_register(DOMAIN, "log_maintenance", handle_log_maintenance)
    hass.services.async_register(DOMAIN, "delete_fuel_entry", handle_delete_fuel_entry)
    hass.services.async_register(DOMAIN, "update_fuel_entry", handle_update_fuel_entry)
    hass.services.async_register(DOMAIN, "delete_maintenance_entry", handle_delete_maintenance_entry)
    hass.services.async_register(DOMAIN, "update_maintenance_entry", handle_update_maintenance_entry)

    return True


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    if "store" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["store"] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        hass.data[DOMAIN]["data"] = await hass.data[DOMAIN]["store"].async_load() or {"cars": {}}
    hass.data[DOMAIN].setdefault("runtime", {})

    car_id = entry.data["car_id"]
    name = entry.data["name"]

    car = _ensure_car(hass.data[DOMAIN]["data"], car_id)
    meta = car.setdefault("meta", {})
    meta["name"] = name
    meta.setdefault("maintenance_defaults", DEFAULT_MAINTENANCE_TYPES)
    meta["license_plate"] = _normalize_license_plate(entry.data.get("license_plate"))

    # Backwards compatible tank capacity
    if "tank_capacity_l" in entry.data and entry.data["tank_capacity_l"] is not None:
        meta.setdefault("tank_capacity_l", float(entry.data["tank_capacity_l"]))
    else:
        meta.setdefault("tank_capacity_l", None)

    _ensure_ui_defaults(car)

    # runtime defaults
    rt = hass.data[DOMAIN]["runtime"].setdefault(car_id, {})
    rt.setdefault("saving", False)
    rt.setdefault("state", "idle")
    rt.setdefault("message", "")
    rt.setdefault("ts", None)

    await hass.data[DOMAIN]["store"].async_save(hass.data[DOMAIN]["data"])

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry) -> bool:
    """Migrate old config entries to new versions (backwards compatible)."""
    hass.data.setdefault(DOMAIN, {})

    # Ensure store/data are available during migration
    if "store" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["store"] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        hass.data[DOMAIN]["data"] = await hass.data[DOMAIN]["store"].async_load() or {"cars": {}}
    hass.data[DOMAIN].setdefault("runtime", {})

    current_version = entry.version or 1

    if current_version < 2:
        new_data = dict(entry.data)

        car_id = entry.data.get("car_id")
        tank_from_storage = None
        if car_id:
            car = hass.data[DOMAIN]["data"].get("cars", {}).get(car_id, {})
            tank_from_storage = car.get("meta", {}).get("tank_capacity_l")

        if "tank_capacity_l" not in new_data and tank_from_storage is not None:
            new_data["tank_capacity_l"] = float(tank_from_storage)

        hass.config_entries.async_update_entry(entry, data=new_data, version=2)
        current_version = 2

    if current_version < 3:
        new_data = dict(entry.data)
        new_data["license_plate"] = _normalize_license_plate(new_data.get("license_plate"))
        hass.config_entries.async_update_entry(entry, data=new_data, version=3)

    return True
