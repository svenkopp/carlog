from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN


class CarLogConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("car_id"): str,
                    vol.Optional("tank_capacity_l"): vol.Coerce(float),
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        await self.async_set_unique_id(user_input["car_id"])
        self._abort_if_unique_id_configured()

        data = {"name": user_input["name"], "car_id": user_input["car_id"]}
        if "tank_capacity_l" in user_input and user_input["tank_capacity_l"] is not None:
            data["tank_capacity_l"] = float(user_input["tank_capacity_l"])

        return self.async_create_entry(title=user_input["name"], data=data)
