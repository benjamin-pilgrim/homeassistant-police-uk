# Police.uk Local Crime

[![HACS Custom Repository](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://home-assistant.io)

Police.uk Local Crime is a Home Assistant custom integration for local crime data from the official [Police.uk open data API](https://data.police.uk/docs/). It is a breaking, crime-only fork of the upstream `uk_police` integration and uses the domain `police_uk_local`.

This fork is not a drop-in migration target. Existing `uk_police` users should remove the old integration and add this one as a new integration if they want the narrowed crime-only surface.

## Scope

Included:

- Latest Police.uk data month.
- Total crimes for the configured area.
- One enabled crime count sensor per Police.uk crime category, excluding `all-crime`.
- Optional grouped-by-category or individual incident `geo_location` map pins.
- Optional auto-detect radius mode around the Home Assistant home location.
- `police_uk_local.get_crimes`, which fires the latest raw crime records capped at 200 records.

Removed from this fork:

- Binary sensors.
- Stop/search data and services.
- Outcomes aggregation.
- Force, team, event, priority, engagement, trend, and monthly-count helper sensors.

Home Assistant helpers, templates, statistics sensors, and automations should handle averages, unusualness, alert labels, and other policy decisions.

## Installation

### HACS

1. In HACS, open Integrations, then Custom repositories.
2. Add `https://github.com/benjamin-pilgrim/homeassistant-police-uk` as type Integration.
3. Install Police.uk Local Crime.
4. Restart Home Assistant.

### Manual

Copy `custom_components/police_uk_local/` into your Home Assistant `config/custom_components/` folder, then restart Home Assistant.

## Configuration

Add the integration from Settings > Devices & services > Add integration > Police.uk Local Crime.

Setup methods:

- Auto-detect from Home Assistant home location: finds the Police.uk neighbourhood for naming/routing and stores the HA home latitude/longitude as the query centre.
- Manual force and neighbourhood: stores the selected neighbourhood centre as the query centre.

Area modes:

- Default Police.uk area: uses Police.uk `lat`/`lng` street-crime queries.
- Radius around Home Assistant home location: auto-detect entries only; converts a radius into a 16-point polygon and calls Police.uk with `poly=`.

Radius is configured in metres. Minimum is `50`, default is `250`, and maximum is `5000`. Police.uk does not provide a native radius API, so radius mode is an approximation. Large radii can hit Police.uk API result limits.

Manual entries always use Default Police.uk area for this MVP and cannot switch to radius mode.

The integration fetches only the latest available Police.uk data month. Home Assistant's recorder, history, statistics, and helper integrations should be used for longer-term comparisons and averages.

## Sensors

The integration creates:

| Sensor | State | Key attributes |
| --- | --- | --- |
| Data Month | `YYYY-MM` | `query_area`, `data_month_fallback` |
| Total Crimes | Count for current data month | `by_category`, `latest_incidents`, `incident_count`, `incidents_truncated`, `query_area` |
| Crimes - Category | Count for current data month and category | `incidents`, `incident_count`, `incidents_truncated`, `by_approximate_location`, `query_area`, `month` |

Category sensors are created even when the current category count is zero, so automations can target stable entities.
Category sensors use the same category-specific icons as map pins. Police.uk's
`all-crime` category is represented by the Total Crimes sensor.

| Police.uk category | Display name | Icon |
| --- | --- | --- |
| `all-crime` | All crime | `mdi:police-badge` |
| `anti-social-behaviour` | Anti-social behaviour | `mdi:account-alert-outline` |
| `bicycle-theft` | Bicycle theft | `mdi:bicycle` |
| `burglary` | Burglary | `mdi:home-lock` |
| `criminal-damage-arson` | Criminal damage and arson | `mdi:fire-alert` |
| `drugs` | Drugs | `mdi:pill` |
| `other-theft` | Other theft | `mdi:bag-personal-off` |
| `possession-of-weapons` | Possession of weapons | `mdi:knife` |
| `public-order` | Public order | `mdi:bullhorn-outline` |
| `robbery` | Robbery | `mdi:robber` |
| `shoplifting` | Shoplifting | `mdi:cart-off` |
| `theft-from-the-person` | Theft from the person | `mdi:hand-coin-outline` |
| `vehicle-crime` | Vehicle crime | `mdi:car-key` |
| `violent-crime` | Violence and sexual offences | `mdi:knife` |
| `other-crime` | Other crime | `mdi:police-badge-outline` |

Incident attributes are normalized and capped:

- Total `latest_incidents`: first 100 records.
- Category `incidents`: first 50 records.
- `incident_count` is the full count before truncation.
- `incidents_truncated` shows whether the attribute payload was capped.

Normalized incident fields include `id`, `persistent_id`, `category`, `category_name`, `month`, `approximate_location`, `latitude`, `longitude`, and `outcome` when Police.uk includes an inline `outcome_status`.

Police.uk locations are anonymised and approximate, usually reported as "On or near ..." labels rather than exact addresses.

## Map Pins

The `geo_location` platform is enabled for crime incidents only.

Map modes:

- Grouped by category: default; one stable pin per category, positioned at the category centroid.
- Individual incidents: one pin per returned crime record. Multiple records can share the same anonymised Police.uk location.
- None: disables map pins and removes any existing map pin entities for the entry.

Pins use category names, category-appropriate icons, the active area mode, and query-area metadata where practical. Entity names do not include counts, locations, or record IDs; use attributes such as `count`, `by_approximate_location`, `id`, and `persistent_id` for details.

To show pins in a map card, use the per-entry source:

```yaml
type: map
geo_location_sources:
  - police_uk_local_YOUR_FORCE_YOUR_NEIGHBOURHOOD
```

## Services

| Service | Description |
| --- | --- |
| `police_uk_local.refresh` | Force-refresh all configured areas, or one area when `entry_id` is supplied. |
| `police_uk_local.get_crimes` | Fires `police_uk_local_crimes_data` with up to 200 raw crime records for the selected area. |

## Automation Examples

Trigger when Police.uk publishes a new data month:

```yaml
trigger:
  - platform: state
    entity_id: sensor.YOUR_PREFIX_data_month
action:
  - service: notify.mobile_app_phone
    data:
      title: Police.uk data updated
      message: "New Police.uk data month: {{ states('sensor.YOUR_PREFIX_data_month') }}"
```

Notify when a category has records in the current configured area:

```yaml
trigger:
  - platform: numeric_state
    entity_id: sensor.YOUR_PREFIX_crimes_vehicle_crime
    above: 0
action:
  - service: notify.mobile_app_phone
    data:
      title: Nearby vehicle crime
      message: >
        {{ states('sensor.YOUR_PREFIX_crimes_vehicle_crime') }} vehicle crime reports
        in {{ state_attr('sensor.YOUR_PREFIX_crimes_vehicle_crime', 'month') }}.
        {{ state_attr('sensor.YOUR_PREFIX_crimes_vehicle_crime', 'by_approximate_location') }}
```

## Data Refresh

The coordinator checks `crime-last-updated` once per day. It derives the latest data month from the returned date and fetches that month for the configured area. The older "today minus two months" heuristic is used only if `crime-last-updated` is unavailable.

## License

MIT
