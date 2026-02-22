# Home Assistant Automations Guide

Complete guide for setting up Home Assistant automations to automatically control climate, ventilation, and air purification systems based on Allergen Alert sensor data.

## Quick Start

### 1. Copy Automation Templates

Copy the automations from `config/home-assistant-automations.yaml` to your Home Assistant configuration.

**Option A: Direct Include**

Add to `configuration.yaml`:
```yaml
automation: !include config/home-assistant-automations.yaml
```

**Option B: Manual Copy**

Copy individual automation YAML into Home Assistant UI:
1. Go to **Settings → Automations & Scenes → Create Automation**
2. Click **Edit in YAML**
3. Paste automation YAML
4. Save

### 2. Update Entity IDs

Replace placeholder entity IDs with your actual devices:

```
climate.living_room          → Your thermostat/HVAC
cover.living_room_window     → Smart window/blind
switch.ventilation_fan       → Ventilation fan switch
switch.ventilation_fan_boost → Ventilation boost mode
fan.air_purifier             → Air purifier fan
notify.mobile_app            → Your notification service
weather.home                 → Your weather integration
```

### 3. Test Automations

1. Go to **Settings → Automations & Scenes**
2. Find your automation
3. Click the three dots → **Test this automation**
4. Verify expected action occurs

## Temperature Control Automations

### Heating - Low Temperature Alert

**When:** Temperature drops below 18°C for 5 minutes
**Then:**
- Set thermostat to 21°C in heating mode
- Send mobile notification

**Customization:**

```yaml
automation climate_heating_custom:
  alias: "Custom Heating Trigger"
  trigger:
    platform: numeric_state
    entity_id: sensor.temperature_consensus
    below: 16  # Change temperature threshold
    for:
      minutes: 10  # Change wait time
  action:
    service: climate.set_temperature
    target:
      entity_id: climate.master_bedroom  # Your thermostat
    data:
      temperature: 22  # Your target temp
      hvac_mode: heat
```

**Thresholds by Climate:**
- Cold climate: Trigger at 15°C → Target 22°C
- Temperate: Trigger at 18°C → Target 21°C
- Warm climate: Trigger at 20°C → Target 23°C

### Cooling - High Temperature Alert

**When:** Temperature exceeds 26°C for 5 minutes
**Then:**
- Set thermostat to 23°C in cooling mode
- Send mobile notification

**Customization for Dehumidification:**

If you have separate humidity control:

```yaml
automation climate_cooling_dehumidify:
  alias: "Cooling + Dehumidification"
  trigger:
    platform: numeric_state
    entity_id: sensor.overall_aqi
    above: 100
  action:
    - service: climate.set_temperature
      target:
        entity_id: climate.living_room
      data:
        temperature: 22
        hvac_mode: cool
    - service: climate.set_humidity
      target:
        entity_id: climate.living_room
      data:
        humidity: 45  # Dry out air
```

### Humidity Target Maintenance

**When:** Humidity exceeds 65% for 10 minutes
**Then:**
- Set humidity target to 50%
- Increase ventilation

**Humidity Comfort Ranges:**

| Condition | RH Range | Recommendation |
|-----------|----------|-----------------|
| Too Dry | < 30% | Add humidifier, drink water |
| Comfortable | 40-60% | No action needed |
| Moderate Humidity | 60-70% | Increase ventilation |
| High Humidity | > 70% | Active dehumidification |
| Mold Risk | > 80% | Maximum ventilation |

## Ventilation Control Automations

### High CO2 - Open Windows

**When:** CO2 exceeds 1000 ppm for 5 minutes
**Then:**
- Open smart windows/vents
- Turn on ventilation fan
- Send alert notification

**Why 1000 ppm?**
- < 600 ppm: Fresh outdoor air or well ventilated
- 600-1000 ppm: Acceptable indoor, some CO2 buildup
- 1000-1500 ppm: Poor ventilation, fatigue/headaches
- > 1500 ppm: Severe, immediate ventilation needed

**Advanced: Conditional Ventilation**

Don't open windows if outside air quality is worse:

```yaml
automation ventilation_smart_open:
  alias: "Smart Window Opening"
  trigger:
    platform: numeric_state
    entity_id: sensor.co2_scd40
    above: 1000
  condition:
    - condition: numeric_state
      entity_id: sensor.outdoor_pm25
      below: 25  # Only if outdoor air is better
    - condition: state
      entity_id: weather.home
      state:
        - "clear"
        - "sunny"
        - "cloudy"  # Not rainy/snowy
  action:
    - service: cover.open_cover
      target:
        entity_id: cover.living_room_window
    - service: switch.turn_on
      target:
        entity_id: switch.ventilation_fan
```

### CO2 Normal - Close Windows

**When:** CO2 drops below 600 ppm for 10 minutes
**Then:**
- Close windows
- Turn off ventilation
- Save energy

**Time-based Override:**

Close windows at night regardless of CO2:

