
from pathlib import Path
import numpy as np
import rasterio
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

base = Path("data/thailand_external/2021_10_05")
results = Path("results/sar_unet_baseline_v1/thailand_pilot")

reference_path = base / "masks/thailand_flood_reference.tif"
valid_path = base / "masks/thailand_valid_mask.tif"
prediction_path = results / "thailand_predicted_water_mask.tif"


def read_raster(path):
    if not path.exists():
        raise FileNotFoundError(path)
    with rasterio.open(path) as src:
        return src.read(1), src.profile.copy(), src.read_masks(1) > 0


ref, ref_profile, ref_data_valid = read_raster(reference_path)
valid_mask, valid_profile, _ = read_raster(valid_path)
pred, pred_profile, pred_data_valid = read_raster(prediction_path)

# Verify alignment
for p in [valid_profile, pred_profile]:
    assert ref.shape == (
        p["height"], p["width"]
    ), "Image shapes do not match"
    assert ref_profile["crs"] == p["crs"], "CRS mismatch"
    assert ref_profile["transform"].almost_equals(
        p["transform"]
    ), "Pixel grids are not aligned"

# Valid comparison area
valid = (
    (valid_mask == 1)
    & ref_data_valid
    & pred_data_valid
    & np.isin(ref, [0, 1])
    & np.isin(pred, [0, 1])
)

flood = ref == 1
water = pred == 1

both = valid & flood & water
missed = valid & flood & ~water
extra = valid & ~flood & water
neither = valid & ~flood & ~water

# 0 neither, 1 agreement, 2 missed, 3 extra, 4 ignore
difference = np.full(ref.shape, 4, dtype=np.uint8)
difference[neither] = 0
difference[both] = 1
difference[missed] = 2
difference[extra] = 3

print("\n=== THAILAND COMPARISON ===")
print("Both detect water/flood:", int(both.sum()))
print("UNOSAT flood missed by model:", int(missed.sum()))
print("Model water outside UNOSAT flood:", int(extra.sum()))
print("Neither:", int(neither.sum()))
print("Ignored:", int((~valid).sum()))

print(
    "UNOSAT reference detection rate:",
    round(100 * both.sum() / max(1, flood[valid].sum()), 2),
    "%"
)

# Visualization
colors = [
    "#cbd5e1",
    "#16a34a",
    "#ef4444",
    "#eab308",
    "#ffffff"
]

cmap = ListedColormap(colors)

fig, ax = plt.subplots(figsize=(12, 9))
ax.imshow(difference, cmap=cmap, vmin=-0.5, vmax=4.5)
ax.set_title("Thailand: Model vs UNOSAT Disagreement Map")
ax.axis("off")

labels = [
    "Neither",
    "UNOSAT flood + model water",
    "UNOSAT flood missed",
    "Model water outside UNOSAT",
    "Ignore"
]

handles = [
    Patch(facecolor=c, label=l)
    for c, l in zip(colors, labels)
]

ax.legend(
    handles=handles,
    loc="lower center",
    bbox_to_anchor=(0.5, -0.12),
    ncol=2
)

plt.tight_layout()

output = results / "thailand_disagreement_map.png"
plt.savefig(output, dpi=180, bbox_inches="tight")
plt.show()

print("Saved:", output)
