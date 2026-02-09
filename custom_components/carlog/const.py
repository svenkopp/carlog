DOMAIN = "carlog"
STORAGE_KEY = "carlog_data"
STORAGE_VERSION = 1

DEFAULT_MAINTENANCE_TYPES = {
    "oil": {"label": "Olie", "interval_km": 15000, "interval_days": 365},
    "tires": {"label": "Banden wissel", "interval_km": 35000, "interval_days": 2136},
    "brakes": {"label": "Remmen", "interval_km": 60000, "interval_days": 730},
}
