"""First Monte Carlo sweep: float vs fixed-point unitary MUSIC.

Usage:  python sweep_rmse.py [n_trials]
Outputs: results/rmse_vs_snr.csv, results/jacobi_convergence.csv,
         results/rmse_vs_snr.png
"""

import csv
import os
import sys

import numpy as np

from doa_golden import (
    MimoArray, Quantizers, complex_music_doa, jacobi_evd, make_fixed,
    real_valued_scm, normalize_frame, simulate_snapshots, unitary_music_doa,
)

ARR = MimoArray()
GRID = np.arange(-90.0, 90.0 + 1e-9, 1.0)      # 181-point ROM
TRUE = np.array([-10.0, 5.0])                   # 15 deg ~ one beamwidth
M = 128
SNRS = [-10, -5, 0, 5, 10, 15, 20]
SUCCESS_TOL = 2.0                               # deg, both sources

FIXED = {
    # name: (input, scm, jacobi, music)  -- ap_fixed<W, I>
    "Fixed A (16/32/24/24)": Quantizers(make_fixed(16, 1), make_fixed(32, 5),
                                        make_fixed(24, 6), make_fixed(24, 5)),
    "Fixed B (12/20/18/18)": Quantizers(make_fixed(12, 1), make_fixed(20, 5),
                                        make_fixed(18, 6), make_fixed(18, 5)),
}


def run(n_trials: int):
    os.makedirs("results", exist_ok=True)
    methods = ["Complex MUSIC (float, eigh)", "Unitary MUSIC (float, Jacobi)", *FIXED]
    rows = []
    for coherent in (False, True):
        for snr in SNRS:
            rng = np.random.default_rng(1000 + snr + (500 if coherent else 0))
            err = {m: [] for m in methods}
            ok = {m: 0 for m in methods}
            for _ in range(n_trials):
                x = simulate_snapshots(ARR, TRUE, snr, M, rng, coherent=coherent)
                ests = {
                    methods[0]: complex_music_doa(x, ARR, 2, GRID),
                    methods[1]: unitary_music_doa(x, ARR, 2, GRID),
                }
                for name, qz in FIXED.items():
                    ests[name] = unitary_music_doa(x, ARR, 2, GRID, qz=qz)
                for m, e in ests.items():
                    d = np.sort(e) - TRUE
                    err[m].append(d)
                    ok[m] += int(np.all(np.abs(d) < SUCCESS_TOL))
            for m in methods:
                e = np.array(err[m])
                rows.append(dict(coherent=coherent, snr_db=snr, method=m,
                                 rmse_deg=float(np.sqrt(np.mean(e ** 2))),
                                 success_rate=ok[m] / n_trials, trials=n_trials))
            print(f"coherent={coherent!s:5} snr={snr:4} " + "  ".join(
                f"{m.split(' (')[0][:14]}{'' if 'Fixed' not in m else m[6]}:"
                f"{r['rmse_deg']:.3f}/{r['success_rate']:.2f}"
                for m, r in zip(methods, rows[-len(methods):])))
    with open("results/rmse_vs_snr.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return methods, rows


def convergence(n_trials: int = 200, n_sweeps: int = 8):
    """Off-diagonal Frobenius norm (relative) after each sweep."""
    rng = np.random.default_rng(7)
    configs = {"float": None, **{k: v for k, v in FIXED.items()}}
    out = []
    for name, qz in configs.items():
        hist = []
        for _ in range(n_trials):
            x, _ = normalize_frame(simulate_snapshots(ARR, TRUE, 10, M, rng))
            if qz is not None:
                x = qz.input(x.real) + 1j * qz.input(x.imag)
            r = real_valued_scm(x, qz.scm if qz else (lambda a: a))
            res = jacobi_evd(r, n_sweeps, qz.jacobi if qz else (lambda a: a))
            hist.append(np.array(res.off_norm_per_sweep) / np.linalg.norm(r))
        h = np.median(np.array(hist), axis=0)
        for s, v in enumerate(h, 1):
            out.append(dict(config=name, sweep=s, median_rel_offnorm=float(v)))
        print(f"Jacobi {name:22}: " + " ".join(f"{v:.1e}" for v in h))
    with open("results/jacobi_convergence.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)


def plot(methods, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]   # categorical slots 1-4
    markers = ["o", "s", "^", "D"]
    styles = ["-", "-", "--", ":"]
    # Left: RMSE, uncorrelated sources. Right: resolution probability,
    # coherent sources (RMSE is outlier-dominated there, so it misleads).
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4))
    panels = [
        (axes[0], False, "rmse_deg", "Uncorrelated sources: RMSE", "RMSE (deg)", True),
        (axes[1], True, "success_rate",
         f"Coherent sources: P(both within {SUCCESS_TOL:g} deg)", "Resolution probability", False),
    ]
    for ax, coherent, key, title, ylab, logy in panels:
        for m, c, mk, ls in zip(methods, colors, markers, styles):
            pts = [r for r in rows if r["coherent"] == coherent and r["method"] == m]
            ax.plot([p["snr_db"] for p in pts], [p[key] for p in pts],
                    ls, color=c, marker=mk, markersize=6, linewidth=2, label=m)
        if logy:
            ax.set_yscale("log")
        else:
            ax.set_ylim(0, 1.05)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("SNR (dB)")
        ax.set_ylabel(ylab)
        ax.grid(True, which="both", color="#e4e2da", linewidth=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, frameon=False, fontsize=8.5, loc="lower center", ncol=4)
    fig.suptitle(f"N = 8 virtual ULA (2Tx x 4Rx), M = {M}, DOAs {TRUE[0]:g} deg / {TRUE[1]:g} deg, "
                 f"{rows[0]['trials']} trials/point", fontsize=10)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig("results/rmse_vs_snr.png", dpi=200)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    methods, rows = run(n)
    convergence()
    plot(methods, rows)
