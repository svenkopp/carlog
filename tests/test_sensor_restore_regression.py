from pathlib import Path
import unittest


SENSOR_FILE = Path("custom_components/carlog/sensor.py")


class TestSensorRestoreRegression(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SENSOR_FILE.read_text(encoding="utf-8")

    def test_native_attrs_none_is_guarded(self) -> None:
        self.assertIn(
            "self._restored_attrs = dict(last_sensor_data.native_attrs or {})",
            self.source,
        )

    def test_last_state_attribute_fallback_exists(self) -> None:
        self.assertIn("last_state = await self.async_get_last_state()", self.source)
        self.assertIn("if last_state is not None and not self._restored_attrs:", self.source)
        self.assertIn("self._restored_attrs = dict(last_state.attributes)", self.source)

    def test_save_status_has_safe_idle_fallback(self) -> None:
        self.assertIn('return str(restored) if restored is not None else "idle"', self.source)


if __name__ == "__main__":
    unittest.main()
