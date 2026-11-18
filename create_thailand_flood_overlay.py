
from pathlib import Path
import json
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_geom
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

base = Path("data/thailand_external/2021_10_05")
sar_files = sorted((base / "sar").glob("*.tif"))

if not sar_files:
    raise FileNotFoundError("ไม่พบ SAR GeoTIFF")

# 1. อ่านภาพ SAR
with rasterio.open(sar_files[0]) as src:
    if src.count < 2:
        raise ValueError("SAR ต้องมี VV และ VH")

    vv = src.read(1)
    vh = src.read(2)
    profile = src.profile.copy()

    valid_sar = (
        (src.read_masks(1) > 0)
        & (src.read_masks(2) > 0)
        & np.isfinite(vv)
        & np.isfinite(vh)
        & (vv != -9999)
        & (vh != -9999)
    )

    # 2. อ่าน UNOSAT GeoJSON
    with open(base / "flood_extent.geojson") as f:
        geojson = json.load(f)

    def rasterize_kind(kind):
        geometries = []

        for feature in geojson["features"]:
            if feature["properties"].get("kind") != kind:
                continue

            geom = transform_geom(
                "EPSG:4326",
                src.crs.to_string(),
                feature["geometry"]
            )
            geometries.append((geom, 1))

        return rasterize(
            geometries,
            out_shape=(src.height, src.width),
            transform=src.transform,
            fill=0,
            dtype="uint8"
        ).astype(bool)

    flood = rasterize_kind("flood")
    analysed = rasterize_kind("analysed_extent")

# 3. สร้าง Reference และ Validity Masks
valid = analysed & valid_sar
reference_flood = flood & valid

# 255 = Ignore, 0 = No detected flood, 1 = Flood
reference = np.full(vv.shape, 255, dtype=np.uint8)
reference[valid] = 0
reference[reference_flood] = 1

print("Image shape:", vv.shape)
print("Valid pixels:", int(valid.sum()))
print("Flood pixels:", int(reference_flood.sum()))

if valid.any():
    print(
        "Flood fraction:",
        round(100 * reference_flood.sum() / valid.sum(), 2),
        "%"
    )

# 4. สร้างภาพ
fig, axes = plt.subplots(1, 3, figsize=(18, 6))

sar_display = np.ma.masked_where(~valid_sar, vv)

axes[0].imshow(
    sar_display, cmap="gray", vmin=-25, vmax=0
)
axes[0].set_title("Sentinel-1 VV (Sigma0 dB)")

cmap = ListedColormap(["#aaaaaa", "#168bda"])
cmap.set_bad("white")

mask_display = np.ma.masked_where(
    reference == 255, reference
)

axes[1].imshow(
    mask_display,
    cmap=cmap, vmin=-0.5, vmax=1.5
)
axes[1].set_title("UNOSAT Flood Reference")

axes[2].imshow(
    sar_display, cmap="gray", vmin=-25, vmax=0
)
overlay = np.ma.masked_where(
    ~reference_flood,
    np.ones_like(vv, dtype=np.float32)
)

axes[2].imshow(
    overlay, cmap="autumn",
    vmin=0, vmax=1, alpha=0.55
)
axes[2].set_title("SAR + Flood Overlay")

for ax in axes:
    ax.axis("off")

plt.tight_layout()

out = Path(
    "results/figures/thailand_flood_overlay.png"
)
out.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out, dpi=180)
plt.show()

print("Saved:", out)


# 5. Save reference mask and validity mask
mask_dir = base / "masks"
mask_dir.mkdir(parents=True, exist_ok=True)

# Reference classes:
# 0 = No detected flood
# 1 = Detected flood
# 255 = Ignore / NoData

reference_profile = profile.copy()
reference_profile.update(
    driver="GTiff",
    count=1,
    dtype="uint8",
    nodata=255,
    compress="lzw"
)

reference_path = mask_dir / "thailand_flood_reference.tif"

with rasterio.open(reference_path, "w", **reference_profile) as dst:
    dst.write(reference, 1)

# Save validity mask separately
# 1 = valid for evaluation
# 0 = ignore

valid_profile = profile.copy()
valid_profile.update(
    driver="GTiff",
    count=1,
    dtype="uint8",
    nodata=None,
    compress="lzw"
)

valid_path = mask_dir / "thailand_valid_mask.tif"

with rasterio.open(valid_path, "w", **valid_profile) as dst:
    dst.write(valid.astype(np.uint8), 1)

# 6. Summary
n_flood = int((reference == 1).sum())
n_non_flood = int((reference == 0).sum())
n_ignore = int((reference == 255).sum())

n_valid = n_flood + n_non_flood

print("\n=== THAILAND DATASET SUMMARY ===")
print("Flood pixels:", n_flood)
print("Non-flood pixels:", n_non_flood)
print("Ignore pixels:", n_ignore)

if n_valid > 0:
    print(
        "Flood fraction:",
        round(100 * n_flood / n_valid, 3),
        "%"
    )

print("Reference saved:", reference_path)
print("Validity saved:", valid_path)
