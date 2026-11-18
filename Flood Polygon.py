
import json
from shapely.geometry import shape, box
from shapely.ops import unary_union, transform
from pyproj import Transformer

path = "data/thailand_external/2021_10_05/flood_extent.geojson"

with open(path) as f:
    data = json.load(f)

# พื้นที่พิมายที่เลือกใน Google Earth Engine
roi = box(102.43, 15.17, 102.56, 15.26)

# แยก flood และ analysed_extent
flood = unary_union([
    shape(f["geometry"])
    for f in data["features"]
    if f["properties"].get("kind") == "flood"
])

analysed = unary_union([
    shape(f["geometry"])
    for f in data["features"]
    if f["properties"].get("kind") == "analysed_extent"
])

# หาพื้นที่ซ้อนทับที่อยู่ภายในขอบเขตวิเคราะห์
valid_area = roi.intersection(analysed)
flood_area = valid_area.intersection(flood)

# แปลง WGS84 -> UTM Zone 48N สำหรับคำนวณพื้นที่
project = Transformer.from_crs(
    "EPSG:4326", "EPSG:32648", always_xy=True
).transform


def area_km2(geom):
    return transform(project, geom).area / 1e6


valid_km2 = area_km2(valid_area)
flood_km2 = area_km2(flood_area)

print("Analysed area (km²):", round(valid_km2, 3))
print("Flood area (km²):", round(flood_km2, 3))

if valid_km2 > 0:
    print("Flood fraction (%):",
          round(100 * flood_km2 / valid_km2, 2))

if flood_km2 > 0:
    print("PASS: Flood polygons exist inside the AOI")
else:
    print("WARNING: No measurable flood area inside AOI")
