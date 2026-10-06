"""Adaptive learning engine for water consumption and waste water estimation.

This module is pure Python with no Home Assistant dependencies, making it
easy to unit-test independently of the HA framework.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .const import (
    DEFAULT_BASE_ML_PER_M2,
    DEFAULT_WASH_VOLUME_ML,
    DEFAULT_WASTE_RATIO,
    DEFAULT_CLEAN_RESERVE_ML,
    DEFAULT_DIRTY_RESERVE_ML,
    EWMA_ALPHA_RESERVE,
    EWMA_ALPHA_CORRECTION,
    EWMA_ALPHA_WASH_VOLUME,
    MOP_INTENSITY_MULTIPLIERS,
)


def ewma(current: float, observation: float, alpha: float) -> float:
    """Exponentially weighted moving average update.

    Args:
        current: The current EWMA value.
        observation: The new observation.
        alpha: Smoothing factor in [0, 1]. Higher alpha weights new data more.

    Returns:
        Updated EWMA value.
    """
    if current is None or math.isnan(current):
        return observation
    return current * (1.0 - alpha) + observation * alpha


@dataclass
class WaterModel:
    """Adaptive model for estimating clean water consumption.

    Attributes:
        cycles_observed: Number of refill cycles observed.
        correction_factors: Learned correction factors.
        pending_usage_ml: Accumulated usage since last calibration.
        pending_area_m2: Accumulated area since last calibration.
        pending_wash_count: Wash events since last calibration.
        pending_mop_intensity: Dominant mop intensity since last calibration.
    """

    cycles_observed: int = 0
    correction_factors: dict[str, Any] = field(default_factory=dict)
    pending_usage_ml: float = 0.0
    pending_area_m2: float = 0.0
    pending_wash_count: int = 0
    pending_mop_intensity: str = "medium"

    def __post_init__(self) -> None:
        """Initialize default correction factors."""
        if "area_ml_per_m2" not in self.correction_factors:
            self.correction_factors["area_ml_per_m2"] = DEFAULT_BASE_ML_PER_M2
        if "mop_intensity_multiplier" not in self.correction_factors:
            self.correction_factors["mop_intensity_multiplier"] = dict(
                MOP_INTENSITY_MULTIPLIERS
            )
        if "wash_volume_ml" not in self.correction_factors:
            self.correction_factors["wash_volume_ml"] = DEFAULT_WASH_VOLUME_ML

    @property
    def learned_wash_volume_ml(self) -> float:
        """Return the learned wash volume."""
        return self.correction_factors.get("wash_volume_ml", DEFAULT_WASH_VOLUME_ML)

    def estimate_usage(
        self,
        area_cleaned_m2: float,
        mop_mode: str | None,
        mop_intensity: str | None,
        wash_count: int,
    ) -> float:
        """Estimate water usage for a cleaning session.

        Args:
            area_cleaned_m2: Area cleaned in square meters.
            mop_mode: Current mop mode (e.g., 'on', 'off', 'none').
            mop_intensity: Mop intensity level.
            wash_count: Number of mop wash events.

        Returns:
            Estimated water usage in mL.
        """
        base_ml_per_m2 = self.correction_factors.get(
            "area_ml_per_m2", DEFAULT_BASE_ML_PER_M2
        )

        # Determine if mopping is active
        # Default to True if no mop mode entity is configured (user likely
        # has a mopping vacuum if they installed this integration)
        # Check BOTH mop_mode and mop_intensity - if either indicates
        # vacuum-only mode, mopping is inactive (OR condition)
        mop_active = True
        vacuum_only_keywords = {
            "off", "none", "stop", "vacuum", "sweep",
            "vacuum_only", "sweep_only", "no_mop",
            "sweeping", "vacuuming",
        }

        if mop_mode is not None:
            mop_lower = str(mop_mode).lower().strip()
            if mop_lower in vacuum_only_keywords:
                mop_active = False

        # Also check mop intensity - if it's "off", vacuum is not mopping
        if mop_intensity is not None and mop_active:
            intensity_lower = str(mop_intensity).lower().strip()
            if intensity_lower in vacuum_only_keywords:
                mop_active = False

        if not mop_active:
            area_usage = 0.0
        else:
            area_usage = area_cleaned_m2 * base_ml_per_m2

        # Intensity multiplier
        intensity_key = (mop_intensity or "medium").lower()
        intensity_mult = self.correction_factors.get(
            "mop_intensity_multiplier", {}
        ).get(intensity_key, MOP_INTENSITY_MULTIPLIERS.get(intensity_key, 1.0))

        # Wash volume
        wash_volume = self.learned_wash_volume_ml

        total = area_usage * intensity_mult + wash_count * wash_volume
        return round(total, 2)

    def record_usage(
        self,
        area_cleaned_m2: float,
        mop_mode: str | None,
        mop_intensity: str | None,
        wash_count: int,
    ) -> float:
        """Record usage and return the estimate for this session.

        Accumulates pending values for future calibration against actual refill.
        """
        estimated = self.estimate_usage(
            area_cleaned_m2, mop_mode, mop_intensity, wash_count
        )
        self.pending_usage_ml += estimated
        self.pending_area_m2 += area_cleaned_m2
        self.pending_wash_count += wash_count
        # Track dominant intensity
        if mop_intensity:
            self.pending_mop_intensity = mop_intensity
        return estimated

    def calibrate(self, actual_usage_ml: float) -> None:
        """Calibrate the model against observed actual usage.

        Called when a refill is detected and we know the total water consumed.
        Updates correction factors using EWMA.

        Args:
            actual_usage_ml: Actual water consumed since last refill.
        """
        if self.pending_area_m2 <= 0 and self.pending_wash_count <= 0:
            # No data to calibrate against
            return

        estimated = self.pending_usage_ml
        if estimated <= 0:
            return

        # Compute correction ratio
        ratio = actual_usage_ml / estimated

        # Bound the ratio to avoid extreme jumps
        ratio = max(0.1, min(ratio, 10.0))

        # Update area consumption rate
        if self.pending_area_m2 > 0:
            current_area_rate = self.correction_factors.get(
                "area_ml_per_m2", DEFAULT_BASE_ML_PER_M2
            )
            # Estimate how much of the actual usage was area vs wash
            wash_volume = self.learned_wash_volume_ml
            estimated_wash = self.pending_wash_count * wash_volume
            estimated_area = estimated - estimated_wash
            if estimated_area > 0:
                area_ratio = estimated_area / estimated
                actual_area_usage = actual_usage_ml * area_ratio
                observed_area_rate = actual_area_usage / self.pending_area_m2
                self.correction_factors["area_ml_per_m2"] = round(
                    ewma(
                        current_area_rate,
                        observed_area_rate,
                        EWMA_ALPHA_CORRECTION,
                    ),
                    4,
                )

        # Update wash volume if we had wash events
        if self.pending_wash_count > 0:
            current_wash = self.learned_wash_volume_ml
            # Estimate wash portion of actual usage
            estimated_area_total = self.correction_factors.get(
                "area_ml_per_m2", DEFAULT_BASE_ML_PER_M2
            ) * self.pending_area_m2
            # Use intensity multiplier for the dominant intensity
            intensity_key = self.pending_mop_intensity.lower()
            intensity_mult = self.correction_factors.get(
                "mop_intensity_multiplier", {}
            ).get(intensity_key, 1.0)
            estimated_area_total *= intensity_mult
            if actual_usage_ml > estimated_area_total:
                actual_wash_total = actual_usage_ml - estimated_area_total
                observed_wash = actual_wash_total / self.pending_wash_count
                self.correction_factors["wash_volume_ml"] = round(
                    ewma(
                        current_wash,
                        observed_wash,
                        EWMA_ALPHA_WASH_VOLUME,
                    ),
                    2,
                )

        self.cycles_observed += 1
        # Reset pending
        self.pending_usage_ml = 0.0
        self.pending_area_m2 = 0.0
        self.pending_wash_count = 0

    def reset_model(self) -> None:
        """Reset the adaptive model completely.

        Called by the Clear Prediction Model button.
        Resets water_model and waste_model entirely.
        Does NOT reset reserve learning (clean_reserve_ml, dirty_reserve_ml,
        warning_cycles) - those represent physical vacuum behavior.
        """
        self.cycles_observed = 0
        self.correction_factors = {
            "area_ml_per_m2": DEFAULT_BASE_ML_PER_M2,
            "mop_intensity_multiplier": dict(MOP_INTENSITY_MULTIPLIERS),
            "wash_volume_ml": DEFAULT_WASH_VOLUME_ML,
        }
        self.pending_usage_ml = 0.0
        self.pending_area_m2 = 0.0
        self.pending_wash_count = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "cycles_observed": self.cycles_observed,
            "correction_factors": self.correction_factors,
            "pending_usage_ml": self.pending_usage_ml,
            "pending_area_m2": self.pending_area_m2,
            "pending_wash_count": self.pending_wash_count,
            "pending_mop_intensity": self.pending_mop_intensity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> WaterModel:
        """Deserialize from dictionary."""
        if data is None:
            return cls()
        return cls(
            cycles_observed=data.get("cycles_observed", 0),
            correction_factors=data.get("correction_factors", {}),
            pending_usage_ml=data.get("pending_usage_ml", 0.0),
            pending_area_m2=data.get("pending_area_m2", 0.0),
            pending_wash_count=data.get("pending_wash_count", 0),
            pending_mop_intensity=data.get("pending_mop_intensity", "medium"),
        )


@dataclass
class WasteModel:
    """Adaptive model for estimating waste water collection.

    Attributes:
        cycles_observed: Number of empty cycles observed.
        correction_factors: Learned correction factors including waste_ratio.
        pending_usage_ml: Accumulated waste estimate since last calibration.
    """

    cycles_observed: int = 0
    correction_factors: dict[str, Any] = field(default_factory=dict)
    pending_usage_ml: float = 0.0

    def __post_init__(self) -> None:
        """Initialize default correction factors."""
        if "waste_ratio" not in self.correction_factors:
            self.correction_factors["waste_ratio"] = DEFAULT_WASTE_RATIO

    @property
    def waste_ratio(self) -> float:
        """Return the learned waste-to-clean ratio."""
        return self.correction_factors.get("waste_ratio", DEFAULT_WASTE_RATIO)

    def estimate_waste(self, clean_water_used_ml: float) -> float:
        """Estimate waste water collected based on clean water used.

        Initially assumes waste ~= clean * ratio.
        Over time, the ratio is learned independently.
        """
        return round(clean_water_used_ml * self.waste_ratio, 2)

    def record_usage(self, clean_water_used_ml: float) -> float:
        """Record waste estimate and accumulate for calibration."""
        estimated = self.estimate_waste(clean_water_used_ml)
        self.pending_usage_ml += estimated
        return estimated

    def calibrate(self, actual_waste_ml: float, clean_water_used_ml: float) -> None:
        """Calibrate the waste model against observed actual waste.

        Called when waste tank is emptied and we know total waste collected.

        Args:
            actual_waste_ml: Actual waste water collected since last empty.
            clean_water_used_ml: Clean water used in the same period.
        """
        if clean_water_used_ml <= 0:
            return

        observed_ratio = actual_waste_ml / clean_water_used_ml
        # Bound the ratio
        observed_ratio = max(0.0, min(observed_ratio, 3.0))

        current_ratio = self.waste_ratio
        self.correction_factors["waste_ratio"] = round(
            ewma(current_ratio, observed_ratio, EWMA_ALPHA_CORRECTION), 4
        )

        self.cycles_observed += 1
        self.pending_usage_ml = 0.0

    def reset_model(self) -> None:
        """Reset the adaptive model.

        Called by the Clear Prediction Model button.
        """
        self.cycles_observed = 0
        self.correction_factors = {"waste_ratio": DEFAULT_WASTE_RATIO}
        self.pending_usage_ml = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "cycles_observed": self.cycles_observed,
            "correction_factors": self.correction_factors,
            "pending_usage_ml": self.pending_usage_ml,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> WasteModel:
        """Deserialize from dictionary."""
        if data is None:
            return cls()
        return cls(
            cycles_observed=data.get("cycles_observed", 0),
            correction_factors=data.get("correction_factors", {}),
            pending_usage_ml=data.get("pending_usage_ml", 0.0),
        )


@dataclass
class ReserveLearning:
    """Track learned reserve volumes for water low and waste full warnings.

    Most vacuums generate 'water low' before reaching 0%, and 'waste tank full'
    before reaching 100%. This class learns those reserve volumes using EWMA.
    """

    clean_reserve_ml: float = DEFAULT_CLEAN_RESERVE_ML
    dirty_reserve_ml: float = DEFAULT_DIRTY_RESERVE_ML
    warning_cycles: int = 0

    def update_clean_reserve(self, capacity_ml: float, used_ml: float) -> None:
        """Update clean water reserve when a water low warning occurs.

        Args:
            capacity_ml: Full tank capacity in mL.
            used_ml: Water used at the time of the warning.
        """
        observed_reserve = capacity_ml - used_ml
        if observed_reserve < 0:
            observed_reserve = 0.0
        self.clean_reserve_ml = round(
            ewma(self.clean_reserve_ml, observed_reserve, EWMA_ALPHA_RESERVE), 2
        )
        self.warning_cycles += 1

    def update_dirty_reserve(self, capacity_ml: float, waste_ml: float) -> None:
        """Update dirty water reserve when a waste full warning occurs.

        Args:
            capacity_ml: Full tank capacity in mL.
            waste_ml: Waste collected at the time of the warning.
        """
        observed_reserve = capacity_ml - waste_ml
        if observed_reserve < 0:
            observed_reserve = 0.0
        self.dirty_reserve_ml = round(
            ewma(self.dirty_reserve_ml, observed_reserve, EWMA_ALPHA_RESERVE), 2
        )
        self.warning_cycles += 1

    def effective_clean_capacity(self, capacity_ml: float) -> float:
        """Return effective clean tank capacity after reserve."""
        return max(capacity_ml - self.clean_reserve_ml, 1.0)

    def effective_dirty_capacity(self, capacity_ml: float) -> float:
        """Return effective dirty tank capacity after reserve."""
        return max(capacity_ml - self.dirty_reserve_ml, 1.0)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "clean_reserve_ml": self.clean_reserve_ml,
            "dirty_reserve_ml": self.dirty_reserve_ml,
            "warning_cycles": self.warning_cycles,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ReserveLearning:
        """Deserialize from dictionary."""
        if data is None:
            return cls()
        return cls(
            clean_reserve_ml=data.get("clean_reserve_ml", DEFAULT_CLEAN_RESERVE_ML),
            dirty_reserve_ml=data.get("dirty_reserve_ml", DEFAULT_DIRTY_RESERVE_ML),
            warning_cycles=data.get("warning_cycles", 0),
        )


@dataclass
class VacuumWaterState:
    """Runtime state for a single vacuum's water tracking.

    This holds all mutable runtime data that needs to persist across restarts.
    """

    water_used_since_refill_ml: float = 0.0
    waste_collected_ml: float = 0.0
    clean_water_used_since_waste_empty_ml: float = 0.0
    last_refill: str | None = None
    last_waste_empty: str | None = None
    clean_warning_latched: bool = False
    dirty_warning_latched: bool = False
    last_cleaning_state: bool = False
    last_area: float = 0.0
    last_mop_mode: str | None = None
    last_mop_intensity: str | None = None
    wash_count: int = 0
    cleaning_in_progress: bool = False
    session_start_area: float = 0.0
    session_checkpointed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "water_used_since_refill_ml": self.water_used_since_refill_ml,
            "waste_collected_ml": self.waste_collected_ml,
            "clean_water_used_since_waste_empty_ml": self.clean_water_used_since_waste_empty_ml,
            "last_refill": self.last_refill,
            "last_waste_empty": self.last_waste_empty,
            "clean_warning_latched": self.clean_warning_latched,
            "dirty_warning_latched": self.dirty_warning_latched,
            "last_cleaning_state": self.last_cleaning_state,
            "last_area": self.last_area,
            "last_mop_mode": self.last_mop_mode,
            "last_mop_intensity": self.last_mop_intensity,
            "wash_count": self.wash_count,
            "cleaning_in_progress": self.cleaning_in_progress,
            "session_start_area": self.session_start_area,
            "session_checkpointed": self.session_checkpointed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> VacuumWaterState:
        """Deserialize from dictionary."""
        if data is None:
            return cls()
        return cls(
            water_used_since_refill_ml=data.get("water_used_since_refill_ml", 0.0),
            waste_collected_ml=data.get("waste_collected_ml", 0.0),
            clean_water_used_since_waste_empty_ml=data.get(
                "clean_water_used_since_waste_empty_ml", 0.0
            ),
            last_refill=data.get("last_refill"),
            last_waste_empty=data.get("last_waste_empty"),
            clean_warning_latched=data.get("clean_warning_latched", False),
            dirty_warning_latched=data.get("dirty_warning_latched", False),
            last_cleaning_state=data.get("last_cleaning_state", False),
            last_area=data.get("last_area", 0.0),
            last_mop_mode=data.get("last_mop_mode"),
            last_mop_intensity=data.get("last_mop_intensity"),
            wash_count=data.get("wash_count", 0),
            cleaning_in_progress=data.get("cleaning_in_progress", False),
            session_start_area=data.get("session_start_area", 0.0),
            session_checkpointed=data.get("session_checkpointed", False),
        )


def compute_water_remaining_pct(
    used_ml: float,
    capacity_ml: float,
    reserve_ml: float,
) -> float:
    """Compute water remaining percentage.

    Uses effective capacity (capacity - reserve) so that 0% corresponds to
    when the vacuum would generate a water low warning.

    Args:
        used_ml: Water used since last refill.
        capacity_ml: Full tank capacity in mL.
        reserve_ml: Learned reserve volume in mL.

    Returns:
        Percentage remaining (0-100), clamped.
    """
    effective_capacity = max(capacity_ml - reserve_ml, 1.0)
    remaining = effective_capacity - used_ml
    pct = (remaining / effective_capacity) * 100.0
    return max(0.0, min(pct, 100.0))


def compute_water_remaining_ml(
    used_ml: float,
    capacity_ml: float,
    reserve_ml: float,
) -> float:
    """Compute water remaining in mL.

    Returns remaining mL using effective capacity.
    """
    effective_capacity = max(capacity_ml - reserve_ml, 1.0)
    remaining = effective_capacity - used_ml
    return max(0.0, round(remaining, 1))


def compute_waste_pct(
    waste_ml: float,
    capacity_ml: float,
    reserve_ml: float,
) -> float:
    """Compute waste tank fill percentage.

    Uses effective capacity so that 100% corresponds to when the vacuum
    would generate a waste tank full warning.

    Args:
        waste_ml: Waste collected since last empty.
        capacity_ml: Full tank capacity in mL.
        reserve_ml: Learned dirty reserve volume in mL.

    Returns:
        Percentage full (0-100), clamped.
    """
    effective_capacity = max(capacity_ml - reserve_ml, 1.0)
    pct = (waste_ml / effective_capacity) * 100.0
    return max(0.0, min(pct, 100.0))


def compute_waste_ml(
    waste_ml: float,
    capacity_ml: float,
    reserve_ml: float,
) -> float:
    """Compute waste tank fill in mL (capped at effective capacity)."""
    effective_capacity = max(capacity_ml - reserve_ml, 1.0)
    return min(round(waste_ml, 1), round(effective_capacity, 1))
