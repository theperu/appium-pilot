"""Pixel-ratio comparison engine for `expect --baseline` (§1.3).

Synthetic PIL images keep this deterministic and device-free. Skips cleanly when
the optional [visual] extra (Pillow) isn't installed.
"""

from io import BytesIO

import pytest

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from appium_pilot.visualdiff import SizeMismatch, compare, open_image, write_diff  # noqa: E402


def _img(color, size=(20, 20)):
    return Image.new("RGB", size, color)


def test_identical_images_score_zero():
    r = compare(_img((10, 20, 30)), _img((10, 20, 30)), 0)
    assert r.ratio == 0.0 and r.differing == 0 and r.region is None


def test_changed_block_counts_pixels_and_region():
    a = _img((0, 0, 0))
    b = _img((0, 0, 0))
    for x in range(2, 7):        # 5 px wide
        for y in range(3, 7):    # 4 px tall
            b.putpixel((x, y), (255, 255, 255))
    r = compare(a, b, 16)
    assert r.differing == 20 and r.total == 400 and r.ratio == 20 / 400
    assert r.region == (2, 3, 7, 7)  # getbbox: right/bottom exclusive


def test_pixel_threshold_is_a_noise_floor():
    a = _img((100, 100, 100))
    b = _img((108, 100, 100))  # max per-channel delta = 8
    assert compare(a, b, 16).differing == 0    # 8 <= 16 → ignored
    assert compare(a, b, 4).differing == 400   # 8 > 4  → every pixel differs


def test_size_mismatch_raises():
    with pytest.raises(SizeMismatch) as exc:
        compare(_img((0, 0, 0), (20, 20)), _img((0, 0, 0), (21, 20)), 0)
    assert exc.value.baseline == (20, 20) and exc.value.current == (21, 20)


def test_open_from_bytes_and_write_diff(tmp_path):
    buf = BytesIO()
    _img((0, 0, 0)).save(buf, "PNG")
    base = open_image(buf.getvalue())  # bytes path
    assert base.size == (20, 20) and base.mode == "RGB"

    changed = _img((0, 0, 0))
    changed.putpixel((1, 1), (255, 255, 255))
    result = compare(base, changed, 0)
    out = tmp_path / "d.png"
    write_diff(base, result, out)
    assert out.exists() and out.stat().st_size > 0
