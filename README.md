# Vacuum Water Level

A Home Assistant custom integration that estimates **clean water tank level** and **dirty/waste water tank fill level** for robot vacuums that do not expose actual tank levels.

## How It Works

The integration works **without additional hardware** by combining:

1. **Area-based water consumption estimation** - Water usage is estimated based on cleaned area (m²), mop intensity, and mop mode
2. **Mop washing event tracking** - Each mop wash event adds to estimated water consumption
3. **Adaptive learning** - The system learns and improves over time using EWMA (Exponentially Weighted Moving Average)
4. **Reserve volume learning** - Learns the "reserve" volume that remains when the vacuum generates a water low or waste tank full warning
5. **Independent waste tracking** - Waste water is tracked independently, not assumed to equal clean water consumed

## Key Features

- **Vendor-neutral** - Works with Roborock, Dreame, Ecovacs, Narwal, Xiaomi, Eufy, Samsung, and future vendors
- **Self-learning** - Improves accuracy over time through adaptive correction factors
- **Multi-vacuum support** - Each vacuum gets its own config entry, storage, and models
- **Configurable via Config Flow** - All settings are configurable through the Home Assistant UI
- **Auto-discovery** - Automatically discovers companion entities (cleaning sensor, area sensor, mop mode, etc.)
- **Survives restarts** - All learning data is stored using Home Assistant storage
- **Native entities** - Uses only native HA entities (sensors, binary sensors, buttons) - no custom Lovelace card needed

## Supported Vendors

The integration does not hardcode any vendor-specific logic. It uses heuristic entity discovery based on entity names, domains, and device associations.

- Roborock
- Dreame
- Ecovacs
- Narwal
- Xiaomi
- Eufy
- Samsung
- Future vendors (auto-discovery works with any vendor)

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Search for "Vacuum Water Level" in HACS
3. Install the integration
4. Restart Home Assistant
5. Go to Settings → Devices & Services → Add Integration → "Vacuum Water Level"

### Manual

1. Copy the `custom_components/vacuum_water_level` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration → "Vacuum Water Level"

## Configuration

### Step 1: Select Vacuum

- Choose your vacuum entity
- Set clean water tank capacity (mL)
- Set dirty water tank capacity (mL)
- Set water low warning threshold (%)
- Set waste tank full threshold (%)

### Step 2: Companion Entity Discovery

The integration will auto-discover companion entities. You can keep the discovered values or override any of them:

- **Cleaning binary sensor** - Detects when the vacuum is cleaning
- **Cleaned area sensor** - Tracks area cleaned in m²
- **Status sensor** - Vacuum status (alternative cleaning detection)
- **Mop mode entity** - Mop on/off state
- **Mop intensity entity** - Mop intensity level
- **Dock error sensor** - Dock error/warning state
- **Clean water box sensor** - Binary sensor for water low
- **Dirty water box sensor** - Binary sensor for waste tank full

All entity selections remain editable after setup via the integration's Options flow.

## Entities Created

### Sensors

| Entity | Description |
|--------|-------------|
| Water Remaining (%) | Estimated clean water remaining percentage |
| Water Remaining (mL) | Estimated clean water remaining in mL |
| Water Used Since Refill | Total water used since last refill |
| Waste Tank (%) | Estimated waste tank fill percentage |
| Waste Tank (mL) | Estimated waste tank fill in mL |
| Last Refill | Timestamp of last detected refill |
| Last Waste Empty | Timestamp of last detected waste tank empty |
| Prediction Diagnostics | Detailed diagnostics for troubleshooting |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| Water Low | True when water is low (sensor or prediction) |
| Waste Tank Full | True when waste tank is full (sensor or prediction) |

### Buttons

| Entity | Description |
|--------|-------------|
| Refilled | Manually trigger a refill event (calibrates water model) |
| Waste Tank Emptied | Manually trigger a waste empty event (calibrates waste model) |
| Clear Prediction Model | Reset adaptive models (preserves reserve learning) |

## How Learning Works

### Water Consumption Model

The model estimates water usage based on:
- Area cleaned (m²) × learned consumption rate (mL/m²)
- Mop intensity multiplier
- Mop washing events × learned wash volume

When a refill is detected, the model calibrates:
- Adjusts the area consumption rate using EWMA
- Adjusts the wash volume using EWMA
- Increments cycles observed

### Waste Water Model

Initially assumes waste water ≈ 0.9 × clean water consumed. When the waste tank is emptied, the model calibrates the waste ratio using EWMA.

### Reserve Volume Learning

Most vacuums generate warnings before reaching 0% or 100%:
- "Water low" fires before the tank is empty
- "Waste tank full" fires before the tank is completely full

The integration learns these reserve volumes:
- `observed_reserve = capacity - used_at_warning`
- Updated using EWMA with alpha=0.3

### Effective Capacity

Calibration uses effective capacity, not full capacity:
```
effective_capacity = actual_capacity - reserve_ml
```

This ensures that 0% remaining corresponds to when the vacuum would actually warn about low water.

### Clear Prediction Model

The "Clear Prediction Model" button resets:
- Water model (correction factors, cycles observed)
- Waste model (correction factors, cycles observed)

It does **NOT** reset:
- `clean_reserve_ml` (learned physical vacuum behavior)
- `dirty_reserve_ml` (learned physical vacuum behavior)
- `warning_cycles` (physical vacuum behavior)

## Detection Priority

### Cleaning State Detection

1. Dedicated cleaning binary sensor
2. Status sensor (checks for cleaning-related states)
3. Vacuum state entity
4. Fallback (return False)

### Water Low Detection

1. Clean water box binary sensor
2. Dock error sensor
3. Prediction model (based on estimated remaining)

### Waste Full Detection

1. Dirty water box binary sensor
2. Dock error sensor
3. Prediction model (based on estimated fill)

### Refill Detection

1. Clean water binary sensor clears
2. Dock error clears
3. Manual refill button

### Waste Empty Detection

1. Dirty water binary sensor clears
2. Dock full error clears
3. Manual empty button

## Persistence

All data is stored using Home Assistant storage, keyed by config entry ID (not entity ID, so it survives entity renames):
- Water model
- Waste model
- Reserve learning
- Runtime state (water used, waste collected, timestamps, warning latches)

Data survives: restarts, reloads, upgrades, and backup restores.

## Testing

The integration includes comprehensive pytest coverage for:
- Reserve learning (EWMA convergence)
- Effective capacity calculation
- Refill detection (all priority paths)
- Waste empty detection (all priority paths)
- Binary sensor state transitions
- Cleaning detection priority order
- Storage migration tests
- Multi-vacuum isolation tests
- Vendor-neutral discovery tests
- Convergence tests (direction and boundedness)

Run tests:
```bash
pytest tests/ -v
```

## License

MIT
