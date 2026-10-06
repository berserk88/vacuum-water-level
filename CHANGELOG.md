# Changelog

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
