"""Indian cities tracked by the pipeline (name, latitude, longitude). Add or remove cities freely."""

CITIES: list[tuple[str, float, float]] = [
    ("Delhi", 28.6139, 77.2090),
    ("Mumbai", 19.0760, 72.8777),
    ("Bengaluru", 12.9716, 77.5946),
    ("Kolkata", 22.5726, 88.3639),
    ("Chennai", 13.0827, 80.2707),
    ("Hyderabad", 17.3850, 78.4867),
    ("Pune", 18.5204, 73.8567),
    ("Ahmedabad", 23.0225, 72.5714),
    ("Jaipur", 26.9124, 75.7873),
    ("Lucknow", 26.8467, 80.9462),
    ("Kanpur", 26.4499, 80.3319),
    ("Patna", 25.5941, 85.1376),
    ("Chandigarh", 30.7333, 76.7794),
    ("Bhopal", 23.2599, 77.4126),
    ("Nagpur", 21.1458, 79.0882),
    ("Visakhapatnam", 17.6868, 83.2185),
    ("Vijayawada", 16.5062, 80.6480),
    ("Kochi", 9.9312, 76.2673),
    ("Guwahati", 26.1445, 91.7362),
    ("Varanasi", 25.3176, 82.9739),
]

CITY_COORDS = {name: (lat, lon) for name, lat, lon in CITIES}
