"""Constants for UK Police integration."""

DOMAIN = "uk_police"

# How often (minutes) the coordinator wakes up to check if police data has changed.
# The API only publishes new data roughly every 2 months, so once per day is plenty.
DEFAULT_SCAN_INTERVAL = 1440  # 24 hours

# UK Police API base URL
API_BASE_URL = "https://data.police.uk/api"

# Config entry keys
CONF_FORCE = "force"
CONF_NEIGHBOURHOOD = "neighbourhood"
CONF_NEIGHBOURHOOD_NAME = "neighbourhood_name"
CONF_FORCE_NAME = "force_name"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_INCLUDE_STOP_SEARCH = "include_stop_search"
CONF_CRIME_MONTHS = "crime_months"
CONF_MAP_MODE = "map_mode"

# Map mode values
MAP_MODE_GROUPED = "grouped"
MAP_MODE_INDIVIDUAL = "individual"

# Default values
DEFAULT_INCLUDE_STOP_SEARCH = True
DEFAULT_CRIME_MONTHS = 3
DEFAULT_MAP_MODE = MAP_MODE_GROUPED

# Crime categories (UK Police API standard categories)
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

# Attribution
ATTRIBUTION = "Data provided by data.police.uk"