```yaml
automation ventilation_nighttime_security:
  alias: "Night Security Window Closing"
  trigger:
    platform: time
    at: "22:00:00"  # 10 PM
  action:
    - service: cover.close_cover
      target:
        entity_id: cover.living_room_window
    - service: switch.turn_off
      target:
        entity_id: switch.ventilation_fan
```

### Poor Air Quality - Maximum Ventilation

**When:** AQI exceeds 100 (unhealthy for sensitive groups) for 3 minutes
**Then:**
- Maximum ventilation boost
- Open all windows
- Set HVAC to fresh air mode
- Send urgent notification

**AQI Thresholds:**
- 0-50: Good - Natural ventilation sufficient
- 51-100: Moderate - Standard ventilation
- 101-150: Unhealthy for Sensitive - Increase ventilation
- 151-200: Unhealthy - Maximum ventilation
- 200+: Very Unhealthy/Hazardous - Extreme measures

### Prevent Energy Waste

Combine conditions to avoid unnecessary cycling:

```yaml
automation ventilation_efficiency:
  alias: "Efficient Ventilation Control"
  trigger:
    platform: state
    entity_id: binary_sensor.anyone_home
    from: "off"
    to: "on"
  action:
    - choose:
        - conditions:
            - condition: numeric_state
              entity_id: sensor.co2_scd40
              above: 800
          sequence:
            - service: switch.turn_on
              target:
                entity_id: switch.ventilation_fan
        - conditions:
            - condition: numeric_state
              entity_id: sensor.co2_scd40
              below: 600
          sequence:
            - service: switch.turn_off
              target:
                entity_id: switch.ventilation_fan
```

## Air Purifier Control Automations

### High PM2.5 - Start Purifier

**When:** PM2.5 exceeds 35 µg/m³ for 2 minutes
**Then:**
- Turn on air purifier at high speed
- Send notification

**PM2.5 Health Categories:**

| Level | Category | Recommendation |
|-------|----------|-----------------|
| 0-12 | Good | Enjoy outdoor activities |
| 12-35 | Moderate | Sensitive groups limit activity |
| 35-55 | Unhealthy for Sensitive | Sensitive groups avoid outdoor |
| 55-150 | Unhealthy | General public should avoid outdoor |
| 150-250 | Very Unhealthy | Everyone should avoid outdoor |
| 250+ | Hazardous | Extreme indoor air filtration |

### Adaptive Purifier Speed

Automatically adjust purifier speed based on PM2.5:

```yaml
automation air_purifier_adaptive:
  alias: "Adaptive Air Purifier Speed"
  trigger:
    platform: state
    entity_id: sensor.pm2_5
  action:
    - choose:
        # Off when air is clean
        - conditions:
            - condition: numeric_state
              entity_id: sensor.pm2_5
              below: 12
          sequence:
            - service: fan.turn_off
              target:
                entity_id: fan.air_purifier

        # Low speed for moderate
        - conditions:
            - condition: numeric_state
              entity_id: sensor.pm2_5
              above: 12
              below: 25
          sequence:
            - service: fan.turn_on
              target:
                entity_id: fan.air_purifier
            - service: fan.set_percentage
              target:
                entity_id: fan.air_purifier
              data:
                percentage: 30  # Quiet operation

        # Medium speed for concerning
        - conditions:
            - condition: numeric_state
              entity_id: sensor.pm2_5
              above: 25
              below: 50
          sequence:
            - service: fan.set_percentage
              target:
                entity_id: fan.air_purifier
              data:
                percentage: 65  # Balanced

        # High speed for unhealthy
        - conditions:
            - condition: numeric_state
              entity_id: sensor.pm2_5
              above: 50
          sequence:
            - service: fan.set_percentage
              target:
                entity_id: fan.air_purifier
              data:
                percentage: 100  # Maximum
    default:
      - service: fan.turn_off
        target:
          entity_id: fan.air_purifier
```

### VOC Detection - Maximum Purification

**When:** TVOC exceeds 300 ppb (strong odors detected)
**Then:**
- Run purifier at maximum
- Increase ventilation
- Send alert

**TVOC Sources:**
- Cleaning products: 100-500 ppb
- Cooking: 200-800 ppb
- Off-gassing (new furniture/paint): 500-2000 ppb
- Damage/mold: 1000+ ppb

## Combined Climate Automations

### Comprehensive Response to Poor Air Quality

When AQI > 150 (Very Unhealthy):
1. Maximum ventilation (windows open)
2. Air purifier at 100% speed
3. HVAC in fresh air mode
4. Urgent mobile alert

This automation is critical for health protection.

### Optimize When Air is Good

When AQI < 50 (Good) during daylight:
1. Close windows
2. Set ideal temperature (22°C)
3. Set ideal humidity (50%)
4. Turn off air purifier
5. Confirmation notification

Balances comfort, health, and energy efficiency.

### Sleep Mode Optimization

