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
    "all-crime": "All Crime",
    "anti-social-behaviour": "Anti-social Behaviour",
    "bicycle-theft": "Bicycle Theft",
    "burglary": "Burglary",
    "criminal-damage-arson": "Criminal Damage & Arson",
    "drugs": "Drugs",
    "other-theft": "Other Theft",
    "possession-of-weapons": "Possession of Weapons",
    "public-order": "Public Order",
    "robbery": "Robbery",
    "shoplifting": "Shoplifting",
    "theft-from-the-person": "Theft from Person",
    "vehicle-crime": "Vehicle Crime",
    "violent-crime": "Violent Crime",
    "other-crime": "Other Crime",
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
