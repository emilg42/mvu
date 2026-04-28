#!/usr/bin/env python3
import re
import readline
import subprocess
import sys
from pathlib import Path

from prompt_toolkit import prompt
from prompt_toolkit.application.current import get_app
from prompt_toolkit.formatted_text import HTML

GREEN = "\033[32m"
RESET = "\033[0m"
BANNER = r"""
   ____ ___ _   ____  __
  / __ `__ \ | / / / / /
 / / / / / / |/ / /_/ /
/_/ /_/ /_/|___/\__,_/
 ~ emilg's metavision_utility
"""

script_dir = Path(__file__).resolve().parent
input_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data.raw")

proc = subprocess.run(
    ["metavision_file_info", "-i", str(input_file)],
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)

m = re.search(r"Duration\s+(.+)", proc.stdout)
if not m:
    raise SystemExit("Could not find Duration line.")

duration_text = m.group(1).strip()

parts = {}
for n, u in re.findall(r"(\d+)(h|ms|us|m|s)", duration_text):
    parts[u] = int(n)

total = (
    parts.get("h", 0) * 3600
    + parts.get("m", 0) * 60
    + parts.get("s", 0)
    + parts.get("ms", 0) / 1000
    + parts.get("us", 0) / 1_000_000
)

lines = proc.stdout.splitlines()

print(BANNER)
for line in lines[2:]:
    if line.strip().startswith("Duration"):
        print(f"{GREEN}{line} ({total:.6f}s){RESET}")
    else:
        print(line)

display_fps = 30

def edit_and_run(cmd):
    text = prompt("> ", default=" ".join(map(str, cmd)))
    if text.strip():
        subprocess.run(text, shell=True, check=True)

def bottom_toolbar():
    text = get_app().current_buffer.text.strip()

    try:
        s = float(text) if text else 1.0
        generation_fps = s * display_fps
        accumulation_us = round(1_000_000 / generation_fps)
        preview_length = total * s


        return HTML(
            f" gen. FPS: <b>{generation_fps:g}</b> | "
            f"accumulation: <b>{accumulation_us}μs</b> | "
            f"gen. length: <b>{preview_length:.3f}s</b>"
        )
    except ValueError:
        return HTML(" enter a number, e.g. 1, 15, 50 ")

slow_motion_text = prompt(
    "\npreview slow-motion factor (default 1): ",
    bottom_toolbar=bottom_toolbar,
)

slow_motion = float(slow_motion_text.strip() or "1")

generation_fps = slow_motion * display_fps
accumulation_us = round(1_000_000 / generation_fps)

preview_file = Path("__preview.avi")

print(f"\npreview FPS: {generation_fps:g}")
print(f"accumulation: {accumulation_us}μs")

cmd = [
    "metavision_file_to_video",
    "-i", str(input_file),
    "-o", str(preview_file),
    "-s", str(slow_motion),
    "-a", str(accumulation_us),
]

print()
print(" ".join(cmd))

# run on preview file
try:
    subprocess.run(cmd, check=True)

    timestamps_file = Path("__timestamps.txt")
    if timestamps_file.exists():
        timestamps_file.unlink()

    # open in mpv
    subprocess.run([
        "mpv",
        str(preview_file),
        "--autofit=75%",
        "--script=" + str(script_dir / "event_osd.lua"),
        f"--script-opts=slow_motion={slow_motion:g},outfile={timestamps_file}",
    ], check=True)

    # bundle clip(s)
    clips = []

    if timestamps_file.exists():
        lines = timestamps_file.read_text().splitlines()
        timestamps_file.unlink()

        starts = [float(line.split()[-1]) for line in lines if line.startswith("START")]
        stops = [float(line.split()[-1]) for line in lines if line.startswith("STOP")]

        clips = [
            {"start": start, "end": end, "duration": end - start}
            for start, end in zip(starts, stops)
        ]

    print()
    if not clips:
        clips = [{
            "start": 0.0,
            "end": total,
            "duration": total,
            "whole_file": True,
        }]

    for i, clip in enumerate(clips, start=1):
        print(f"╭──────────[ {'FULL-F' if clip.get('whole_file') else f'CLIP {i}'} ]──────────╮")
        print(f"│ start:    {clip['start']:10.6f}s        │")
        print(f"│ end:      {clip['end']:10.6f}s        │")
        print(f"│ duration: {clip['duration']:10.6f}s        │")
        print(f"╰──────────────────────────────╯")


        # preview clip
        # if not clip.get("whole_file"):
        #     subprocess.run([
        #         "mpv",
        #         str(preview_file),
        #         "--autofit=30%",
        #         f"--start={clip['start'] * slow_motion:.6f}",
        #         f"--ab-loop-a={clip['start'] * slow_motion:.6f}",
        #         f"--ab-loop-b={clip['end'] * slow_motion:.6f}",
        #     ], check=True)

        default_stem = (
            f"{input_file.stem}_export"
            if clip.get("whole_file")
            else f"{input_file.stem}_clip{i:02d}"
        )

        name_text = prompt(f"name ({default_stem}): ").strip()
        base = input_file.with_name(name_text or default_stem)

        # select export
        export_options = ["avi", "raw", "hdf5", "dat", "csv", "discard"]

        fzf = subprocess.run(
            [
                "fzf",
                "--prompt=export > ",
                "--height=40%",
                "--reverse",
            ],
            input="\n".join(export_options),
            text=True,
            stdout=subprocess.PIPE,
        )

        export_mode = "" if fzf.returncode != 0 else fzf.stdout.strip()

        if export_mode in {"", "discard"}:
            print("clip discarded...")
            continue

        # cut
        if clip.get("whole_file"):
            out_file = input_file
        else:
            out_file = base.with_suffix(input_file.suffix)

            subprocess.run([
                "metavision_file_cutter",
                "-i", str(input_file),
                "-o", str(out_file),
                "-s", f"{clip['start']:.6f}",
                "-e", f"{clip['end']:.6f}",
            ], check=True)

        # export
        match export_mode:
            case "raw":
                final_file = out_file

            case "avi":
                avi_s_text = prompt(f"slow-motion factor ({slow_motion}): ")
                avi_s = float(avi_s_text.strip() or slow_motion)

                auto_a = round(1_000_000 / (avi_s * display_fps))
                avi_a_text = prompt(f"accumulation (no temporal overlap ≙ {auto_a}μs): ")
                avi_a = int(avi_a_text.strip() or auto_a)

                final_file = base.with_suffix(".avi")
                edit_and_run([
                    "metavision_file_to_video",
                    "-i", out_file,
                    "-o", final_file,
                    "-s", avi_s,
                    "-a", avi_a,
                ])

            case "hdf5":
                final_file = base.with_suffix(".hdf5")
                edit_and_run([
                    "metavision_file_to_hdf5",
                    "-i", out_file,
                    "-o", final_file,
                ])

            case "dat":
                final_file = base.with_suffix(".dat")
                edit_and_run([
                    "metavision_file_to_dat",
                    "-i", out_file,
                ])

            case "csv":
                final_file = base.with_suffix(".csv")
                edit_and_run([
                    "metavision_file_to_csv",
                    "-i", out_file,
                    "-o", final_file,
                ])

            case _:
                raise SystemExit(f"unknown export mode: {export_mode}")


        # print size & success
        size = final_file.stat().st_size
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                break
            size /= 1024

        print(f"File saved as {final_file} [{size:.1f}{unit}]")

finally:
    if preview_file.exists():
        preview_file.unlink()

    for tmp_index in input_file.parent.glob("*.raw.tmp_index"):
        tmp_index.unlink()