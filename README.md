# UK Police – Home Assistant Integration
[![HACS Custom Repository](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://home-assistant.io)
[![GitHub](https://img.shields.io/badge/GitHub-91JJ%2FHA__UK__Police-lightgrey?logo=github)](https://github.com/91JJ/HA_UK_Police)

<p align="center">
  <img src="https://raw.githubusercontent.com/91JJ/HA_UK_Police/main/custom_components/uk_police/brands/logo.png" alt="UK Police Integration" width="420">
</p>

A bespoke Home Assistant integration that surfaces live data from the **[UK Police open data API](https://data.police.uk/docs/)** directly into your HA dashboard. Entirely free, no API key required.

---

## Features

### Setup
- **Auto-detect** your neighbourhood from your HA home location
- **Manual selection** – pick any of the 43+ UK police forces and their neighbourhoods
- Multiple neighbourhoods supported (add the integration again for each area)
- Options flow: adjust history period & stop/search toggle at any time

### Sensors (per neighbourhood)
| Sensor | Description |
|--------|-------------|
| Total Crimes | All crimes in the latest data month |
| Crime Trend | `rising` / `falling` / `stable` vs previous months |
| Monthly Crime Count | Numeric count (great for history graphs) |
| Crimes – *Category* | Individual sensor per crime category (14 categories) |
| Crime Outcomes | Total outcomes recorded + breakdown by outcome type |
| Stop & Searches | Total stop & searches near your location |
| Stop & Search – Object of Search | What was being searched for (most common) |
| Stop & Search – Outcomes | Most common s&s outcome |
| Stop & Search – Ethnicity | Breakdown by self-defined ethnicity, age, gender |
| Neighbourhood Team Size | Number of assigned officers |
| Neighbourhood Team | Officers' names (all in attributes) |
| Upcoming Events | Count of planned public events/meetings |
| Next Event | Title & date of the next event |
| Policing Priorities | Number of active priorities |
| Priority Issues | Current priority issue text + full list in attributes |
| Force Telephone | Non-emergency number (101 default) |
| Force Description | Full force description text + URL & telephone in attributes |
| Force Engagement Channels | Count of social media / online channels + full `links` dict in attributes |
| Data Last Updated | When the API last received new data |

### Binary Sensors
| Sensor | Triggers when… |
|--------|----------------|
| Upcoming Events | There is at least one scheduled event |
| High Crime Alert | Latest month crime count ≥ 50 |
| Active Policing Priorities | Force has declared active priorities |
| Rising Crime Trend | Crime is trending upward over chosen history window |
| Neighbourhood Team Assigned | At least one officer is assigned |

### Map (Geo Location)
| Entity | Description |
|--------|-------------|
| Crime Category Pins | One map pin per crime category (e.g. *Anti-social Behaviour (21)*), positioned at the centroid of all crimes in that category. The pin's attributes list every incident with street name and outcome. |
| Individual Crime Pins | One pin per crime incident, labelled *Crime Type – Street Name*. Available when **Individual incidents** map mode is selected. |

Crime pins appear automatically on the Home Assistant **Map** dashboard view. To add them to a Lovelace card use `type: map` with `geo_location_sources: [uk_police_YOUR_FORCE_YOUR_NEIGHBOURHOOD]`.

> **Per-location source** — each configured area gets its own geo_location source name in the format `uk_police_{force}_{neighbourhood}` (e.g. `uk_police_metropolitan_E05013580`). The easiest way to find the exact value for your area is to open any of its sensors in **Developer Tools → States** and look at the `source` attribute — it shows the full ready-to-paste string. This means you can show pins from specific locations separately on different map cards. To show all UK Police pins together simply add each source name to the `geo_location_sources` list.

> **Distances are shown in miles** — appropriate for the UK. Each pin displays how far it is from your HA home location (e.g. `0.34 mi`).

> **Map pin style is configurable** — choose between **Grouped by category** (one pin per crime type, ideal for a tidy overview) or **Individual incidents** (one pin per crime, shows exact street-level locations). Switch between modes at any time via **Settings → Devices & Services → UK Police → Configure**. Changing mode automatically clears stale entities from the registry.

> **Persistent ID** — the UK Police API assigns a `persistent_id` (UUID) to certain crimes. When present, this is used as the entity’s unique identifier so it stays stable across monthly data refreshes, and it lets you look up the full case history via `GET /outcomes-for-crime/{persistent_id}`.

### Services
| Service | Description |
|---------|-------------|
| `uk_police.refresh` | Force-refresh all (or one) configured area |
| `uk_police.get_crimes` | Fires `uk_police_crimes_data` event with raw crime list |
| `uk_police.get_stop_search` | Fires `uk_police_stop_search_data` event with raw s&s list |

### Data Refresh
The integration checks for new data **once per day** (instead of every hour). On each daily wake-up it makes a single lightweight call to `crime-last-updated`. If the API date is unchanged, the full fetch is skipped and cached values are kept — meaning sensors only update on the ~2-monthly cadence when the police actually publish new data. You can always trigger an immediate refresh via the `uk_police.refresh` service.

---

## Installation

### Via HACS (recommended)
1. In HACS → **Integrations** → three-dot menu → **Custom repositories**
2. Add `https://github.com/91JJ/HA_UK_Police` as type **Integration**
3. Search for *UK Police* and install
4. Restart Home Assistant

### Manual
1. Copy `custom_components/uk_police/` into your HA `config/custom_components/` folder
2. Restart Home Assistant

---

## Configuration

1. **Settings → Devices & Services → Add Integration → UK Police**
2. Choose **Auto-detect** (uses your HA home coordinates) or **Manual**
3. If manual: pick your force then neighbourhood
4. Confirm and set options:
   - **Include Stop & Search data** – toggle on/off
   - **Crime history period** – 1, 3, 6, or 12 months (used for trend calculation)
   - **Map pin style** – `Grouped by category` or `Individual incidents`

All options can be changed at any time via **Settings → Devices & Services → UK Police → Configure**.

---

## Finding Your Entity Prefix

All entity IDs follow the pattern `sensor.{force}_{neighbourhood}_{sensor_name}`.  
To find your exact prefix:
1. Go to **Developer Tools → States**
2. Filter by `uk_police` or search for `total_crimes`
3. Your prefix is everything before `_total_crimes` — e.g., `metropolitan_west_end`

---

## Example Dashboard (Lovelace)

```yaml
# Replace YOUR_PREFIX with your entity prefix (e.g. metropolitan_west_end)
# Find it in Developer Tools → States by searching for 'total_crimes'

type: vertical-stack
cards:

  # --- Force header ---
  - type: markdown
    content: >
      ## 🏛️ {{ state_attr('sensor.YOUR_PREFIX_force_description', 'url') | regex_replace('https?://', '') | replace('/', '') }}

      {{ state_attr('sensor.YOUR_PREFIX_force_description', 'full_description') }}


      📞 **{{ states('sensor.YOUR_PREFIX_force_telephone') }}**
      &nbsp;&nbsp;🌐 [Force website]({{ state_attr('sensor.YOUR_PREFIX_force_description', 'url') }})


      {% set links = state_attr('sensor.YOUR_PREFIX_force_engagement_channels', 'links') %}
      {% if links %}
      **Connect:** {% for title, url in links.items() %}[{{ title }}]({{ url }}){% if not loop.last %} · {% endif %}{% endfor %}
      {% endif %}

  # --- Crime overview ---
  - type: entities
    title: 🚔 Local Crime Overview
    entities:
      - sensor.YOUR_PREFIX_total_crimes
      - sensor.YOUR_PREFIX_crime_trend
      - sensor.YOUR_PREFIX_stop_searches
      - binary_sensor.YOUR_PREFIX_high_crime_alert
      - binary_sensor.YOUR_PREFIX_rising_crime_trend

  - type: history-graph
    title: Crime History
    entities:
      - sensor.YOUR_PREFIX_monthly_crime_count

  - type: map
    title: 🗺️ Crime Map
    geo_location_sources:
      - uk_police_YOUR_FORCE_YOUR_NEIGHBOURHOOD   # e.g. uk_police_metropolitan_west_end
    default_zoom: 13
    aspect_ratio: "16:9"

  - type: entities
    title: 👮 Neighbourhood Team
    entities:
      - sensor.YOUR_PREFIX_neighbourhood_team_size
      - sensor.YOUR_PREFIX_neighbourhood_team
      - sensor.YOUR_PREFIX_upcoming_events
      - sensor.YOUR_PREFIX_next_event
      - sensor.YOUR_PREFIX_policing_priorities
```

---

## Data Sources

All data is sourced from [data.police.uk](https://data.police.uk) — the official open data platform for UK police forces.

## License

MIT
