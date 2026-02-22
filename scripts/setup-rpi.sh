#!/bin/bash
# Setup script for Raspberry Pi - Allergen Alert

set -e

echo "========================================="
echo "Allergen Alert - Raspberry Pi Setup"
echo "========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
   echo "This script must be run as root (sudo)"
   exit 1
fi

# Update system
echo ""
echo "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install required system packages
echo ""
echo "Installing required packages..."
apt-get install -y \
    python3-pip \
    python3-dev \
    i2c-tools \
    python3-smbus \
    git \
    curl \
    wget

# Enable I2C interface
echo ""
echo "Enabling I2C interface..."
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" >> /boot/config.txt
    echo "I2C enabled in /boot/config.txt"
else
    echo "I2C already enabled"
fi

# Enable UART for PMS5003 serial communication
echo ""
echo "Enabling UART interface..."
if ! grep -q "^enable_uart=1" /boot/config.txt; then
    echo "enable_uart=1" >> /boot/config.txt
    echo "UART enabled in /boot/config.txt"
else
    echo "UART already enabled"
fi

# Disable serial login shell but enable serial port hardware
echo ""
echo "Configuring UART (disabling login shell, enabling hardware)..."
systemctl disable serial-getty@ttyS0.service 2>/dev/null || true

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install --upgrade pip setuptools wheel
pip3 install paho-mqtt==1.7.1 python-dotenv==1.0.1 PyYAML==6.0.1 smbus2==0.4.2 pyserial==3.5 numpy==1.26.4

# Install Adafruit libraries
echo ""
echo "Installing Adafruit sensor libraries..."
pip3 install \
    adafruit-circuitpython-bme680==3.8.5 \
    adafruit-circuitpython-tsl2591==1.4.5 \
    adafruit-circuitpython-am2320==2.0.4

# Create allergen-alert user
echo ""
echo "Creating allergen-alert user..."
if ! id "allergen-alert" &>/dev/null; then
    useradd -r -s /bin/bash -d /opt/allergen-alert -m allergen-alert
    echo "User allergen-alert created"
else
    echo "User allergen-alert already exists"
fi

# Add allergen-alert user to i2c and dialout groups
echo ""
echo "Adding allergen-alert to i2c and dialout groups..."
usermod -a -G i2c,dialout allergen-alert

# Create application directory
echo ""
echo "Setting up application directory..."
mkdir -p /opt/allergen-alert
cp -r ../* /opt/allergen-alert/
chown -R allergen-alert:allergen-alert /opt/allergen-alert
chmod +x /opt/allergen-alert/scripts/*.py
chmod +x /opt/allergen-alert/scripts/*.sh

# Create log directory
mkdir -p /var/log
touch /var/log/allergen-alert.log
chown allergen-alert:allergen-alert /var/log/allergen-alert.log
chmod 644 /var/log/allergen-alert.log

# Setup certificates directory
echo ""
echo "Setting up certificates directory..."
mkdir -p /etc/allergen-alert/certs
chmod 700 /etc/allergen-alert/certs
chown -R allergen-alert:allergen-alert /etc/allergen-alert

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Copy MQTT TLS certificates to /etc/allergen-alert/certs/"
echo "2. Edit /opt/allergen-alert/.env with MQTT broker details"
echo "3. Run I2C scanner to verify sensors:"
echo "   sudo python3 /opt/allergen-alert/scripts/i2c-scanner.py"
echo "4. Test MQTT connection:"
echo "   python3 /opt/allergen-alert/scripts/test-mqtt-connection.py"
echo "5. Install systemd service:"
echo "   sudo cp /opt/allergen-alert/systemd/allergen-alert.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable allergen-alert.service"
echo "   sudo systemctl start allergen-alert.service"
echo ""
echo "Monitor logs with:"
echo "   sudo journalctl -u allergen-alert.service -f"
echo ""
