"""Project 05: N-1 contingency screening toolkit with parallel execution.
Network: IEEE 118-bus (Christie 1993, University of Washington archive) as
shipped with pandapower.
"""
import time, json, copy
import numpy as np, pandas as pd
import pandapower as pp, pandapower.networks as pn
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor

OUT = "/tmp/work/out/"
V_MIN, V_MAX, LOAD_MAX = 0.94, 1.06, 100.0
_NET = None

def build_net():
    """IEEE 118-bus with derived thermal ratings.

    The University of Washington archive states the line MVA limits were not part
    of the original 1962 AEP data and were made up. With pandapower's defaults the
    base case peaks at 4.5 percent loading, which makes N-1 screening vacuous.
    Ratings are therefore derived as 1.3x the base case apparent flow with a
    20 MVA floor. This is a modelling choice, not measured data, and is stated
    as such in the write-up.
    """
    net = pn.case118()
    pp.runpp(net, numba=False)
    i_base = net.res_line.i_ka.values
    net.line["max_i_ka"] = np.maximum(1.3 * i_base, 0.05) * net.line.parallel.values
    pp.runpp(net, numba=False)
    assert net.res_line.loading_percent.max() <= 100.0, "base case must be secure"
    return net

def _init(net):
    global _NET
    _NET = net

def _screen(idx):
    net = _NET
    net.line.at[idx, "in_service"] = False
    try:
        pp.runpp(net, numba=False)
        r = dict(line=int(idx), converged=True,
            max_loading=float(net.res_line.loading_percent.max()),
            v_min=float(net.res_bus.vm_pu.min()), v_max=float(net.res_bus.vm_pu.max()),
            n_thermal=int((net.res_line.loading_percent > LOAD_MAX).sum()),
            n_voltage=int((net.res_bus.vm_pu < V_MIN).sum() + (net.res_bus.vm_pu > V_MAX).sum()))
    except Exception:
        r = dict(line=int(idx), converged=False, max_loading=np.nan,
                 v_min=np.nan, v_max=np.nan, n_thermal=0, n_voltage=0)
    net.line.at[idx, "in_service"] = True
    return r

class ContingencyAnalyzer:
    """Screen every single line outage on a network, sequentially or in parallel."""
    def __init__(self, net): self.net = net
    def screen(self, parallel=False, workers=None):
        idxs = list(self.net.line.index)
        t0 = time.perf_counter()
        if parallel:
            with ProcessPoolExecutor(max_workers=workers, initializer=_init,
                                     initargs=(self.net,)) as ex:
                recs = list(ex.map(_screen, idxs, chunksize=8))
        else:
            _init(copy.deepcopy(self.net))
            recs = [_screen(i) for i in idxs]
        df = pd.DataFrame(recs); df["n_violations"] = df.n_thermal + df.n_voltage
        return df, time.perf_counter() - t0

if __name__ == "__main__":
    net = build_net()
    base = dict(n_bus=len(net.bus), n_line=len(net.line), n_trafo=len(net.trafo),
                n_gen=len(net.gen), n_load=len(net.load),
                total_load_mw=round(float(net.load.p_mw.sum()), 1),
                base_max_loading=round(float(net.res_line.loading_percent.max()), 2),
                base_v_min=round(float(net.res_bus.vm_pu.min()), 4),
                base_v_max=round(float(net.res_bus.vm_pu.max()), 4))
    print("BASE", json.dumps(base), flush=True)

    a = ContingencyAnalyzer(net)
    seq, t_seq = a.screen(parallel=False)
    print(f"sequential {t_seq:.2f}s", flush=True)
    timings = {"1": t_seq}
    par4 = None
    for w in (2, 4):
        df, t = a.screen(parallel=True, workers=w)
        timings[str(w)] = t
        if w == 4: par4 = df
        print(f"workers={w}  {t:.2f}s  speedup {t_seq/t:.2f}x", flush=True)

    m = seq.merge(par4, on="line", suffixes=("_s", "_p"))
    identical = bool(np.allclose(m.max_loading_s.fillna(-1), m.max_loading_p.fillna(-1))
                     and (m.n_violations_s == m.n_violations_p).all())
    print("identical results:", identical, flush=True)

    seq = seq.sort_values("max_loading", ascending=False)
    seq.to_csv(OUT+"p05_contingency_118bus.csv", index=False)
    best = min(timings.values())
    summary = dict(base=base, timings={k: round(v,3) for k,v in timings.items()},
        identical_results=identical, cpu_count=4,
        n_contingencies=int(len(seq)), n_converged=int(seq.converged.sum()),
        n_diverged=int((~seq.converged).sum()),
        n_with_violations=int((seq.n_violations>0).sum()),
        n_thermal_cases=int((seq.n_thermal>0).sum()),
        n_voltage_cases=int((seq.n_voltage>0).sum()),
        worst_line=int(seq.iloc[0].line), worst_loading=round(float(seq.iloc[0].max_loading),1),
        speedup=round(t_seq/best,2), runtime_reduction_pct=round(100*(1-best/t_seq),1))
    json.dump(summary, open(OUT+"p05_summary.json","w"), indent=1)
    print(json.dumps(summary, indent=1), flush=True)
    print(seq.head(10)[["line","max_loading","v_min","n_thermal","n_voltage"]].to_string(index=False))

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    ok = seq[seq.converged]
    ax[0].bar(range(len(ok)), ok.max_loading, width=1.0,
              color=["#C4714A" if v > LOAD_MAX else "#4A7C6F" for v in ok.max_loading])
    ax[0].axhline(LOAD_MAX, ls="--", c="#1A1714", lw=1)
    ax[0].annotate("thermal limit", (len(ok)*0.45, LOAD_MAX*1.04), fontsize=9)
    ax[0].set(xlabel="Contingency, ranked by severity", ylabel="Max line loading [%]",
              title=f"N-1 screening, IEEE 118-bus, {len(ok)} outages")
    ks = sorted(int(k) for k in timings)
    ax[1].plot(ks, [t_seq/timings[str(k)] for k in ks], "o-", color="#4A7C6F", lw=2, label="measured")
    ax[1].plot([1, max(ks)], [1, max(ks)], ls=":", c="#9B948C", label="linear scaling")
    ax[1].set(xlabel="Worker processes", ylabel="Speed-up vs sequential",
              title="Parallel scaling on 4 cores", xticks=ks); ax[1].legend(fontsize=9)
    for x in ax: x.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(OUT+"p05_results.png", dpi=160)
    print("figures written", flush=True)
