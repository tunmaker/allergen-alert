#!/bin/bash
# Generate TLS certificates for MQTT broker and clients
# This creates self-signed certificates for testing/home use

set -e

echo "========================================="
echo "MQTT TLS Certificate Generation"
echo "========================================="
echo ""

# Create certificates directory
CERT_DIR="${1:-.}/certs"
mkdir -p "$CERT_DIR"

echo "Certificates will be saved to: $CERT_DIR"
echo ""

# Certificate validity in days
VALID_DAYS=365

# 1. Create CA (Certificate Authority)
echo "1. Generating CA (Certificate Authority)..."
openssl genrsa -out "$CERT_DIR/ca.key" 2048
openssl req -new -x509 -days $VALID_DAYS -key "$CERT_DIR/ca.key" -out "$CERT_DIR/ca.crt" \
    -subj "/C=US/ST=Home/L=Home/O=Home Assistant/CN=Home Assistant CA"
echo "   CA certificate created"

# 2. Create Server (Broker) Certificate
echo ""
echo "2. Generating Server (Mosquitto Broker) Certificate..."
openssl genrsa -out "$CERT_DIR/server.key" 2048
openssl req -new -key "$CERT_DIR/server.key" -out "$CERT_DIR/server.csr" \
    -subj "/C=US/ST=Home/L=Home/O=Home Assistant/CN=mqtt.proxmox.local"
openssl x509 -req -in "$CERT_DIR/server.csr" \
    -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" \
    -CAcreateserial -out "$CERT_DIR/server.crt" -days $VALID_DAYS
rm "$CERT_DIR/server.csr"
echo "   Server certificate created"

# 3. Create Client Certificate
echo ""
echo "3. Generating Client (Raspberry Pi) Certificate..."
openssl genrsa -out "$CERT_DIR/client.key" 2048
openssl req -new -key "$CERT_DIR/client.key" -out "$CERT_DIR/client.csr" \
    -subj "/C=US/ST=Home/L=Home/O=Home Assistant/CN=rpi-air-quality"
openssl x509 -req -in "$CERT_DIR/client.csr" \
    -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" \
    -CAcreateserial -out "$CERT_DIR/client.crt" -days $VALID_DAYS
rm "$CERT_DIR/client.csr"
echo "   Client certificate created"

# Set correct permissions
chmod 644 "$CERT_DIR/ca.crt"
chmod 644 "$CERT_DIR/server.crt"
chmod 600 "$CERT_DIR/server.key"
chmod 644 "$CERT_DIR/client.crt"
chmod 600 "$CERT_DIR/client.key"

echo ""
echo "========================================="
echo "Certificate Generation Complete!"
echo "========================================="
echo ""
echo "Generated certificates:"
echo "  CA Certificate:      $CERT_DIR/ca.crt"
echo "  Server Certificate:  $CERT_DIR/server.crt"
echo "  Server Key:          $CERT_DIR/server.key (KEEP SECURE)"
echo "  Client Certificate:  $CERT_DIR/client.crt"
echo "  Client Key:          $CERT_DIR/client.key (KEEP SECURE)"
echo ""
echo "Next steps:"
echo ""
echo "For Mosquitto Broker (on Proxmox/Home Assistant VM):"
echo "1. Copy to /etc/mosquitto/certs/:"
echo "   sudo cp $CERT_DIR/ca.crt /etc/mosquitto/certs/"
echo "   sudo cp $CERT_DIR/server.crt /etc/mosquitto/certs/"
echo "   sudo cp $CERT_DIR/server.key /etc/mosquitto/certs/"
echo "   sudo chown mosquitto:mosquitto /etc/mosquitto/certs/*"
echo "   sudo chmod 600 /etc/mosquitto/certs/server.key"
echo ""
echo "2. Update /etc/mosquitto/mosquitto.conf:"
echo "   listener 8883"
echo "   protocol mqtt"
echo "   cafile /etc/mosquitto/certs/ca.crt"
echo "   certfile /etc/mosquitto/certs/server.crt"
echo "   keyfile /etc/mosquitto/certs/server.key"
echo "   allow_anonymous false"
echo "   password_file /etc/mosquitto/passwd"
echo ""
echo "3. Restart Mosquitto:"
echo "   sudo systemctl restart mosquitto"
echo ""
echo "For Raspberry Pi Client:"
echo "1. Copy to /etc/allergen-alert/certs/:"
echo "   sudo cp $CERT_DIR/ca.crt /etc/allergen-alert/certs/"
echo "   sudo cp $CERT_DIR/client.crt /etc/allergen-alert/certs/"
echo "   sudo cp $CERT_DIR/client.key /etc/allergen-alert/certs/"
echo "   sudo chown allergen-alert:allergen-alert /etc/allergen-alert/certs/*"
echo "   sudo chmod 600 /etc/allergen-alert/certs/client.key"
echo ""
echo "For Home Assistant:"
echo "1. In Home Assistant Settings → Devices & Services → MQTT:"
echo "   Broker: mqtt.proxmox.local"
echo "   Port: 8883"
echo "   TLS: Enable"
echo "   CA Certificate: copy ca.crt content"
echo ""
