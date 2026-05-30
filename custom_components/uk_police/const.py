"""Constants for UK Police integration."""

DOMAIN = "uk_police"
PLATFORMS = ["sensor", "binary_sensor", "geo_location"]

# Update interval in minutes
DEFAULT_SCAN_INTERVAL = 60

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

# Outcome categories
OUTCOME_CATEGORIES = {
    "under-investigation": "Under Investigation",
    "awaiting-court-outcome": "Awaiting Court Outcome",
    "unable-to-prosecute": "Unable to Prosecute",
    "local-resolution": "Local Resolution",
    "no-further-action": "No Further Action",
    "defendant-sent-to-crown-court": "Sent to Crown Court",
    "offender-given-suspended-prison-sentence": "Suspended Sentence",
    "offender-fined": "Offender Fined",
    "offender-given-community-sentence": "Community Sentence",
    "offender-deprived-of-property": "Deprived of Property",
    "offender-given-conditional-discharge": "Conditional Discharge",
    "offender-given-absolute-discharge": "Absolute Discharge",
    "offender-given-penalty-notice": "Penalty Notice",
    "offender-sent-to-prison": "Sent to Prison",
    "offender-otherwise-dealt-with": "Otherwise Dealt With",
    "formal-action-is-not-in-the-public-interest": "Not in Public Interest",
    "court-result-unavailable": "Court Result Unavailable",
    "offender-cautioned": "Offender Cautioned",
    "status-update-unavailable": "Status Update Unavailable",
}

# Stop & search object types
STOP_SEARCH_OBJECT_TYPES = {
    "articles_for_use_in_connection_with": "Articles for Use in Connection With",
    "controlled_drugs": "Controlled Drugs",
    "firearms": "Firearms",
    "going_equipped_for_stealing": "Going Equipped for Stealing",
    "offensive_weapons": "Offensive Weapons",
    "stolen_articles": "Stolen Articles",
    "evidence_of_offences_under_s1_customs": "Customs Offences Evidence",
    "items_which_may_damage_or_destroy_property": "Items to Damage/Destroy Property",
    "evidence_of_wildlife_offences": "Wildlife Offence Evidence",
    "evidence_of_game_or_poaching_offences": "Poaching Offence Evidence",
    "anything_to_threaten_or_harm_anyone": "Items to Threaten/Harm",
}

# Attribution
ATTRIBUTION = "Data provided by data.police.uk"
