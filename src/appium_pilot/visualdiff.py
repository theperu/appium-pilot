"""Pixel-ratio image comparison for `expect --baseline`.

Isolated here so Pillow stays an *optional* dependency: nothing imports this at
module load; expect_cmd imports it lazily and turns an ImportError into a clean
"install appium-pilot[visual]" message.

The metric mirrors pixelmatch without the dependency: a pixel "differs" only if
its largest per-channel delta exceeds `pixel_threshold` (a noise floor that
absorbs sub-pixel/anti-aliasing jitter), and the score is the fraction of such
pixels. Structured so a perceptual metric (SSIM, …) could replace `compare`
behind the same shape later.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageChops


class SizeMismatch(Exception):
    """Baseline and current differ in dimensions — not comparable (goldens are
    device/orientation/scale specific; we never resize to force a match)."""

    def __init__(self, baseline: tuple[int, int], current: tuple[int, int]):
        self.baseline = baseline
        self.current = current
        super().__init__(
            f"size mismatch: baseline {baseline[0]}x{baseline[1]} vs "
            f"current {current[0]}x{current[1]}"
        )


@dataclass
class DiffResult:
    ratio: float                          # differing / total, in [0, 1]
    differing: int
    total: int
    width: int
    height: int
    region: tuple[int, int, int, int] | None  # (left, top, right, bottom) of changed area, or None
    mask: "Image.Image"                   # 1-bit-ish L mask (255 where changed), for rendering


def open_image(source) -> Image.Image:  # noqa: ANN001 — bytes | str | Path
    """Load PNG bytes or a file path into an RGB image (alpha flattened away)."""
    data = BytesIO(source) if isinstance(source, (bytes, bytearray)) else source
    return Image.open(data).convert("RGB")


def compare(baseline: Image.Image, current: Image.Image, pixel_threshold: int) -> DiffResult:
    """Diff two same-size RGB images. Raises SizeMismatch if dimensions differ."""
    if baseline.size != current.size:
        raise SizeMismatch(baseline.size, current.size)

    delta = ImageChops.difference(baseline, current)
    r, g, b = delta.split()
    # Per-pixel MAX channel delta — a hue shift at constant luminance still counts
    # (a plain grayscale of the difference would wash that out).
    magnitude = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mask = magnitude.point(lambda p: 255 if p > pixel_threshold else 0)

    differing = mask.histogram()[255]
    total = baseline.width * baseline.height
    return DiffResult(
        ratio=differing / total if total else 0.0,
        differing=differing,
        total=total,
        width=baseline.width,
        height=baseline.height,
        region=mask.getbbox(),
        mask=mask,
    )


def write_diff(baseline: Image.Image, result: DiffResult, path) -> None:  # noqa: ANN001
    """Render a review image: the baseline dimmed, changed pixels flagged magenta."""
    dimmed = Image.blend(baseline, Image.new("RGB", baseline.size, (255, 255, 255)), 0.6)
    flag = Image.new("RGB", baseline.size, (255, 0, 255))
    out = Image.composite(flag, dimmed, result.mask)  # mask=255 → flag, else dimmed base
    out.save(path)
