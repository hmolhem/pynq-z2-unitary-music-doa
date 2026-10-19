"""
jacobi_bitexact.py -- Integer-exact model of the HLS Jacobi EVD kernel (Tier 2).

Bit-true reference for hls/jacobi. Every operation is an integer add,
shift or multiply with exactly defined rounding, so C simulation and
C/RTL co-simulation must match this model bit for bit.

Input   : R_re from the SCM kernel, 64 raw words, ap_fixed<32,5>  (Q5.27)
Internal: A entries  ap_fixed<32,7>  (Q7.25, |a| <= ||R||_2 <= 32)
          V entries  ap_fixed<32,2>  (Q2.30, |v| <= 1)
          c, s       ap_fixed<32,2>  (Q2.30)
          angles     ap_fixed<32,4>  (radians, 28 fractional bits)
Output  : 8 eigenvalues (diag A, raw Q7.25) then V row-major (raw Q2.30);
          column j of V is the eigenvector of eigenvalue j. Not sorted.

Rotation (p, q), cyclic by row, a fixed number of sweeps:
    phi   = atan2(2 a_pq, a_qq - a_pp)       CORDIC vectoring, x >= 0
    theta = phi / 2                           |theta| <= pi/4
    (c, s) = (cos theta, sin theta)           CORDIC rotation, gain precompensated
    A <- J^T A J,  V <- V J,  J = [[c, s], [-s, c]] in the (p, q) plane

No square root and no division: the angle and (c, s) come from shift-add
CORDIC iterations, and only the A/V updates use multipliers.
"""

from __future__ import annotations

import math

import numpy as np

N = 8
N_SWEEPS = 4
R_FRAC = 27            # input:  ap_fixed<32,5>
A_FRAC = 25            # matrix: ap_fixed<32,7>
CS_FRAC = 30           # c, s, V: ap_fixed<32,2>
ANG_FRAC = 28          # angles in radians
N_CORDIC = 24          # iterations per CORDIC (vectoring and rotation)
NORM_BITS = 30         # CORDIC inputs are normalized to |x|, |y| < 2^30

ATAN_TABLE = [int(round(math.atan(2.0 ** -i) * 2 ** ANG_FRAC)) for i in range(N_CORDIC)]
_k = 1.0
for _i in range(N_CORDIC):
    _k /= math.sqrt(1.0 + 2.0 ** (-2 * _i))
CORDIC_KINV = int(round(_k * 2 ** CS_FRAC))           # 1/gain in Q2.30
PAIRS = [(p, q) for p in range(N - 1) for q in range(p + 1, N)]


def _rnd(x: int, shift: int) -> int:
    """Round half toward +inf, then drop `shift` bits (AP_RND)."""
    return (x + (1 << (shift - 1))) >> shift


def cordic_vectoring(x: int, y: int) -> int:
    """atan2(y, x) for x >= 0, as an ANG_FRAC integer.

    The inputs are first normalized (both shifted by the same amount) so the
    larger magnitude has NORM_BITS bits: small off-diagonal entries late in
    the sweeps still get a full-precision angle.
    """
    m = max(abs(x), abs(y))
    if m == 0:
        return 0
    sh = NORM_BITS - m.bit_length()
    if sh > 0:
        x, y = x << sh, y << sh
    elif sh < 0:
        x, y = x >> -sh, y >> -sh
    z = 0
    for i in range(N_CORDIC):
        if y >= 0:
            x, y, z = x + (y >> i), y - (x >> i), z + ATAN_TABLE[i]
        else:
            x, y, z = x - (y >> i), y + (x >> i), z - ATAN_TABLE[i]
    return z


def cordic_rotation(theta: int) -> tuple[int, int]:
    """(cos theta, sin theta) in Q2.30 for |theta| <= pi/4."""
    x, y, z = CORDIC_KINV, 0, theta
    for i in range(N_CORDIC):
        if z >= 0:
            x, y, z = x - (y >> i), y + (x >> i), z - ATAN_TABLE[i]
        else:
            x, y, z = x + (y >> i), y - (x >> i), z + ATAN_TABLE[i]
    return x, y


