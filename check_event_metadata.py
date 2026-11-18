
import json
from pathlib import Path

path = Path(
    "data/sen1floods11/metadata/Sen1Floods11_Metadata.geojson"
)

with open(path) as f:
    metadata = json.load(f)

print("Number of events:", len(metadata["features"]))

for feature in metadata["features"]:
    p = feature["properties"]

    print(
        p["location"],
        "| Date:", p["s1_date"],
        "| Orbit:", p["orbit"],
        "| Relative orbit:", p["rel_orbit_num"]
    )
