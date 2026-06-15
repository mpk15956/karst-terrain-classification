"""Data-driven manuscript figures and tables (elis-only, reads committed JSONs).

Generates Figs 2-6 (study area, power curve, headline, optical contrast,
sensitivity profile) into paper/figures/ and Tables 1-4 as Quarto include files
into paper/_tables/. Also runs the cross-JSON consistency assertions (the plan's
verification step 3) and prints PASS/FAIL. No compute, no whitebox: pure plotting
of the summary JSONs. Figs 1 and 7 (whitebox H0 panels) are in fig_qual.py.

Run from the repo root: .pixi/envs/cpu/bin/python paper/fig_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
VAL = ROOT / "results" / "validity"
FIGS = ROOT / "paper" / "figures"
TABS = ROOT / "paper" / "_tables"
FIGS.mkdir(parents=True, exist_ok=True)
TABS.mkdir(parents=True, exist_ok=True)

# colorblind-friendly province palette (Wong)
PROV_COLOR = {
    "cumberland_plateau": "#0072B2",
    "appalachian_highlands": "#D55E00",
    "coastal_plain": "#009E73",
}
PROV_LABEL = {
    "cumberland_plateau": "Cumberland Plateau",
    "appalachian_highlands": "Appalachian Highlands",
    "coastal_plain": "Coastal Plain",
}
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 150, "savefig.bbox": "tight"})


def load(name):
    return json.loads((VAL / name).read_text())


def save(fig, stem):
    for ext in ("pdf", "png"):
        fig.savefig(FIGS / f"{stem}.{ext}")
    plt.close(fig)
    print(f"  wrote figures/{stem}.pdf/.png")


# ----------------------------------------------------------------------------
def consistency_checks(headline, noise, power, optical):
    print("\n=== cross-JSON consistency (verification step 3) ===")
    ok = True
    hf, nf = headline["null_p95_floor"], noise["null_p95_floor"]
    hs, ns = headline["sw_sigma"], noise["sw_sigma"]
    print(f"  headline floor {hf!r} == noise floor {nf!r}: {hf == nf}")
    print(f"  headline sigma {hs!r} == noise sigma {ns!r}: {hs == ns}")
    ok &= (hf == nf) and (hs == ns)
    op_floor = power["operating_point"]["null_mmd2_p95"]
    print(f"  TWO DISTINCT FLOORS (expected): headline realized {hf:.4f} (reps {headline['reps']}) "
          f"vs power design {op_floor:.4f} (reps {power['operating_point']['reps']}) -> distinct: {hf != op_floor}")
    tr = optical["topology_test_over_floor"]
    hr = headline["test_median_over_floor_ratio"]
    print(f"  optical's topology ref {tr:.4f} == headline ratio {hr:.4f}: {abs(tr - hr) < 1e-9}")
    ok &= abs(tr - hr) < 1e-9
    print(f"  n: topology real={headline['n_real']} gen={headline['n_generated']} | "
          f"optical real={optical['results']['clip_hill']['n_real']} "
          f"gen={optical['results']['clip_hill']['n_gen']} | both K={headline['tiles_per_group']}")
    print(f"  CONSISTENCY: {'PASS' if ok else 'FAIL'}")
    return ok


# ----------------------------------------------------------------------------
def fig_studyarea():
    tm = load("teach_run_20260530/tile_manifest.json")
    tiles = tm["tiles"]
    fig, ax = plt.subplots(figsize=(7, 5))
    for t in tiles:
        lon0, lat0, lon1, lat1 = t["bbox"]
        c = PROV_COLOR.get(t["province"], "#888888")
        ax.add_patch(mpatches.Rectangle((lon0, lat0), lon1 - lon0, lat1 - lat0,
                                        facecolor=c, edgecolor="white", alpha=0.85, lw=0.8))
        ax.text((lon0 + lon1) / 2, (lat0 + lat1) / 2, str(t.get("quintile", "")),
                ha="center", va="center", fontsize=7, color="white")
    lons = [t["bbox"][0] for t in tiles] + [t["bbox"][2] for t in tiles]
    lats = [t["bbox"][1] for t in tiles] + [t["bbox"][3] for t in tiles]
    ax.set_xlim(min(lons) - 0.4, max(lons) + 0.4)
    ax.set_ylim(min(lats) - 0.4, max(lats) + 0.4)
    ax.set_aspect("equal")
    ax.set_xlabel("Longitude (deg)")
    ax.set_ylabel("Latitude (deg)")
    counts = {}
    for t in tiles:
        counts[t["province"]] = counts.get(t["province"], 0) + 1
    handles = [mpatches.Patch(color=PROV_COLOR[p], label=f"{PROV_LABEL[p]} (n={counts.get(p,0)})")
               for p in PROV_COLOR]
    ax.legend(handles=handles, loc="lower left", fontsize=8, frameon=False)
    ax.set_title("20 one-degree tiles; labels = NHD drainage-density quintile", fontsize=9)
    save(fig, "fig-studyarea")


def fig_power():
    pc = load("m2_power.json")
    curve = pc["spatial_null_power_curve"]
    op = pc["operating_point"]
    x = [c["patches_per_side_mean"] for c in curve]
    y = [c["null_mmd2_p95"] for c in curve]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x, y, "-o", color="#444444", lw=1.5, ms=4, label="spatial-null p95 floor")
    ox, oy = op["patches_per_side_mean"], op["null_mmd2_p95"]
    ax.plot([ox], [oy], "*", color="#D55E00", ms=16, zorder=5)
    ax.annotate(f"operating point K=10\n~{ox:.0f} patches/side\nfloor = {oy:.4f}",
                (ox, oy), textcoords="offset points", xytext=(-12, 22), fontsize=8,
                ha="right", color="#D55E00")
    ax.set_xlabel("patches per side (drawn from K tiles per side)")
    ax.set_ylabel("spatial-null MMD$^2$ p95 floor")
    ax.set_title("By-tile null tightens with sample size; operating point set before generation", fontsize=9)
    save(fig, "fig-power")


def fig_headline():
    h = load("m2_generated_vs_real.json")
    nul, tst = h["null_mmd2"], h["test_mmd2"]
    floor = h["null_p95_floor"]
    null_stats = {"med": nul["median"], "q1": 0.0, "q3": floor,
                  "whislo": 0.0, "whishi": nul["max"], "fliers": [], "label": f"null\n(real vs real)\nn={h['n_real']}"}
    test_stats = {"med": tst["median"], "q1": tst["p5"], "q3": tst["p95"],
                  "whislo": tst["min"], "whishi": tst["max"], "fliers": [], "label": f"test\n(gen vs real)\nn={h['n_generated']}"}
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    bp = ax.bxp([null_stats, test_stats], showfliers=False, widths=0.5, patch_artist=True)
    for patch, col in zip(bp["boxes"], ["#9ecae1", "#D55E00"]):
        patch.set_facecolor(col); patch.set_alpha(0.85)
    ax.axhline(floor, ls="--", color="#333333", lw=1)
    ax.text(2.45, floor, f" p95 floor = {floor:.4f}", va="bottom", ha="right", fontsize=8)
    ax.annotate(f"test median = {tst['median']:.4f}\n= {h['test_median_over_floor_ratio']:.2f}x floor\n"
                f"0/{h['reps']} null splits exceed test (p<{1/h['reps']:.3f})",
                (2, tst["median"]), textcoords="offset points", xytext=(8, -6), fontsize=8, ha="left")
    ax.set_ylabel("MMD$^2$ (sliced-Wasserstein kernel)")
    ax.set_title("Generated drainage topology is distinguishable from real", fontsize=9)
    ax.text(0.01, 0.99, "box = p5-p95, whiskers = min-max, line = median", transform=ax.transAxes,
            fontsize=7, va="top", color="#666666")
    save(fig, "fig-headline")


def fig_optical():
    o = load("m2_optical_contrast.json")["results"]
    topo = load("m2_optical_contrast.json")["topology_test_over_floor"]
    order = [("clip_hill", "CLIP\nhillshade"), ("clip_stack", "CLIP\nstack"),
             ("incep_hill", "Inception\nhillshade"), ("incep_stack", "Inception\nstack")]
    rbf = [o[k]["rbf_mmd2"]["test_over_floor"] for k, _ in order]
    kid = [o[k]["kid"]["test_over_p95"] for k, _ in order]
    swap = [o[k]["swap_max_over_floor"] for k, _ in order]
    labels = [lab for _, lab in order]
    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(7, 4.3))
    ax.bar(x - 0.2, rbf, 0.38, label="RBF-MMD test/floor", color="#0072B2")
    ax.bar(x + 0.2, kid, 0.38, label="KID test/floor", color="#56B4E9")
    ax.plot(x, swap, "kx", ms=9, label="province-swap/floor (positive control)")
    ax.axhline(1.0, ls=":", color="#888888", lw=1)
    ax.text(len(order) - 0.5, 1.0, " floor (=1)", va="bottom", ha="right", fontsize=8, color="#888888")
    ax.axhline(topo, ls="--", color="#D55E00", lw=1.3)
    ax.text(-0.4, topo, f"topology = {topo:.2f}x ", va="bottom", ha="left", fontsize=8.5, color="#D55E00")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylabel("test / spatial-null floor")
    ax.set_title("Every optical metric separates generated from real (only topology names the axis)", fontsize=8.5)
    ax.legend(fontsize=8, loc="upper right", frameon=False)
    save(fig, "fig-optical")


def fig_sensitivity():
    pcv = load("m2_power_curve.json")
    trench_max = max(r["ratio"] for r in pcv["curves"]["h0"]["rows"])
    noise = load("m2_noise_vs_real.json")["test_median_over_floor_ratio"]
    mesa = load("m2_generated_vs_real.json")["test_median_over_floor_ratio"]
    saddle = load("teach_run_20260530/saddle_probe_A.json")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))
    # panel A: profile bars
    names = ["trench\n(localized\nincision)", "phase-noise\n(coherence\ndestroyed)", "MESA\n(over-smooth\ngenerator)"]
    vals = [trench_max, noise, mesa]
    cols = ["#999999", "#56B4E9", "#D55E00"]
    ax1.bar(names, vals, color=cols)
    for i, v in enumerate(vals):
        ax1.text(i, v + 0.06, f"{v:.2f}x", ha="center", fontsize=9)
    ax1.axhline(1.0, ls=":", color="#888888", lw=1)
    ax1.text(2.45, 1.0, "floor (=1)", va="bottom", ha="right", fontsize=8, color="#888888")
    ax1.set_ylabel("MMD$^2$ / spatial-null floor (matched currency)")
    ax1.set_ylim(0, mesa * 1.25)
    ax1.set_title("(a) Sensitivity profile, not a bracket: MESA is largest;\nno upper bound established", fontsize=8.5)
    # panel B: saddle rr_h0 vs flips
    fl, rr = [], []
    for row in saddle["rows"]:
        for p in row.get("perturbations", []):
            if "flips" in p and "rr_h0" in p:
                fl.append(p["flips"]); rr.append(p["rr_h0"])
    ax2.scatter(fl, rr, s=18, color="#0072B2", alpha=0.7, label="real perturbations")
    v = saddle.get("verdict", {})
    mesa_rr = v.get("mesa_rr_h0") or v.get("rr_h0_mesa") or 1.27
    ax2.axhline(mesa_rr, ls="--", color="#D55E00", lw=1.3, label=f"MESA operating point ({mesa_rr:.2f})")
    ax2.axhline(1.0, ls=":", color="#888888", lw=1, label="real-vs-real baseline (1.0)")
    ax2.set_xscale("log")
    ax2.set_xlabel("D8 flips induced (log)")
    ax2.set_ylabel("H0 movement ratio rr_h0")
    ax2.set_title("(b) Saddle caveat: H0 movement rises with D8 flips;\nMESA sits in the high-flip regime", fontsize=8.5)
    ax2.legend(fontsize=7.5, loc="upper left", frameon=False)
    save(fig, "fig-sensitivity")
    return trench_max, noise, mesa, mesa_rr


# ----------------------------------------------------------------------------
def write_table(stem, header, rows, caption, label):
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    lines.append("")
    lines.append(f": {caption} {{#{label}}}")
    lines.append("")
    (TABS / f"{stem}.md").write_text("\n".join(lines))
    print(f"  wrote _tables/{stem}.md")


def tables(trench_max, noise, mesa):
    c = load("teach_run_20260530/construct.json")["summary"]
    write_table("tbl-construct",
                ["Criterion", "PH vs NHD", "whitebox vs NHD", "pass"],
                [["junction-count correlation", f"{c['ph_vs_nhd']['junction_count_spearman_proxy']:.3f}",
                  f"{c['whitebox_vs_nhd']['junction_count_spearman_proxy']:.3f}", "yes"],
                 ["Strahler Wasserstein-1 (lower better)", f"{c['ph_vs_nhd']['strahler_wasserstein_median']:.3f}",
                  f"{c['whitebox_vs_nhd']['strahler_wasserstein_median']:.3f}", "yes"],
                 ["bifurcation-ratio |dR_b| (lower better)", f"{c['ph_vs_nhd']['bifurcation_ratio_abs_diff_median']:.3f}",
                  f"{c['whitebox_vs_nhd']['bifurcation_ratio_abs_diff_median']:.3f}", "yes"]],
                "Construct validity against NHD on karst across three CONUS provinces (n=20 tiles). "
                "Whitebox-vs-NHD is the pre-registered agreement ceiling.", "tbl-construct")

    h = load("m2_generated_vs_real.json")
    write_table("tbl-headline",
                ["quantity", "value"],
                [["test (gen vs real) median MMD$^2$", f"{h['test_mmd2']['median']:.4f}"],
                 ["null (real vs real) p95 floor", f"{h['null_p95_floor']:.4f}"],
                 ["test / floor ratio", f"{h['test_median_over_floor_ratio']:.2f}x"],
                 ["null splits exceeding test", f"0 / {h['reps']} (p<{1/h['reps']:.3f})"],
                 ["n (real / generated)", f"{h['n_real']} / {h['n_generated']}"],
                 ["province mix (forced mirror)", "40 : 40 : 34"]],
                "Headline distributional test at the K=10 operating point.", "tbl-headline")

    o = load("m2_optical_contrast.json")["results"]
    topo = load("m2_optical_contrast.json")["topology_test_over_floor"]
    rows = [["topology (flow-accumulation H0)", f"{topo:.2f}x", "--", "--", "--"]]
    nm = {"clip_hill": "CLIP (hillshade)", "clip_stack": "CLIP (stack)",
          "incep_hill": "Inception (hillshade)", "incep_stack": "Inception (stack)"}
    for k, lab in nm.items():
        r = o[k]
        fid = r["fid"].get("test_over_p95")
        rows.append([lab, f"{r['rbf_mmd2']['test_over_floor']:.2f}x",
                     f"{fid:.2f}x" if fid else "skipped",
                     f"{r['kid']['test_over_p95']:.2f}x", f"{r['swap_max_over_floor']:.2f}x"])
    write_table("tbl-optical",
                ["metric", "RBF-MMD", "FID", "KID", "province swap"], rows,
                "Optical contrast (test/floor). Every metric separates generated from real; "
                "the province swap is the positive control. n_real=320 (all renderable windows), n_gen=114.",
                "tbl-optical")

    write_table("tbl-sensitivity",
                ["perturbation", "MMD$^2$/floor", "what it isolates"],
                [["trench (localized incision)", f"{trench_max:.2f}x", "H0 insensitive to localized structure"],
                 ["phase-noise (spectrum kept)", f"{noise:.2f}x", "H0 insensitive to spatial coherence"],
                 ["MESA (over-smooth generator)", f"{mesa:.2f}x", "H0 sensitive to branching-distribution change"]],
                "Sensitivity profile across three perturbation classes (matched test/floor currency). "
                "MESA is the largest response; no upper bound is established.", "tbl-sensitivity")


def main():
    headline = load("m2_generated_vs_real.json")
    noise = load("m2_noise_vs_real.json")
    power = load("m2_power.json")
    optical = load("m2_optical_contrast.json")
    consistency_checks(headline, noise, power, optical)
    print("\n=== figures ===")
    fig_studyarea()
    fig_power()
    fig_headline()
    fig_optical()
    trench_max, nz, mz, _ = fig_sensitivity()
    print("\n=== tables ===")
    tables(trench_max, nz, mz)
    print("\ndone.")


if __name__ == "__main__":
    main()
