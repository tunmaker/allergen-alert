#!/usr/bin/env python3
"""Debug script to check system health and sensor status."""

import os
import sys
import subprocess
import time
import socket
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.health_check import SensorHealthMonitor
from utils.data_aggregation import TemperatureAggregator, HumidityAggregator


class HealthDebugger:
    """System health debugging utility."""

    def __init__(self):
        """Initialize debugger."""
        self.project_root = Path(__file__).parent.parent
        self.issues = []
        self.warnings = []

    def check_mosquitto_connectivity(self):
        """Check MQTT broker connectivity."""
        print("\n" + "=" * 60)
        print("MQTT Broker Connectivity Check")
        print("=" * 60)

        broker_host = os.getenv("MQTT_BROKER_HOST", "mqtt.proxmox.local")
        broker_port = int(os.getenv("MQTT_BROKER_PORT", 8883))

        print(f"Target: {broker_host}:{broker_port}")

        try:
            # Try TCP connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((broker_host, broker_port))
            sock.close()

            if result == 0:
                print("✓ TCP connection successful")
                return True
            else:
                print("✗ TCP connection failed")
                self.issues.append(f"Cannot connect to {broker_host}:{broker_port}")
                return False
        except Exception as e:
            print(f"✗ Connection error: {e}")
            self.issues.append(f"MQTT connection error: {e}")
            return False

    def check_certificates(self):
        """Check TLS certificate configuration."""
        print("\n" + "=" * 60)
        print("TLS Certificate Check")
        print("=" * 60)

        ca_cert = os.getenv("MQTT_TLS_CA_CERT")

        if not ca_cert:
            print("⚠ No CA certificate configured")
            self.warnings.append("TLS not fully configured")
            return False

        print(f"CA Certificate: {ca_cert}")

        if not os.path.exists(ca_cert):
            print(f"✗ Certificate file not found: {ca_cert}")
            self.issues.append(f"Missing certificate: {ca_cert}")
            return False

        print("✓ Certificate file exists")

        # Try to validate certificate
        try:
            result = subprocess.run(
                ["openssl", "x509", "-in", ca_cert, "-text", "-noout"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                print("✓ Certificate is valid")
                # Extract expiration date
                for line in result.stdout.split("\n"):
                    if "Not After" in line:
                        print(f"  {line.strip()}")
                return True
            else:
                print(f"✗ Certificate validation failed: {result.stderr}")
                self.issues.append("Invalid certificate")
                return False
        except FileNotFoundError:
            print("⚠ openssl not available for certificate validation")
            self.warnings.append("Cannot validate certificate without openssl")
            return True
        except Exception as e:
            print(f"✗ Error checking certificate: {e}")
            self.issues.append(f"Certificate check failed: {e}")
            return False

    def check_sensors(self):
        """Check if sensors are detected."""
        print("\n" + "=" * 60)
        print("I2C Sensors Detection")
        print("=" * 60)

        try:
            result = subprocess.run(
                ["i2cdetect", "-y", "1"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                print(result.stdout)

                # Check for expected addresses
                expected = {
                    "0x29": "TSL2591",
                    "0x38": "AHT21",
                    "0x53": "ENS160",
                    "0x62": "SCD40",
                    "0x76": "BME680 (option 1)",
                    "0x77": "BME680 (option 2)",
                }

                found = []
                for addr, name in expected.items():
                    if addr in result.stdout:
                        found.append(name)
                        print(f"✓ Found {name} at {addr}")

                if len(found) < 5:
                    missing_count = 6 - len(found)
                    print(f"⚠ Missing {missing_count} sensors")
                    self.warnings.append(
                        f"Not all sensors detected (found {len(found)}/6)"
                    )
                else:
                    print("✓ All expected sensors detected")

                return True
            else:
                print(f"✗ i2cdetect failed: {result.stderr}")
                self.issues.append("I2C detection failed - check if I2C is enabled")
                return False
        except FileNotFoundError:
            print("⚠ i2cdetect not available")
            self.warnings.append("Cannot run i2cdetect")
            return True
        except Exception as e:
            print(f"✗ Error detecting sensors: {e}")
            self.issues.append(f"Sensor detection failed: {e}")
            return False

    def check_service_status(self):
        """Check allergen-alert service status."""
        print("\n" + "=" * 60)
        print("Service Status Check")
        print("=" * 60)

        try:
            result = subprocess.run(
                ["sudo", "systemctl", "status", "allergen-alert"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if "active (running)" in result.stdout:
                print("✓ allergen-alert service is running")
                return True
            elif "inactive" in result.stdout:
                print("⚠ allergen-alert service is not running")
                self.warnings.append("Service not running - start with: sudo systemctl start allergen-alert")
                return False
            else:
                print("⚠ Could not determine service status")
                return True
        except Exception as e:
            print(f"⚠ Cannot check service status: {e}")
            self.warnings.append("Could not verify service status (may need sudo)")
            return True

    def check_logs(self):
        """Display recent service logs."""
        print("\n" + "=" * 60)
        print("Recent Service Logs (last 20 lines)")
        print("=" * 60)

        try:
            result = subprocess.run(
                ["sudo", "journalctl", "-u", "allergen-alert", "-n", "20", "--no-pager"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                print(result.stdout)
                return True
            else:
                print(f"⚠ Could not read logs: {result.stderr}")
                return True
        except Exception as e:
            print(f"⚠ Cannot read logs: {e}")
            self.warnings.append("Could not read service logs")
            return True

    def test_data_aggregation(self):
        """Test data aggregation with sample data."""
        print("\n" + "=" * 60)
        print("Data Aggregation Test")
        print("=" * 60)

        try:
            # Test temperature aggregation
            temp_agg = TemperatureAggregator(use_offsets=True)
            temp_agg.add_reading("temperature", 20.0)
            temp_agg.add_reading("temperature_bme680", 23.0)
            temp_agg.add_reading("temperature_scd40", 21.5)

            consensus = temp_agg.get_consensus_temperature()
            if consensus is not None:
                print(f"✓ Temperature consensus: {consensus}°C")
            else:
                print("✗ Temperature consensus failed")
                self.issues.append("Temperature aggregation failed")

            # Test humidity aggregation
            humidity_agg = HumidityAggregator()
            humidity_agg.add_reading("humidity", 45.0)
            humidity_agg.add_reading("humidity_bme680", 47.0)

            consensus = humidity_agg.get_consensus_humidity()
            if consensus is not None:
                print(f"✓ Humidity consensus: {consensus}%")
            else:
                print("✗ Humidity consensus failed")
                self.issues.append("Humidity aggregation failed")

            return True
        except Exception as e:
            print(f"✗ Data aggregation test failed: {e}")
            self.issues.append(f"Data aggregation error: {e}")
            return False

    def test_health_monitor(self):
        """Test sensor health monitoring."""
        print("\n" + "=" * 60)
        print("Health Monitor Test")
        print("=" * 60)

        try:
            monitor = SensorHealthMonitor(max_consecutive_errors=3)

            # Register sensors
            for sensor in [
                "aht21",
                "ens160",
                "scd40",
                "bme680",
                "tsl2591",
                "pms5003",
            ]:
                monitor.register_sensor(sensor)

            # Simulate some readings
            monitor.record_successful_read("aht21")
            monitor.record_successful_read("ens160")
            monitor.record_error("scd40", "I2C timeout")
            monitor.record_error("scd40", "I2C timeout")

            print(monitor.get_status_report())

            healthy = monitor.get_healthy_sensors()
            unhealthy = monitor.get_unhealthy_sensors()

            print(f"\n✓ Health monitor test passed")
            print(f"  Healthy: {len(healthy)}/6")
            print(f"  Unhealthy: {len(unhealthy)}/6")

            return True
        except Exception as e:
            print(f"✗ Health monitor test failed: {e}")
            self.issues.append(f"Health monitor error: {e}")
            return False

    def generate_report(self):
        """Generate final report."""
        print("\n" + "=" * 60)
        print("HEALTH CHECK SUMMARY")
        print("=" * 60)

        if not self.issues and not self.warnings:
            print("✓ All checks passed!")
            return 0
        else:
            if self.warnings:
                print(f"\n⚠ Warnings ({len(self.warnings)}):")
                for warning in self.warnings:
                    print(f"  - {warning}")

            if self.issues:
                print(f"\n✗ Issues ({len(self.issues)}):")
                for issue in self.issues:
                    print(f"  - {issue}")
                return 1

            return 0

    def run_all_checks(self):
        """Run all health checks."""
        print("Starting Allergen Alert Health Check")
        print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        self.check_mosquitto_connectivity()
        self.check_certificates()
        self.check_sensors()
        self.check_service_status()
        self.check_logs()
        self.test_data_aggregation()
        self.test_health_monitor()

        return self.generate_report()


if __name__ == "__main__":
    debugger = HealthDebugger()
    exit_code = debugger.run_all_checks()
    sys.exit(exit_code)
