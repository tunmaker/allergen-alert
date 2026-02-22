"""Tests for Phase 3 features: calibration, duty cycle, AQI, data processing."""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.calibration import (
    CalibrationManager,
    ENS160BurnInTracker,
    SCD40CalibrationTracker,
)
from utils.data_processing import (
    MovingAverageFilter,
    AQICalculator,
    MultiSensorAQI,
    ExponentialMovingAverage,
)
from utils.duty_cycle import PMS5003DutyCycleManager, DutyCycleScheduler


def test_moving_average_filter():
    """Test moving average filtering."""
    print("\n" + "=" * 60)
    print("Testing Moving Average Filter")
    print("=" * 60)

    filter_ma = MovingAverageFilter(window_size=3)

    # Add readings
    readings = [10.0, 12.0, 11.0, 13.0, 12.5]

    print("\nAdding readings: ", readings)
    for reading in readings:
        avg = filter_ma.add_reading(reading)
        if avg is not None:
            print(f"  Input: {reading:.1f} → Moving Avg (window=3): {avg:.2f}")
        else:
            print(f"  Input: {reading:.1f} → Waiting for more readings ({filter_ma.get_readings_count()}/3)")

    # Verify
    assert filter_ma.is_ready(), "Filter should be ready"
    expected = (11.0 + 13.0 + 12.5) / 3
    actual = filter_ma.get_average()
    assert abs(actual - expected) < 0.01, f"Expected {expected}, got {actual}"

    print("✓ Moving average filter test passed")


def test_aqi_calculation():
    """Test AQI calculation from PM2.5."""
    print("\n" + "=" * 60)
    print("Testing AQI Calculation")
    print("=" * 60)

    test_cases = [
        (5, 0, "Good"),
        (25, 51, "Moderate"),
        (50, 101, "Unhealthy for Sensitive Groups"),
        (100, 151, "Unhealthy"),
        (200, 201, "Very Unhealthy"),
        (300, 301, "Hazardous"),
    ]

    print("\nAQI Calculations:")
    for pm2_5, expected_aqi_range_start, category in test_cases:
        aqi, cat = AQICalculator.calculate_aqi(pm2_5)
        print(
            f"  PM2.5: {pm2_5:5.1f} µg/m³ → AQI: {aqi:3d} ({cat:35})"
        )
        assert cat == category, f"Expected {category}, got {cat}"

    # Test health effects
    effects_good = AQICalculator.get_health_effects(25)
    print(f"\nHealth effects at AQI 25 (Good):")
    print(f"  {effects_good}")
    assert "satisfactory" in effects_good.lower()

    effects_bad = AQICalculator.get_health_effects(250)
    print(f"\nHealth effects at AQI 250 (Very Unhealthy):")
    print(f"  {effects_bad}")
    assert "serious" in effects_bad.lower()

    print("✓ AQI calculation test passed")


def test_multi_sensor_aqi():
    """Test comprehensive AQI from multiple sensors."""
    print("\n" + "=" * 60)
    print("Testing Multi-Sensor AQI")
    print("=" * 60)

    aqi_calc = MultiSensorAQI()

    # Simulate poor air quality
    aqi_calc.update(pm2_5=55.5, co2=1200, tvoc=400)

    overall_aqi = aqi_calc.calculate_overall_aqi()
    print(f"\nScenario: Poor indoor air")
    print(f"  PM2.5: 55.5 µg/m³")
    print(f"  CO2: 1200 ppm")
    print(f"  TVOC: 400 ppb")
    print(f"  Overall AQI: {overall_aqi}")

    status = aqi_calc.get_air_quality_status()
    print(f"\nStatus: {status}")

    recommendations = AQICalculator.get_health_recommendations(overall_aqi)
    print("\nRecommendations:")
    for rec in recommendations:
        print(f"  • {rec}")

    assert overall_aqi > 100, "Poor air quality should have AQI > 100"
    print("✓ Multi-sensor AQI test passed")


def test_exponential_moving_average():
    """Test exponential moving average filter."""
    print("\n" + "=" * 60)
    print("Testing Exponential Moving Average")
    print("=" * 60)

    ema = ExponentialMovingAverage(alpha=0.3)

    readings = [100, 110, 105, 115, 120, 108]
    print(f"\nAlpha (smoothing): 0.3")
    print("Adding readings with EMA:")

    for reading in readings:
        smoothed = ema.add_reading(reading)
        print(f"  Input: {reading:3.0f} → EMA: {smoothed:.2f}")

    assert ema.get_ema() is not None, "EMA should have a value"
    assert 100 < ema.get_ema() < 120, "EMA should be within range"

    print("✓ Exponential moving average test passed")


