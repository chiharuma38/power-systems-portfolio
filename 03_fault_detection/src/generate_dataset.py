"""Project 03, stage 1: generate the labelled dataset.
Network: IEEE 39-bus New England (Athay, Podmore and Virmani 1979) via pandapower.
Run repeatedly; each run appends a chunk to the .npz store.
"""
import sys, os, time
import numpy as np
import pandapower as pp, pandapower.networks as pn

OUT, STORE = "/tmp/work/out/", "/tmp/work/out/p03_dataset.npz"
SEED = 42
LOAD_SIGMA = 0.10          # load scaling noise, 10 percent standard deviation

def features(net):
    """124 measurements: 39 voltage magnitudes, 39 angles, 46 line active flows."""
    return np.concatenate([net.res_bus.vm_pu.values,
                           net.res_bus.va_degree.values,
                           net.res_line.p_from_mw.values])

def run(n_per_class, seed_offset):
    rng = np.random.default_rng(SEED + seed_offset)
    net = pn.case39()
    base_scaling = net.load.scaling.values.copy()
    n_lines = len(net.line)
    X, y_bin, y_loc = [], [], []
    t0 = time.time()
    made = 0
    while made < 2 * n_per_class:
        fault = made >= n_per_class
        net.load.scaling = base_scaling * rng.normal(1.0, LOAD_SIGMA, len(net.load)).clip(0.6, 1.4)
        line = int(rng.integers(0, n_lines)) if fault else -1
        if fault:
            net.line.at[line, "in_service"] = False
        try:
            pp.runpp(net, numba=False)
            X.append(features(net)); y_bin.append(int(fault)); y_loc.append(line)
            made += 1
        except Exception:
            pass
        finally:
            if fault:
                net.line.at[line, "in_service"] = True
        if time.time() - t0 > 33:
            break
    return np.array(X), np.array(y_bin), np.array(y_loc)

if __name__ == "__main__":
    n = int(sys.argv[1]); off = int(sys.argv[2])
    X, yb, yl = run(n, off)
    if os.path.exists(STORE):
        d = np.load(STORE)
        X = np.vstack([d["X"], X]); yb = np.concatenate([d["y_bin"], yb])
        yl = np.concatenate([d["y_loc"], yl])
    np.savez_compressed(STORE, X=X, y_bin=yb, y_loc=yl)
    print(f"store now: X {X.shape}  normal {int((yb==0).sum())}  fault {int((yb==1).sum())}")
