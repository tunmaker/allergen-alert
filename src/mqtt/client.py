"""MQTT client with TLS support and Home Assistant integration."""

import json
import logging
import os
import time
from typing import Callable, Dict, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTClient:
    """MQTT client with TLS support and automatic reconnection."""

    def __init__(
        self,
        broker_host: str,
        broker_port: int = 8883,
        username: str = None,
        password: str = None,
        ca_certs: str = None,
        certfile: str = None,
        keyfile: str = None,
        tls_version: str = "tlsv1_2",
        client_id: str = "allergen-alert",
        discovery_prefix: str = "homeassistant",
        data_topic_prefix: str = "home/rpi_aq",
        availability_topic: str = "home/rpi_aq/availability",
    ):
        """
        Initialize MQTT client.

        Args:
            broker_host: MQTT broker hostname or IP
            broker_port: MQTT broker port (default 8883 for TLS)
            username: MQTT username
            password: MQTT password
            ca_certs: Path to CA certificate file
            certfile: Path to client certificate file
            keyfile: Path to client key file
            tls_version: TLS version (tlsv1_2 or tlsv1_3)
            client_id: MQTT client ID
            discovery_prefix: Home Assistant MQTT discovery prefix
            data_topic_prefix: Prefix for data publishing topics
            availability_topic: Topic for online/offline status
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.ca_certs = ca_certs
        self.certfile = certfile
        self.keyfile = keyfile
        self.tls_version = tls_version
        self.client_id = client_id
        self.discovery_prefix = discovery_prefix
        self.data_topic_prefix = data_topic_prefix
        self.availability_topic = availability_topic

        self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
        self.connected = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 300

        # Setup callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        self.client.on_subscribe = self._on_subscribe

        # Custom message handlers
        self.message_handlers: Dict[str, Callable] = {}

    def setup_tls(self):
        """Configure TLS for MQTT connection."""
        if self.ca_certs:
            tls_version_map = {
                "tlsv1_2": mqtt.ssl_tlsv1_2,
                "tlsv1_3": mqtt.ssl_tlsv1_3,
            }
            tls_version_enum = tls_version_map.get(self.tls_version, mqtt.ssl_tlsv1_2)

            self.client.tls_set(
                ca_certs=self.ca_certs,
                certfile=self.certfile,
                keyfile=self.keyfile,
                cert_reqs=mqtt.ssl_cert_required,
                tls_version=tls_version_enum,
                ciphers=None,
            )
            self.client.tls_insecure = False
            logger.info(f"TLS configured with CA cert: {self.ca_certs}")
        else:
            logger.warning("No TLS certificates configured - connection will not be encrypted")

    def setup_auth(self):
        """Configure authentication for MQTT connection."""
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
            logger.info(f"Authentication configured for user: {self.username}")

    def connect(self):
        """Connect to MQTT broker."""
        try:
            self.setup_tls()
            self.setup_auth()

            logger.info(
                f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}"
            )
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            logger.info("MQTT connection attempt started")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    def disconnect(self):
        """Disconnect from MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False
        logger.info("Disconnected from MQTT broker")

    def publish(
        self,
        topic: str,
        payload: any,
        qos: int = 1,
        retain: bool = False,
    ) -> bool:
        """
        Publish message to MQTT topic.

        Args:
            topic: MQTT topic
            payload: Message payload (will be JSON encoded if dict/list)
            qos: Quality of service (0, 1, or 2)
            retain: Retain message on broker

        Returns:
            True if message was published successfully
        """
        try:
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload)
            elif not isinstance(payload, str):
                payload = str(payload)

            result = self.client.publish(topic, payload, qos=qos, retain=retain)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(
                    f"Failed to publish to {topic}: {mqtt.error_string(result.rc)}"
                )
                return False
            return True
        except Exception as e:
            logger.error(f"Error publishing to {topic}: {e}")
            return False

    def publish_discovery(
        self,
        device_id: str,
        sensor_id: str,
        config: Dict,
    ) -> bool:
        """
        Publish Home Assistant MQTT discovery message.

        Args:
            device_id: Device identifier (e.g., 'rpi_main')
            sensor_id: Sensor identifier (e.g., 'temperature')
            config: Discovery configuration dict (name, unit_of_measurement, etc.)

        Returns:
            True if discovery message was published successfully
        """
        topic = f"{self.discovery_prefix}/sensor/{device_id}/{sensor_id}/config"

        # Add required discovery fields
        discovery_config = {
            "unique_id": f"{device_id}_{sensor_id}",
            "object_id": f"{device_id}_{sensor_id}",
            "state_topic": f"{self.data_topic_prefix}/{sensor_id}/state",
            "availability_topic": self.availability_topic,
            "device": {
                "identifiers": [device_id],
                "name": config.get("device_name", "Air Quality Monitor"),
                "model": "Raspberry Pi 4B",
                "manufacturer": "Raspberry Pi Foundation",
            },
            **config,
        }

        logger.debug(f"Publishing discovery for {device_id}/{sensor_id}")
        return self.publish(topic, discovery_config, qos=1, retain=True)

    def publish_data(self, sensor_id: str, value: any) -> bool:
        """
        Publish sensor data.

        Args:
            sensor_id: Sensor identifier
            value: Sensor value

        Returns:
            True if data was published successfully
        """
        topic = f"{self.data_topic_prefix}/{sensor_id}/state"
        return self.publish(topic, value, qos=1, retain=False)

    def publish_availability(self, is_online: bool):
        """
        Publish availability status.

        Args:
            is_online: True if system is online, False if offline
        """
        payload = "online" if is_online else "offline"
        self.publish(self.availability_topic, payload, qos=1, retain=True)

    def subscribe(self, topic: str, callback: Callable = None, qos: int = 1):
        """
        Subscribe to MQTT topic.

        Args:
            topic: MQTT topic (supports wildcards)
            callback: Optional callback function for messages on this topic
            qos: Quality of service (0, 1, or 2)
        """
        self.client.subscribe(topic, qos=qos)
        if callback:
            self.message_handlers[topic] = callback
        logger.debug(f"Subscribed to topic: {topic}")

    def wait_for_connection(self, timeout: int = 30) -> bool:
        """
        Wait for MQTT connection to establish.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if connected, False if timeout
        """
        start_time = time.time()
        while not self.connected:
            if time.time() - start_time > timeout:
                logger.error(f"MQTT connection timeout after {timeout} seconds")
                return False
            time.sleep(0.1)
        logger.info("MQTT connection established")
        return True

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT on_connect callback."""
        if rc == 0:
            self.connected = True
            self.reconnect_delay = 1
            logger.info("Successfully connected to MQTT broker")
            # Publish availability on connect
            self.publish_availability(True)
        else:
            logger.error(f"MQTT connection failed with code {rc}: {mqtt.connack_string(rc)}")

    def _on_disconnect(self, client, userdata, rc):
        """MQTT on_disconnect callback."""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection (code {rc}), will reconnect...")
            # Exponential backoff for reconnection
            wait_time = min(self.reconnect_delay, self.max_reconnect_delay)
            self.reconnect_delay *= 2
            time.sleep(wait_time)
            try:
                self.client.reconnect()
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
        else:
            logger.info("Disconnected from MQTT broker")

    def _on_message(self, client, userdata, msg):
        """MQTT on_message callback."""
        try:
            payload = msg.payload.decode()
            logger.debug(f"Message received on {msg.topic}: {payload}")

            # Call registered handler if exists
            if msg.topic in self.message_handlers:
                self.message_handlers[msg.topic](msg.topic, payload)
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _on_publish(self, client, userdata, mid):
        """MQTT on_publish callback."""
        logger.debug(f"Message published (id: {mid})")

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """MQTT on_subscribe callback."""
        logger.debug(f"Subscription confirmed (id: {mid})")


def create_mqtt_client_from_env() -> MQTTClient:
    """
    Create MQTT client from environment variables.

    Returns:
        Configured MQTTClient instance
    """
    return MQTTClient(
        broker_host=os.getenv("MQTT_BROKER_HOST", "mqtt.proxmox.local"),
        broker_port=int(os.getenv("MQTT_BROKER_PORT", "8883")),
        username=os.getenv("MQTT_USERNAME"),
        password=os.getenv("MQTT_PASSWORD"),
        ca_certs=os.getenv("MQTT_TLS_CA_CERT"),
        certfile=os.getenv("MQTT_TLS_CERTFILE"),
        keyfile=os.getenv("MQTT_TLS_KEYFILE"),
        tls_version=os.getenv("MQTT_TLS_VERSION", "tlsv1_2"),
        client_id=os.getenv("DEVICE_ID", "allergen-alert"),
        discovery_prefix=os.getenv("HA_DISCOVERY_PREFIX", "homeassistant"),
        data_topic_prefix=os.getenv("HA_MQTT_TOPIC_PREFIX", "home/rpi_aq"),
    )
