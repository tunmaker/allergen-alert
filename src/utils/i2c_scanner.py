"""I2C device scanner for sensor detection."""

import logging

try:
    import smbus2
except ImportError:
    smbus2 = None

logger = logging.getLogger(__name__)


def scan_i2c_devices(bus: int = 1) -> dict:
    """
    Scan I2C bus for connected devices.

    Args:
        bus: I2C bus number (default 1 on Raspberry Pi)

    Returns:
        Dict of address -> device name
    """
    if smbus2 is None:
        logger.error("smbus2 not installed")
        return {}

    devices = {}
    known_devices = {
        0x29: "TSL2591 (Light Sensor)",
        0x38: "AHT21 (Temperature/Humidity)",
        0x53: "ENS160 (Air Quality)",
        0x62: "SCD40 (CO2)",
        0x76: "BME680 (Environmental)",
        0x77: "BME680 (Environmental)",
    }

    try:
        bus_obj = smbus2.SMBus(bus)

        print(f"\nScanning I2C bus {bus}...\n")
        print("Address | Hex  | Device")
        print("--------|------|-----------------------------------")

        for addr in range(0x03, 0x78):
            try:
                # Try to read from this address
                bus_obj.read_byte(addr)
                device_name = known_devices.get(addr, "Unknown Device")
                devices[addr] = device_name
                print(f"{addr:7d} | 0x{addr:02x} | {device_name}")
            except Exception:
                pass

        bus_obj.close()

        print("\n" + "=" * 40)
        if devices:
            print(f"Found {len(devices)} device(s)")
            print("\nExpected devices for allergen-alert:")
            print("  0x29: TSL2591 (Light)")
            print("  0x38: AHT21 (Temp/Humidity)")
            print("  0x53: ENS160 (Air Quality)")
            print("  0x62: SCD40 (CO2)")
            print("  0x76 or 0x77: BME680 (Environmental)")
        else:
            print("No I2C devices found")
            print("Check I2C is enabled: sudo raspi-config")
            print("Check wiring and power connections")

        return devices

    except Exception as e:
        logger.error(f"Error scanning I2C bus: {e}")
        print(f"Error: Could not access I2C bus {bus}")
        print("Make sure I2C is enabled and you have appropriate permissions")
        return {}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scan_i2c_devices()
