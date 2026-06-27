"""Constants for Police.uk Local Crime integration."""

DOMAIN = "police_uk_local"

# How often (minutes) the coordinator wakes up to check if police data has changed.
# The API only publishes new data roughly every 2 months, so once per day is plenty.
DEFAULT_SCAN_INTERVAL = 1440  # 24 hours

# Police.uk API base URL
API_BASE_URL = "https://data.police.uk/api"

# Config entry keys
CONF_FORCE = "force"
CONF_NEIGHBOURHOOD = "neighbourhood"
CONF_NEIGHBOURHOOD_NAME = "neighbourhood_name"
CONF_FORCE_NAME = "force_name"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_CRIME_MONTHS = "crime_months"
CONF_MAP_MODE = "map_mode"
CONF_SETUP_METHOD = "setup_method"
CONF_AREA_MODE = "area_mode"
CONF_RADIUS_METERS = "radius_meters"

SETUP_METHOD_AUTO = "auto"
SETUP_METHOD_MANUAL = "manual"

# Area mode values
AREA_MODE_DEFAULT = "default"
AREA_MODE_RADIUS = "radius"

# Map mode values
MAP_MODE_GROUPED = "grouped"
MAP_MODE_INDIVIDUAL = "individual"

# Default values
DEFAULT_CRIME_MONTHS = 3
DEFAULT_MAP_MODE = MAP_MODE_GROUPED
DEFAULT_AREA_MODE = AREA_MODE_DEFAULT
DEFAULT_RADIUS_METERS = 250
MIN_RADIUS_METERS = 50
MAX_RADIUS_METERS = 5000
POLYGON_POINTS = 16

# Crime categories (Police.uk API standard categories)
CRIME_CATEGORIES = {
    "all-crime": "All crime",
    "anti-social-behaviour": "Anti-social behaviour",
    "bicycle-theft": "Bicycle theft",
    "burglary": "Burglary",
    "criminal-damage-arson": "Criminal damage and arson",
    "drugs": "Drugs",
    "other-theft": "Other theft",
    "possession-of-weapons": "Possession of weapons",
    "public-order": "Public order",
    "robbery": "Robbery",
    "shoplifting": "Shoplifting",
    "theft-from-the-person": "Theft from the person",
    "vehicle-crime": "Vehicle crime",
    "violent-crime": "Violence and sexual offences",
    "other-crime": "Other crime",
}

DEFAULT_CRIME_CATEGORY_ICON = "mdi:police-badge-outline"
CRIME_CATEGORY_ICONS = {
    "all-crime": "mdi:police-badge",
    "anti-social-behaviour": "mdi:account-alert-outline",
    "bicycle-theft": "mdi:bicycle",
    "burglary": "mdi:home-lock",
    "criminal-damage-arson": "mdi:fire-alert",
    "drugs": "mdi:pill",
    "other-theft": "mdi:bag-personal-off",
    "possession-of-weapons": "mdi:knife",
    "public-order": "mdi:bullhorn-outline",
    "robbery": "mdi:robber",
    "shoplifting": "mdi:cart-off",
    "theft-from-the-person": "mdi:hand-coin-outline",
    "vehicle-crime": "mdi:car-key",
    "violent-crime": "mdi:knife",
    "other-crime": DEFAULT_CRIME_CATEGORY_ICON,
}

# Attribution
ATTRIBUTION = "Data provided by data.police.uk"