def test_calibration_manager():
    """Test calibration tracking."""
    print("\n" + "=" * 60)
    print("Testing Calibration Manager")
    print("=" * 60)

    # Use in-memory test (don't persist)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        calib_file = f.name

    try:
        manager = CalibrationManager(calib_file)

        # Start calibration
        manager.start_calibration("test_sensor", "Test burn-in")
        assert not manager.is_calibrated("test_sensor")
        print("✓ Started calibration for test sensor")

        # Complete calibration
        manager.complete_calibration("test_sensor")
        assert manager.is_calibrated("test_sensor")
        print("✓ Completed calibration for test sensor")

        # Check status
        status = manager.get_calibration_status("test_sensor")
        assert status.calibration_status == "complete"
        print(f"✓ Calibration status: {status.calibration_status}")

        print("✓ Calibration manager test passed")
    finally:
        os.unlink(calib_file)


def test_ens160_burn_in_tracker():
    """Test ENS160 burn-in tracking."""
    print("\n" + "=" * 60)
    print("Testing ENS160 Burn-in Tracker")
    print("=" * 60)

    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        calib_file = f.name

    try:
        manager = CalibrationManager(calib_file)
        tracker = ENS160BurnInTracker(manager)

        accuracy = tracker.get_accuracy_level()
        progress = tracker.get_burn_in_progress()

        print(f"\nInitial state:")
        print(f"  Accuracy Level: {accuracy}")
        print(f"  Progress: {progress:.1f}%")

        remaining = tracker.get_time_remaining()
        if remaining:
            print(f"  Time Remaining: ~7 days (simulated)")

        print(f"\nStatus Report:")
        print(tracker.get_status_report())

        assert accuracy in ["initializing", "burn_in", "improving", "full"]
        print("✓ ENS160 burn-in tracker test passed")
    finally:
        os.unlink(calib_file)


def test_scd40_calibration_tracker():
    """Test SCD40 calibration tracking."""
    print("\n" + "=" * 60)
    print("Testing SCD40 Calibration Tracker")
    print("=" * 60)

    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        calib_file = f.name

    try:
        manager = CalibrationManager(calib_file)
        tracker = SCD40CalibrationTracker(manager)

        # Initially needs recalibration
        assert tracker.needs_recalibration()
        print("✓ SCD40 needs initial fresh air exposure")

        # Record fresh air exposure
        tracker.record_fresh_air_exposure()
        assert not tracker.needs_recalibration(max_days=7)
        print("✓ Fresh air exposure recorded")

        print(f"\nStatus Report:")
        print(tracker.get_status_report())

        print("✓ SCD40 calibration tracker test passed")
    finally:
        os.unlink(calib_file)


def test_pms5003_duty_cycle():
    """Test PMS5003 duty cycle management."""
    print("\n" + "=" * 60)
    print("Testing PMS5003 Duty Cycle Manager")
    print("=" * 60)

    # Test extended pattern
    manager = PMS5003DutyCycleManager(pattern="extended")

    print("\nExtended Pattern (50% duty cycle):")
    print(f"  Run: {manager.run_seconds}s, Rest: {manager.rest_seconds}s")
    print(f"  Duty Cycle: {manager.get_duty_cycle_percent():.0f}%")
    print(f"  Est. Lifetime: {manager.get_estimated_lifetime():.1f} years")

    status = manager.get_status()
    print(f"\nCurrent Status:")
    print(f"  State: {status['state']}")
    print(f"  Cycle Progress: {status['cycle_progress_percent']:.1f}%")

    # Test different patterns
    print("\nAll Patterns:")
    for pattern_name in ["extended", "balanced", "normal"]:
        pm = PMS5003DutyCycleManager(pattern=pattern_name)
        lifetime = pm.get_estimated_lifetime()
        print(
            f"  {pattern_name:12} {pm.get_duty_cycle_percent():5.0f}% duty → "
            f"{lifetime:.1f} years lifetime"
        )

    print(f"\nStatus Report:")
    print(manager.get_status_report())

    # Test state change detection
    scheduler = DutyCycleScheduler(manager)
    changed = scheduler.check_and_log_state_change()
    print(f"\n✓ Duty cycle test passed")


if __name__ == "__main__":
    try:
        test_moving_average_filter()
        test_aqi_calculation()
        test_multi_sensor_aqi()
        test_exponential_moving_average()
        test_calibration_manager()
        test_ens160_burn_in_tracker()
        test_scd40_calibration_tracker()
        test_pms5003_duty_cycle()

        print("\n" + "=" * 60)
        print("All Phase 3 tests passed! ✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
