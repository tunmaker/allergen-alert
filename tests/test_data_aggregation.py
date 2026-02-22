"""Tests for data aggregation and consensus calculations."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.data_aggregation import TemperatureAggregator, HumidityAggregator


def test_temperature_aggregation():
    """Test temperature aggregation with offset correction."""
    print("\n" + "=" * 60)
    print("Testing Temperature Aggregation")
    print("=" * 60)

    agg = TemperatureAggregator(use_offsets=True)

    # Simulate readings from all three sensors
    agg.add_reading("temperature", 20.0)  # AHT21 (reference, no offset)
    agg.add_reading("temperature_bme680", 23.5)  # BME680 (reads ~3°C high)
    agg.add_reading("temperature_scd40", 21.2)  # SCD40 (reads ~1.5°C high)

    print("\nRaw readings:")
    print(f"  AHT21:     20.0°C")
    print(f"  BME680:    23.5°C")
    print(f"  SCD40:     21.2°C")

    print("\nCorrected readings (with offset):")
    for name in ["temperature", "temperature_bme680", "temperature_scd40"]:
        corrected = agg.get_corrected_temperature(name)
        print(f"  {name:30} {corrected}°C")

    consensus = agg.get_consensus_temperature()
    avg = agg.get_average_temperature()
    temp_range = agg.get_temperature_range()

    print(f"\nConsensus (median): {consensus}°C")
    print(f"Average (mean):    {avg}°C")
    print(f"Range:             {temp_range[0]}°C to {temp_range[1]}°C")

    print("\nDetailed report:")
    print(agg.get_temperature_report())

    # Validate results
    assert consensus is not None, "Consensus should not be None"
    assert 19.5 <= consensus <= 20.5, f"Consensus should be ~20°C, got {consensus}°C"
    print("✓ Temperature aggregation test passed")


def test_temperature_without_offsets():
    """Test temperature aggregation without offset correction."""
    print("\n" + "=" * 60)
    print("Testing Temperature Aggregation (No Offsets)")
    print("=" * 60)

    agg = TemperatureAggregator(use_offsets=False)

    agg.add_reading("temperature", 20.0)
    agg.add_reading("temperature_bme680", 23.5)
    agg.add_reading("temperature_scd40", 21.2)

    print("\nRaw readings (no offset applied):")
    for name in ["temperature", "temperature_bme680", "temperature_scd40"]:
        corrected = agg.get_corrected_temperature(name)
        print(f"  {name:30} {corrected}°C")

    consensus = agg.get_consensus_temperature()
    print(f"\nConsensus (median): {consensus}°C")

    # Should be median of [20.0, 23.5, 21.2] = 21.2
    assert 21.0 <= consensus <= 21.5, f"Consensus should be ~21.2°C, got {consensus}°C"
    print("✓ Temperature without offsets test passed")


def test_humidity_aggregation():
    """Test humidity aggregation with weighted consensus."""
    print("\n" + "=" * 60)
    print("Testing Humidity Aggregation")
    print("=" * 60)

    agg = HumidityAggregator()

    # Simulate readings with different accuracy levels
    agg.add_reading("humidity", 45.0)  # AHT21 (weight 3, most accurate)
    agg.add_reading("humidity_bme680", 47.0)  # BME680 (weight 2)
    agg.add_reading("humidity_scd40", 50.0)  # SCD40 (weight 1, least accurate)

    print("\nReadings with weights:")
    print(f"  AHT21:     45.0% (weight 3 - most accurate)")
    print(f"  BME680:    47.0% (weight 2)")
    print(f"  SCD40:     50.0% (weight 1 - least accurate)")

    consensus = agg.get_consensus_humidity()
    print(f"\nWeighted Consensus: {consensus}%")

    # Should be weighted average: (45*3 + 47*2 + 50*1) / (3+2+1) = 266/6 = 44.33
    assert 44.0 <= consensus <= 45.5, f"Consensus should be ~44.3%, got {consensus}%"

    print("\nDetailed report:")
    print(agg.get_humidity_report())
    print("✓ Humidity aggregation test passed")


def test_invalid_readings():
    """Test handling of invalid readings."""
    print("\n" + "=" * 60)
    print("Testing Invalid Reading Handling")
    print("=" * 60)

    agg = HumidityAggregator()

    # Try to add invalid readings
    print("\nAdding invalid readings:")
    print("  humidity = 101% (>100%)")
    agg.add_reading("humidity", 101.0)

    print("  humidity = -5% (<0%)")
    agg.add_reading("humidity", -5.0)

    print("  humidity_bme680 = 50% (valid)")
    agg.add_reading("humidity_bme680", 50.0)

    # Should only have the valid reading
    consensus = agg.get_consensus_humidity()
    assert consensus is not None, "Should have consensus with valid reading"
    assert 49.0 <= consensus <= 51.0, f"Consensus should be ~50%, got {consensus}%"

    print("✓ Invalid reading handling test passed")


def test_empty_readings():
    """Test behavior with no readings."""
    print("\n" + "=" * 60)
    print("Testing Empty Readings")
    print("=" * 60)

    temp_agg = TemperatureAggregator()
    humidity_agg = HumidityAggregator()

    print("\nWith no readings:")
    assert temp_agg.get_consensus_temperature() is None
    print("  Temperature consensus: None ✓")

    assert humidity_agg.get_consensus_humidity() is None
    print("  Humidity consensus: None ✓")

    print("✓ Empty readings test passed")


if __name__ == "__main__":
    try:
        test_temperature_aggregation()
        test_temperature_without_offsets()
        test_humidity_aggregation()
        test_invalid_readings()
        test_empty_readings()

        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
