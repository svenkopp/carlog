from __future__ import annotations

import re

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN


def _normalize_license_plate(value: str) -> str:
    return re.sub(r"-", "", value).upper().strip()


class CarLogConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3

    async def async_step_user(self, user_input=None):
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("car_id"): str,
                    vol.Required("license_plate"): str,
                    vol.Optional("tank_capacity_l"): vol.Coerce(float),
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        await self.async_set_unique_id(user_input["car_id"])
        self._abort_if_unique_id_configured()

        data = {
            "name": user_input["name"],
            "car_id": user_input["car_id"],
            "license_plate": _normalize_license_plate(user_input["license_plate"]),
        }
        if "tank_capacity_l" in user_input and user_input["tank_capacity_l"] is not None:
            data["tank_capacity_l"] = float(user_input["tank_capacity_l"])

        return self.async_create_entry(title=user_input["name"], data=data)
