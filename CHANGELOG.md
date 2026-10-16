# Changelog

## [1.2.0] - 2026-10-16

### Fixed
- Fixed tank fill percentage and volume mL alignment across all operational states. Fill % and volume now calculate consistently against effective usable capacity ($C_{\text{capacity}} - R_{\text{reserve}}$).
- Fixed state transition race condition when dock/tank error clears from `error` to `ok`. Refill and waste empty evaluation now occurs before warning threshold checks, ensuring unlatched warning states upon tank refill and emptying.
- Fixed warning latch clearing when refill or empty occurs without accumulated cleaning usage.
- Added automatic fallback to `status_entity` when dedicated `dock_error_entity` is not configured, parsing dock/water error states seamlessly.
- Expanded non-error dock states to include `charging`, `docked`, `idle`, `ready`, `standby`, `cleared`, `normal`, and `ok`.
- Added extra state attributes to `sensor.<vacuum>_water_consumption_rate` and `sensor.<vacuum>_dirty_water_fill_rate` entities.

## [1.1.0] - 2026-10-10

### Added
- Added `sensor.<vacuum>_water_consumption_rate` entity measuring real-time water consumption rate in mL/m².
- Added `sensor.<vacuum>_dirty_water_fill_rate` entity measuring dirty water fill rate in mL/m².
- Exposed baseline rate and intensity-adjusted effective rate calculations in sensor attributes.

## [1.0.0] - 2026-10-06

### Added
- Initial release of Vacuum Water Level integration
- Adaptive water consumption estimation based on cleaned area, mop intensity, and mop mode
- Mop washing event tracking with learnable wash volume
- Independent waste water tracking with learnable waste-to-clean ratio
- Reserve volume learning using EWMA for water low and waste tank full warnings
- Effective capacity calculation (actual capacity - learned reserve)
- Vendor-neutral companion entity auto-discovery
- Config flow with two-step setup (vacuum selection + companion entity discovery)
- Options flow for editing all configuration after setup
- Support for multiple vacuums (one config entry per vacuum)
- Native Home Assistant entities (sensors, binary sensors, buttons)
- Persistence using Home Assistant storage (survives restart, reload, upgrade, backup restore)
- Detection priority for cleaning state, water low, waste full, refill, and waste empty
- Prediction diagnostics sensor with full model state
- Clear prediction model button (preserves reserve learning)
- Comprehensive pytest test suite covering all critical paths
- HACS-ready repository structure
- Translations (English)

### Supported Vendors
- Roborock, Dreame, Ecovacs, Narwal, Xiaomi, Eufy, Samsung, and future vendors
- No vendor-specific logic is hardcoded; all discovery is heuristic