```yaml
automation climate_sleep_optimization:
  alias: "Sleep Mode Optimization"
  trigger:
    platform: time
    at: "22:00:00"  # 10 PM
  condition:
    - condition: state
      entity_id: binary_sensor.anyone_home
      state: "on"
  action:
    # Optimal sleep conditions
    - service: climate.set_temperature
      target:
        entity_id: climate.bedroom
      data:
        temperature: 18  # Cooler for sleep

    # Close all ventilation
    - service: cover.close_cover
      target:
        entity_id: cover.bedroom_window

    # Turn off air purifier (quiet)
    - service: fan.turn_off
      target:
        entity_id: fan.air_purifier

    # Mute notifications
    - service: input_boolean.turn_off
      target:
        entity_id: input_boolean.air_quality_alerts
```

## Notification Configuration

### Required: Set Up Notification Service

Mobile app notifications (recommended):

```yaml
notify:
  - platform: mobile_app
    name: mobile_app
```

Or Telegram:

```yaml
notify:
  - platform: telegram
    name: telegram
    chat_id: YOUR_CHAT_ID
    api_key: YOUR_BOT_TOKEN
```

### Notification Templates

Create reusable templates in `automations.yaml`:

```yaml
script:
  notify_air_quality:
    description: "Notify about air quality"
    fields:
      aqi_value:
        description: "Current AQI"
      message_color:
        description: "Color (red/orange/yellow)"
    sequence:
      - service: notify.mobile_app
        data:
          title: "Air Quality Alert"
          message: "AQI: {{ aqi_value }}"
          data:
            color: "{{ message_color }}"
            priority: "high"
```

## Advanced: Scene-Based Automation

Group multiple actions into scenes:

```yaml
scene:
  living_room_fresh_air:
    name: "Fresh Air Mode"
    entities:
      cover.living_room_window:
        state: open
      switch.ventilation_fan:
        state: on
      fan.air_purifier:
        state: on
      climate.living_room:
        temperature: 22
        hvac_mode: cool_air

  living_room_comfort:
    name: "Comfort Mode"
    entities:
      cover.living_room_window:
        state: closed
      switch.ventilation_fan:
        state: off
      fan.air_purifier:
        state: off
      climate.living_room:
        temperature: 22
        humidity: 50
```

Then trigger scenes in automations:

```yaml
automation activate_fresh_air:
  trigger:
    platform: numeric_state
    entity_id: sensor.overall_aqi
    above: 100
  action:
    service: scene.turn_on
    target:
      entity_id: scene.living_room_fresh_air
```

## Testing & Troubleshooting

### Test Individual Automation

```yaml
# In Developer Tools → YAML
service: automation.trigger
target:
  entity_id: automation.climate_heating_low_temperature
```

### Debug Automation Issues

1. Check **Settings → Automations & Scenes → automation name**
2. Look for error traces
3. Enable debug logging:

```yaml
logger:
  logs:
    homeassistant.automation: debug
```

View logs in **Settings → System → Logs**

### Common Issues

**Automation not triggering:**
- Verify trigger entity exists: Go to **Developer Tools → States**
- Check numeric_state has correct entity_id
- Verify value matches condition (>= or > vs < or <=)
- Check time-based conditions (after/before)

**Action not executing:**
- Verify target entity_id exists
- Check entity state with Developer Tools
- Ensure service call syntax is correct
- Check service parameters match entity type

**Too many notifications:**
- Add `for:` clause to avoid rapid triggers
- Add conditions to prevent unnecessary alerts
- Adjust thresholds to be less sensitive

## Performance Optimization

### Reduce Automation Load

Group related automations:

```yaml
automation: !include automations/climate_control.yaml
automation: !include automations/ventilation_control.yaml
automation: !include automations/air_purifier_control.yaml
automation: !include automations/health_alerts.yaml
```

### Avoid Repetitive Triggering

Use `for:` clause on numeric_state triggers:

```yaml
trigger:
  platform: numeric_state
  entity_id: sensor.pm2_5
  above: 35
  for:
    minutes: 2  # Only trigger if sustained for 2 minutes
```

This prevents flaky sensor readings from causing unwanted actions.

## Next Steps

1. **Start simple**: Get 1-2 automations working first
2. **Test thoroughly**: Verify each automation in multiple scenarios
3. **Expand gradually**: Add more automations as you gain confidence
4. **Tune thresholds**: Adjust values based on your environment
5. **Create custom logic**: Adapt automations to your specific needs

## Examples by Use Case

### Allergy Sufferer
- Lower PM2.5 threshold (20 µg/m³)
- More aggressive air purifier
- Window opening based on outdoor PM2.5

### Hot/Humid Climate
- Focus on dehumidification and ventilation
- Lower temperature thresholds
- Monitor TVOC from AC use

### Cold/Dry Climate
- Focus on heating and humidity
- Higher humidity target (55-60%)
- Less aggressive ventilation

### Office/Commercial
- Schedule-based operation
- Occupancy-aware automations
- Energy efficiency focus

## Support

For issues with automations:
1. Check Home Assistant logs
2. Test individual components
3. Review automation YAML syntax
4. Verify entity_ids are correct
5. Check conditions and triggers