def rotation_cs(app: int, aqq: int, apq: int) -> tuple[int, int]:
    """Jacobi rotation that zeroes a_pq: tan(2 theta) = 2 a_pq / (a_qq - a_pp)."""
    x, y = aqq - app, 2 * apq
    if x < 0:                       # rotate by pi: same tan(2 theta), x >= 0
        x, y = -x, -y
    phi = cordic_vectoring(x, y)    # |phi| <= pi/2
    return cordic_rotation(phi >> 1)


def jacobi_raw(r_raw: np.ndarray, n_sweeps: int = N_SWEEPS):
    """Raw R (Q5.27, 8x8) -> (eigenvalues raw Q7.25, V raw Q2.30), as the HLS kernel."""
    sh_in = R_FRAC - A_FRAC
    a = [[_rnd(int(v), sh_in) for v in row] for row in np.asarray(r_raw)]
    v = [[(1 << CS_FRAC) if i == j else 0 for j in range(N)] for i in range(N)]
    one = CS_FRAC
    for _ in range(n_sweeps):
        for p, q in PAIRS:
            app, aqq, apq = a[p][p], a[q][q], a[p][q]
            c, s = rotation_cs(app, aqq, apq)
            c2, s2, cs = _rnd(c * c, one), _rnd(s * s, one), _rnd(c * s, one)
            for k in range(N):
                if k != p and k != q:
                    akp, akq = a[k][p], a[k][q]
                    nkp = _rnd(c * akp - s * akq, one)
                    nkq = _rnd(s * akp + c * akq, one)
                    a[k][p] = a[p][k] = nkp
                    a[k][q] = a[q][k] = nkq
                vkp, vkq = v[k][p], v[k][q]
                v[k][p] = _rnd(c * vkp - s * vkq, one)
                v[k][q] = _rnd(s * vkp + c * vkq, one)
            a[p][p] = _rnd(c2 * app - 2 * cs * apq + s2 * aqq, one)
            a[q][q] = _rnd(s2 * app + 2 * cs * apq + c2 * aqq, one)
            a[p][q] = a[q][p] = 0
    lim = 1 << 31
    d = np.array([a[i][i] for i in range(N)], dtype=np.int64)
    vv = np.array(v, dtype=np.int64)
    for x in (d, vv, np.array(a, dtype=np.int64)):
        assert np.all(x < lim) and np.all(x >= -lim), "32-bit range exceeded"
    return d, vv


def jacobi_float(d_raw: np.ndarray, v_raw: np.ndarray):
    """Raw outputs -> (eigenvalues, eigenvectors) as floats, sorted descending."""
    d = d_raw.astype(float) * 2.0 ** -A_FRAC
    v = v_raw.astype(float) * 2.0 ** -CS_FRAC
    order = np.argsort(d)[::-1]
    return d[order], v[:, order]


def write_vectors_header(path: str, r_frames: list) -> None:
    """C header for the HLS testbench: input R words and expected 72 output words."""
    lines = [
        "// Generated by python/gen_jacobi_vectors.py -- do not edit.",
        "#ifndef JACOBI_VECTORS_H",
        "#define JACOBI_VECTORS_H",
        f"#define JAC_TV_FRAMES {len(r_frames)}",
        f"static const int JAC_TV_IN[{len(r_frames)}][{N * N}] = {{",
    ]
    outs = []
    for r in r_frames:
        lines.append("  {" + ",".join(str(int(x)) for x in np.ravel(r)) + "},")
        d, v = jacobi_raw(r)
        outs.append(np.concatenate([d, v.ravel()]))
    lines.append("};")
    lines.append(f"static const int JAC_TV_OUT[{len(r_frames)}][{N + N * N}] = {{")
    for o in outs:
        lines.append("  {" + ",".join(str(int(x)) for x in o) + "},")
    lines += ["};", "#endif", ""]
    with open(path, "w") as f:
        f.write("\n".join(lines))
