# Signal City v3.0 — Civic Datasets Provenance

This directory stores the real-world Bengaluru datasets used by the **Applied Impact Console** for decision support. All datasets are loaded locally for offline reliability.

---

## 1. BBMP Ward Boundaries (GeoJSON)
- **Source**: [DataMeet Municipal Spatial Data](https://github.com/datameet/Municipal_Spatial_Data)
- **File**: `Bangalore/BBMP.geojson` (or `bbmp_wards.geojson`)
- **License**: Creative Commons Attribution 2.5 India (CC BY 2.5 IN)
- **Description**: Geospatial boundaries of Bruhat Bengaluru Mahanagara Palike (BBMP) administrative wards. Used for spatial overlays and ward population density calculations.

## 2. BMTC Bus Network (GTFS Stops & Routes)
- **Source**: [Vonter BMTC GTFS Repository](https://github.com/Vonter/bmtc-gtfs)
- **Files**: `stops.txt`, `routes.txt`
- **Description**: Contains positions of bus stops and route mappings for the Bangalore Metropolitan Transport Corporation (BMTC). Used for transit desert analysis.

## 3. Bengaluru Road Crash / Blackspot Data
- **Source**: Compiled from Bengaluru Traffic Police (BTP) road safety reports via [OpenCity.in](https://data.opencity.in)
- **File**: `crash_data.csv`
- **Description**: Locations, severity, and timestamps of road traffic accidents and blackspots in Bengaluru. Used for emergency vehicle routing risks.

## 4. Civic Facilities POIs (Hospitals, Fire Stations, EV Chargers)
- **Source**: OpenStreetMap (OSM) via `osmnx` features API.
- **Query**: `ox.features_from_place("Bengaluru, India", tags={"amenity": ["hospital", "fire_station", "charging_station"]})`
- **Description**: Coordinates of active hospitals, fire services, and EV infrastructure. Used for optimal facility siting analysis.
