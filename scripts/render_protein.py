"""Render a slowly rotating PDB structure as a glowing green GIF for the profile hero.

Runs headless with open-source PyMOL. The structure is downloaded from RCSB,
so the animation shows a real experimental model, not a procedural drawing.
"""
import os
import pathlib
import tempfile

import pymol
from pymol import cmd
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "hero-protein.gif"

PDB_ID = os.environ.get("PDB_ID", "4ZQK")  # PD-1 / PD-L1 complex
FRAMES = 60
SIZE = 440
GREEN = (0.224, 1.0, 0.533)   # #39FF88
TEAL = (0.18, 0.77, 0.71)     # #2EC4B6


def main():
    pymol.finish_launching(["pymol", "-qc"])
    cmd.reinitialize()
    cmd.bg_color("black")
    cmd.fetch(PDB_ID, async_=0)

    cmd.set_color("bio_green", GREEN)
    cmd.set_color("bio_teal", TEAL)

    cmd.hide("everything")
    cmd.remove("solvent")
    cmd.show("cartoon", "polymer")
    cmd.show("surface", "polymer")
    cmd.color("bio_green", "polymer")
    cmd.color("bio_teal", "polymer and chain B")
    cmd.set("cartoon_color", "bio_green", "polymer")
    cmd.set("cartoon_color", "bio_teal", "polymer and chain B")

    cmd.set("transparency", 0.7)
    cmd.set("cartoon_fancy_helices", 1)
    cmd.set("ray_trace_fog", 0)
    cmd.set("depth_cue", 1)
    cmd.set("specular", 0.4)
    cmd.set("ambient", 0.35)

    cmd.orient("polymer")
    cmd.zoom("polymer", buffer=8)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for i in range(FRAMES):
            cmd.turn("y", 360 / FRAMES)
            path = f"{tmp}/frame_{i:03d}.png"
            cmd.png(path, width=SIZE, height=SIZE, ray=1, quiet=1)
            paths.append(path)

        frames = [Image.open(p).convert("P", palette=Image.ADAPTIVE) for p in paths]
        frames[0].save(
            OUT,
            save_all=True,
            append_images=frames[1:],
            duration=60,
            loop=0,
            optimize=True,
        )

    cmd.quit()
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
