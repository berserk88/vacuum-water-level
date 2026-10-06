"""Tests for dock error parsing logic.

Tests that dock errors are correctly parsed to distinguish between
clean water issues, dirty water issues, and unrelated errors.
"""

import pytest
from custom_components.vacuum_water_level.detection import (
    parse_dock_error_clean,
    parse_dock_error_dirty,
)


class TestDockErrorCleanWater:
    """Tests for clean water dock error parsing."""

    def test_clean_water_empty(self):
        """Test 'clean water empty' detected as clean water issue."""
        assert parse_dock_error_clean("clean water empty") is True

    def test_water_box_low(self):
        """Test 'water box low' detected as clean water issue."""
        assert parse_dock_error_clean("water box low") is True

    def test_water_tank_missing(self):
        """Test 'water tank missing' detected as clean water issue."""
        assert parse_dock_error_clean("water tank missing") is True

    def test_no_water(self):
        """Test 'no water' detected as clean water issue."""
        assert parse_dock_error_clean("no water") is True

    def test_dirty_water_full_not_clean(self):
        """Test 'dirty water full' NOT detected as clean water issue."""
        assert parse_dock_error_clean("dirty water full") is False

    def test_waste_tank_full_not_clean(self):
        """Test 'waste tank full' NOT detected as clean water issue."""
        assert parse_dock_error_clean("waste tank full") is False

    def test_generic_error_treated_as_clean(self):
        """Test generic 'error' treated as both (could be clean)."""
        assert parse_dock_error_clean("error") is True

    def test_off_state_not_clean_issue(self):
        """Test 'off' state is not a clean water issue."""
        assert parse_dock_error_clean("off") is False

    def test_ok_state_not_clean_issue(self):
        """Test 'ok' state is not a clean water issue."""
        assert parse_dock_error_clean("ok") is False

    def test_none_input(self):
        """Test None input returns None."""
        assert parse_dock_error_clean(None) is None

    def test_empty_string(self):
        """Test empty string returns False."""
        assert parse_dock_error_clean("") is False

    def test_unrelated_error_not_clean(self):
        """Test unrelated error text doesn't trigger clean water."""
        assert parse_dock_error_clean("brush stuck") is False

    def test_robot_stuck_not_clean(self):
        """Test 'robot stuck' doesn't trigger clean water."""
        assert parse_dock_error_clean("robot stuck") is False


class TestDockErrorDirtyWater:
    """Tests for dirty water dock error parsing."""

    def test_dirty_water_full(self):
        """Test 'dirty water full' detected as dirty water issue."""
        assert parse_dock_error_dirty("dirty water full") is True

    def test_waste_tank_full(self):
        """Test 'waste tank full' detected as dirty water issue."""
        assert parse_dock_error_dirty("waste tank full") is True

    def test_dirty_box_full(self):
        """Test 'dirty box full' detected as dirty water issue."""
        assert parse_dock_error_dirty("dirty box full") is True

    def test_clean_water_empty_not_dirty(self):
        """Test 'clean water empty' NOT detected as dirty water issue."""
        assert parse_dock_error_dirty("clean water empty") is False

    def test_water_box_low_not_dirty(self):
        """Test 'water box low' NOT detected as dirty water issue."""
        assert parse_dock_error_dirty("water box low") is False

    def test_generic_error_treated_as_dirty(self):
        """Test generic 'error' treated as both (could be dirty)."""
        assert parse_dock_error_dirty("error") is True

    def test_off_state_not_dirty_issue(self):
        """Test 'off' state is not a dirty water issue."""
        assert parse_dock_error_dirty("off") is False

    def test_none_input(self):
        """Test None input returns None."""
        assert parse_dock_error_dirty(None) is None

    def test_unrelated_error_not_dirty(self):
        """Test unrelated error text doesn't trigger dirty water."""
        assert parse_dock_error_dirty("brush stuck") is False


class TestDockErrorSpecificity:
    """Tests that dock errors are specific to water type."""

    def test_clean_water_error_only_triggers_clean(self):
        """Test clean water error triggers clean but not dirty."""
        text = "clean water empty"
        assert parse_dock_error_clean(text) is True
        assert parse_dock_error_dirty(text) is False

    def test_dirty_water_error_only_triggers_dirty(self):
        """Test dirty water error triggers dirty but not clean."""
        text = "dirty water full"
        assert parse_dock_error_dirty(text) is True
        assert parse_dock_error_clean(text) is False

    def test_unrelated_error_triggers_neither(self):
        """Test unrelated error triggers neither."""
        text = "brush stuck"
        assert parse_dock_error_clean(text) is False
        assert parse_dock_error_dirty(text) is False

    def test_generic_error_triggers_both(self):
        """Test generic 'error' triggers both (can't determine type)."""
        text = "error"
        assert parse_dock_error_clean(text) is True
        assert parse_dock_error_dirty(text) is True
