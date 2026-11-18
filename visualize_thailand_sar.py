
from pathlib import Path
import numpy as np
import rasterio
import matplotlib.pyplot as plt

# 1. ค้นหาไฟล์ SAR
folder = Path("data/thailand_external/2021_10_05/sar")
files = sorted(folder.glob("*.tif"))

if not files:
    raise FileNotFoundError(
        "ไม่พบไฟล์ .tif ในโฟลเดอร์ sar"
    )

path = files[0]

# 2. อ่านข้อมูล VV และ VH
with rasterio.open(path) as src:
    print("File:", path.name)
    print("Bands:", src.count)
    print("Shape:", src.height, src.width)
    print("CRS:", src.crs)
    print("Resolution:", src.res)
    print("NoData:", src.nodata)

    if src.count < 2:
        raise ValueError("ต้องมีอย่างน้อย 2 bands: VV, VH")

    vv = src.read(1).astype(np.float32)
    vh = src.read(2).astype(np.float32)
    nodata = src.nodata

# 3. กรอง NoData และค่าที่ไม่ถูกต้อง


def clean_band(arr):
    valid = np.isfinite(arr)

    if nodata is not None:
        valid &= arr != nodata

    valid &= arr != -9999

    print("\nValid pixels:",
          round(100 * valid.mean(), 2), "%")

    if valid.sum() == 0:
        raise ValueError("ไม่พบพิกเซลที่ใช้งานได้")

    values = arr[valid]

    print("Min:", float(values.min()))
    print("Max:", float(values.max()))
    print("Percentiles [2, 50, 98]:",
          np.percentile(values, [2, 50, 98]))

    return np.ma.array(arr, mask=~valid)


vv = clean_band(vv)
vh = clean_band(vh)

# 4. ปรับช่วงสีสำหรับการแสดงผลเท่านั้น
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

axes[0].imshow(
    vv, cmap="gray",
    vmin=-25, vmax=0
)
axes[0].set_title("Sentinel-1 VV (Sigma0 dB)")
axes[0].axis("off")

axes[1].imshow(
    vh, cmap="gray",
    vmin=-32, vmax=-5
)
axes[1].set_title("Sentinel-1 VH (Sigma0 dB)")
axes[1].axis("off")

plt.tight_layout()

# 5. บันทึกภาพผลลัพธ์
output = Path(
    "results/figures/thailand_sar_preview.png"
)
output.parent.mkdir(parents=True, exist_ok=True)

plt.savefig(output, dpi=180)
plt.show()

print("\nSaved:", output)
