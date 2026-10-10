"""Constants for the Vacuum Water Level integration."""

DOMAIN = "vacuum_water_level"

# Storage
STORAGE_KEY = "vacuum_water_level"
STORAGE_VERSION = 1
STORAGE_MINOR_VERSION = 1

# Config flow keys
CONF_VACUUM_ENTITY = "vacuum_entity"
CONF_CLEAN_TANK_CAPACITY = "clean_tank_capacity_ml"
CONF_DIRTY_TANK_CAPACITY = "dirty_tank_capacity_ml"
CONF_WATER_LOW_THRESHOLD = "water_low_threshold"
CONF_WASTE_FULL_THRESHOLD = "waste_full_threshold"

# Companion entity keys
CONF_CLEANING_ENTITY = "cleaning_entity"
CONF_AREA_ENTITY = "area_entity"
CONF_STATUS_ENTITY = "status_entity"
CONF_MOP_MODE_ENTITY = "mop_mode_entity"
CONF_MOP_INTENSITY_ENTITY = "mop_intensity_entity"
CONF_DOCK_ERROR_ENTITY = "dock_error_entity"
CONF_CLEAN_WATER_SENSOR = "clean_water_sensor"
CONF_DIRTY_WATER_SENSOR = "dirty_water_sensor"

# Defaults
DEFAULT_CLEAN_TANK_CAPACITY = 250
DEFAULT_DIRTY_TANK_CAPACITY = 250
DEFAULT_WATER_LOW_THRESHOLD = 15
DEFAULT_WASTE_FULL_THRESHOLD = 85
DEFAULT_BASE_ML_PER_M2 = 2.0
DEFAULT_WASH_VOLUME_ML = 50.0
DEFAULT_WASTE_RATIO = 0.5
DEFAULT_CLEAN_RESERVE_ML = 0.0
DEFAULT_DIRTY_RESERVE_ML = 0.0

# EWMA learning rates
EWMA_ALPHA_RESERVE = 0.3
EWMA_ALPHA_CORRECTION = 0.2
EWMA_ALPHA_WASH_VOLUME = 0.15

# Mop intensity multipliers
MOP_INTENSITY_MULTIPLIERS = {
    "low": 0.7,
    "medium": 1.0,
    "high": 1.3,
    "max": 1.5,
    "mild": 0.7,
    "moderate": 1.0,
    "intense": 1.3,
    "custom": 1.0,
}

# Sensor keys
SENSOR_WATER_REMAINING_PCT = "water_remaining_pct"
SENSOR_WATER_REMAINING_ML = "water_remaining_ml"
SENSOR_WATER_USED_SINCE_REFILL = "water_used_since_refill"
SENSOR_WASTE_TANK_PCT = "waste_tank_pct"
SENSOR_WASTE_TANK_ML = "waste_tank_ml"
SENSOR_LAST_REFILL = "last_refill"
SENSOR_LAST_WASTE_EMPTY = "last_waste_empty"
SENSOR_PREDICTION_DIAGNOSTICS = "prediction_diagnostics"
SENSOR_WATER_CONSUMPTION_RATE = "water_consumption_rate"
SENSOR_DIRTY_WATER_FILL_RATE = "dirty_water_fill_rate"

# Binary sensor keys
BINARY_WATER_LOW = "water_low"
BINARY_WASTE_FULL = "waste_tank_full"

# Button keys
BUTTON_REFILLED = "refilled"
BUTTON_WASTE_EMPTIED = "waste_tank_emptied"
BUTTON_CLEAR_MODEL = "clear_prediction_model"

# Warning latch keys
KEY_CLEAN_WARNING_LATCHED = "clean_warning_latched"
KEY_DIRTY_WARNING_LATCHED = "dirty_warning_latched"
KEY_LAST_CLEANING_STATE = "last_cleaning_state"
KEY_LAST_AREA = "last_area"
KEY_LAST_MOP_MODE = "last_mop_mode"
KEY_LAST_MOP_INTENSITY = "last_mop_intensity"
KEY_WASH_COUNT = "wash_count"

# Vendor list
SUPPORTED_VENDORS = [
    "Roborock",
    "Dreame",
    "Ecovacs",
    "Narwal",
    "Xiaomi",
    "Eufy",
    "Samsung",
    "Other",
]
