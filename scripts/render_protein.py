"""Render the PD-L1 dimerization story as a GIF for the profile hero.

Scene 1: the apo PD-L1 monomer (5C3T) morphs into the inhibitor-bound monomer
         (5J89, chain A). This is an interpolation between two experimental
         structures, not a simulated trajectory, and the caption says so.
         The small-molecule inhibitor fades in at the end.
Scene 2: the inhibitor-bound dimer (5J89, chains A and B) rotates.

Structures come from RCSB. Rendering is headless open-source PyMOL.
"""
import math
import pathlib
import tempfile
import urllib.request

import numpy as np
import pymol
from PIL import Image, ImageDraw, ImageFont
from pymol import cmd

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "hero-protein.gif"

APO_ID = "5C3T"    # PD-L1 IgV domain, no ligand
HOLO_ID = "5J89"   # PD-L1 with low-molecular-mass inhibitor, dimer in the assembly
MORPH_FRAMES = 36
DIMER_FRAMES = 36
SIZE = 400
LIGAND_FROM = MORPH_FRAMES - 12  # frame index where the inhibitor appears
GREEN = (0.224, 1.0, 0.533)   # #39FF88
TEAL = (0.18, 0.77, 0.71)     # #2EC4B6


def download(pdb_id, dest):
    urllib.request.urlretrieve(f"https://files.rcsb.org/download/{pdb_id}.pdb", dest)


def read_chain(path, chain):
    """Return {(resi, atom_name): (pdb_line, xyz)} for one chain's ATOM records."""
    atoms = {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("ATOM") and line[21] == chain and line[16] in " A":
                key = (int(line[22:26]), line[12:16])
                xyz = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
                atoms[key] = (line.rstrip("\n"), xyz)
    return atoms


def kabsch(moving, fixed):
    """Return a function that superposes `moving` onto `fixed` (both Nx3 arrays)."""
    mc, fc = moving.mean(0), fixed.mean(0)
    u, _, vt = np.linalg.svd((moving - mc).T @ (fixed - fc))
    d = np.sign(np.linalg.det(vt.T @ u.T))
    rot = vt.T @ np.diag([1, 1, d]) @ u.T
    return lambda x: (x - mc) @ rot.T + fc


def write_morph(apo, holo, path, n_frames):
    """Write a multi-model PDB: apo (aligned to holo) interpolated to holo over n_frames."""
    keys = [k for k in apo if k in holo]
    ca = [k for k in keys if k[1].strip() == "CA"]
    align = kabsch(np.array([apo[k][1] for k in ca]), np.array([holo[k][1] for k in ca]))
    start = align(np.array([apo[k][1] for k in keys]))
    end = np.array([holo[k][1] for k in keys])
    with open(path, "w") as fh:
        for i in range(n_frames):
            # Ease in and out so the motion starts and ends gently.
            t = (1 - math.cos(math.pi * i / (n_frames - 1))) / 2
            xyz = (1 - t) * start + t * end
            fh.write(f"MODEL     {i + 1:4d}\n")
            for k, p in zip(keys, xyz):
                line = apo[k][0]
                fh.write(line[:30] + f"{p[0]:8.3f}{p[1]:8.3f}{p[2]:8.3f}" + line[54:] + "\n")
            fh.write("ENDMDL\n")
        fh.write("END\n")


def write_ligand(holo_path, path):
    """Keep the inhibitor bound at the A-B interface (chain B's 6GX sits 3 A from chain A)."""
    with open(holo_path) as src, open(path, "w") as dst:
        for line in src:
            if line.startswith("HETATM") and line[17:20] == "6GX" and line[21] == "B":
                dst.write(line)
        dst.write("END\n")


def style(obj, surface=True):
    cmd.show("cartoon", obj)
    if surface:
        cmd.show("surface", obj)
    cmd.color("bio_green", obj)
    cmd.set("cartoon_color", "bio_green", obj)


def caption(img, lines):
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=13)
    y = SIZE - 16 - 16 * (len(lines) - 1)
    for text in lines:
        draw.text((14, y), text, fill=(139, 148, 158), font=font)
        y += 16
    return img


def main():
    pymol.finish_launching(["pymol", "-qc"])
    cmd.reinitialize()
    cmd.bg_color("black")
    cmd.set_color("bio_green", GREEN)
    cmd.set_color("bio_teal", TEAL)
    cmd.set("transparency", 0.45)
    cmd.set("depth_cue", 1)
    cmd.set("specular", 0.4)
    cmd.set("ambient", 0.35)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        apo_pdb, holo_pdb = tmp / f"{APO_ID}.pdb", tmp / f"{HOLO_ID}.pdb"
        download(APO_ID, apo_pdb)
        download(HOLO_ID, holo_pdb)

        morph_pdb, ligand_pdb = tmp / "morph.pdb", tmp / "ligand.pdb"
        write_morph(read_chain(apo_pdb, "A"), read_chain(holo_pdb, "A"), morph_pdb, MORPH_FRAMES)
        write_ligand(holo_pdb, ligand_pdb)

        cmd.load(str(morph_pdb), "morph")
        cmd.load(str(ligand_pdb), "ligand")
        cmd.load(str(holo_pdb), "dimer")
        cmd.remove("dimer and not polymer.protein and not resn 6GX")
        cmd.remove("dimer and not (chain A or chain B)")
        cmd.color("bio_teal", "dimer and chain B")
        cmd.set("cartoon_color", "bio_teal", "dimer and chain B")
        cmd.hide("everything", "dimer")
        style("dimer")
        cmd.show("sticks", "dimer and resn 6GX")

        style("morph", surface=False)
        cmd.show("sticks", "ligand")
        cmd.color("bio_teal", "ligand")
        cmd.hide("everything", "ligand")
        cmd.show("sticks", "ligand")
        cmd.set("stick_radius", 0.35, "ligand")
        cmd.disable("dimer")
        cmd.disable("ligand")

        frames = []

        cmd.enable("morph")
        cmd.orient("morph")
        cmd.zoom("morph", buffer=8)
        for i in range(MORPH_FRAMES):
            cmd.frame(i + 1)
            if i >= LIGAND_FROM:
                cmd.enable("ligand")
            path = tmp / f"m_{i:03d}.png"
            cmd.png(str(path), width=SIZE, height=SIZE, ray=1, quiet=1)
            frames.append(caption(Image.open(path).convert("RGB"), [
                "PD-L1 apo (5C3T) to inhibitor-bound (5J89)",
                "interpolated between experimental structures",
            ]))

        cmd.disable("morph")
        cmd.disable("ligand")
        cmd.enable("dimer")
        cmd.orient("dimer")
        cmd.zoom("dimer", buffer=6)
        for i in range(DIMER_FRAMES):
            cmd.turn("y", 360 / DIMER_FRAMES)
            path = tmp / f"d_{i:03d}.png"
            cmd.png(str(path), width=SIZE, height=SIZE, ray=1, quiet=1)
            frames.append(caption(Image.open(path).convert("RGB"), [
                "Inhibitor-bound PD-L1 dimer (5J89)",
            ]))

        P = [f.convert("P", palette=Image.ADAPTIVE) for f in frames]
        P[0].save(OUT, save_all=True, append_images=P[1:], duration=60, loop=0, optimize=True)

    cmd.quit()
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
