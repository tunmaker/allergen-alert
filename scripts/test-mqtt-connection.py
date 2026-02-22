#!/usr/bin/env python3
"""Test MQTT connection with TLS."""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from src.mqtt.client import create_mqtt_client_from_env
from src.mqtt.discovery import DiscoveryPublisher

def test_mqtt_connection():
    """Test MQTT connection and discovery."""
    print("=" * 60)
    print("Testing MQTT Connection")
    print("=" * 60)
    print()

    # Create MQTT client
    print("Creating MQTT client...")
    try:
        mqtt_client = create_mqtt_client_from_env()
    except Exception as e:
        print(f"Failed to create MQTT client: {e}")
        return False

    # Connect to broker
    print("Connecting to MQTT broker...")
    try:
        mqtt_client.connect()
    except Exception as e:
        print(f"Failed to connect: {e}")
        return False

    # Wait for connection
    print("Waiting for connection (10 seconds timeout)...")
    if not mqtt_client.wait_for_connection(timeout=10):
        print("Connection timeout!")
        mqtt_client.disconnect()
        return False

    print("✓ Connected successfully!")
    print()

    # Test publishing discovery
    print("Testing MQTT discovery publish...")
    discovery = DiscoveryPublisher(
        mqtt_client,
        device_id="rpi_test",
        device_name="Test Air Quality Monitor"
    )

    if discovery.publish_sensor_discovery("temperature"):
        print("✓ Discovery message published successfully")
    else:
        print("✗ Failed to publish discovery message")
        mqtt_client.disconnect()
        return False

    print()

    # Test data publish
    print("Testing sensor data publish...")
    if mqtt_client.publish_data("temperature", 22.5):
        print("✓ Test data published successfully")
    else:
        print("✗ Failed to publish test data")
        mqtt_client.disconnect()
        return False

    print()

    # Test availability
    print("Publishing availability status...")
    mqtt_client.publish_availability(True)
    print("✓ Availability published")
    print()

    # Cleanup
    print("Disconnecting...")
    mqtt_client.disconnect()

    print()
    print("=" * 60)
    print("MQTT Connection Test Complete!")
    print("=" * 60)
    print()
    print("Configuration summary:")
    print(f"  Broker:    {os.getenv('MQTT_BROKER_HOST', 'mqtt.proxmox.local')}")
    print(f"  Port:      {os.getenv('MQTT_BROKER_PORT', '8883')}")
    print(f"  Username:  {os.getenv('MQTT_USERNAME', 'N/A')}")
    print(f"  TLS:       {'Enabled' if os.getenv('MQTT_TLS_CA_CERT') else 'Disabled'}")
    print()

    return True

if __name__ == "__main__":
    success = test_mqtt_connection()
    sys.exit(0 if success else 1)
