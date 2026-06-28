"""`video-start` / `video-stop` — record the device screen to an mp4.

Appium records server-side; `stop_recording_screen` returns the video as base64,
which we decode and write to disk. The recording options diverge per platform
(iOS supports videoQuality), so they come from the strategy layer.
"""

from __future__ import annotations

import argparse
import base64
import time

from appium_pilot import config
from appium_pilot.output import CommandError, emit
from appium_pilot.session import Session


def add_parser(sub: argparse._SubParsersAction) -> None:
    s = sub.add_parser("video-start", help="start recording the device screen")
    s.add_argument("--time-limit", type=int, default=1800,
                   help="max recording length in seconds (default 1800; Android caps at 1800)")
    s.add_argument("--quality", choices=["low", "medium", "high"], default="medium",
                   help="video quality (iOS only; ignored on Android)")
    s.set_defaults(func=run_start)

    e = sub.add_parser("video-stop", help="stop recording and save the mp4")
    e.add_argument("-o", "--out", help="output path (default: session videos dir)")
    e.set_defaults(func=run_stop)


def run_start(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    if session.recording:
        emit("recording already in progress", recording=True)
        return
    options = session.strategy.recording_options(args.time_limit, args.quality)
    driver.start_recording_screen(**options)
    session.recording = True
    session.save()
    emit("recording started", recording=True)


def run_stop(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    data_b64 = driver.stop_recording_screen()
    if not data_b64:
        raise CommandError("no recording data returned (was `video-start` run?)", code=2)

    if args.out:
        path = args.out
    else:
        videos = config.videos_dir()
        videos.mkdir(parents=True, exist_ok=True)
        path = str(videos / f"rec-{time.strftime('%Y%m%d-%H%M%S')}.mp4")

    with open(path, "wb") as fh:
        fh.write(base64.b64decode(data_b64))
    session.recording = False
    session.save()
    emit(path, path=path)
