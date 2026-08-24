"""Project 02: HVAC export cable for an offshore wind farm.
Reactive compensation sizing and the practical length limit of an AC connection.

Cable data: pandapower standard type N2XS(FL)2Y 1x300 RM/35 64/110 kV.
Parameter provenance: pandapower/std_types.py, basic_line_std_types, which cites
Heuck, Dettmann and Schulz (2013) p.744.
"""
import json
import numpy as np, pandas as pd
import pandapower as pp
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "/tmp/work/out/"
CABLE = "N2XS(FL)2Y 1x300 RM/35 64/110 kV"
V_KV, F_HZ, FARM_MW = 110.0, 50.0, 200.0
V_MIN, V_MAX, N_CIRC = 0.94, 1.06, 2

_n = pp.create_empty_network()
T = pp.load_std_type(_n, CABLE, element="line")
S_CIRC = float(np.sqrt(3) * V_KV * T["max_i_ka"])

def q_charging(L, n=N_CIRC):
    """No-load charging reactive power, Mvar.  Q = V^2 * w * C * l"""
    c_f = T["c_nf_per_km"] * 1e-9 * L * n
    return (V_KV * 1e3) ** 2 * 2 * np.pi * F_HZ * c_f / 1e6

def make(L, p_mw=FARM_MW, n=N_CIRC):
    """Offshore bus, export cables, onshore slack. Shunts created at zero."""
    net = pp.create_empty_network(f_hz=F_HZ)
    b0 = pp.create_bus(net, vn_kv=V_KV, name="offshore")
    b1 = pp.create_bus(net, vn_kv=V_KV, name="onshore")
    pp.create_ext_grid(net, b1, vm_pu=1.0)
    for k in range(n):
        pp.create_line(net, b0, b1, length_km=L, std_type=CABLE, name=f"circuit_{k}")
    pp.create_sgen(net, b0, p_mw=p_mw, q_mvar=0.0, name="wind farm")
    pp.create_shunt(net, b0, q_mvar=0.0, p_mw=0.0, name="offshore reactor")
    pp.create_shunt(net, b1, q_mvar=0.0, p_mw=0.0, name="onshore reactor")
    return net

def solve(net, L, ratio):
    """Set compensation to `ratio` of charging Mvar, split evenly, then solve."""
    q = q_charging(L) * ratio / 2.0
    net.shunt.loc[:, "q_mvar"] = [q, q]   # positive q_mvar = absorbing = shunt reactor
    try:
        pp.runpp(net, numba=False)
        return dict(converged=True,
            v_off=float(net.res_bus.vm_pu.iloc[0]),
            loading=float(net.res_line.loading_percent.max()),
            p_grid=float(-net.res_ext_grid.p_mw.iloc[0]),
            q_grid=float(-net.res_ext_grid.q_mvar.iloc[0]),
            losses=float(net.res_line.pl_mw.sum()))
    except Exception:
        return dict(converged=False, v_off=np.nan, loading=np.nan,
                    p_grid=np.nan, q_grid=np.nan, losses=np.nan)

def inband(s):
    return s["converged"] and V_MIN <= s["v_off"] <= V_MAX and s["loading"] <= 100.0

if __name__ == "__main__":
    print(f"CABLE {CABLE}")
    print(f"  R {T['r_ohm_per_km']} ohm/km   X {T['x_ohm_per_km']} ohm/km   "
          f"C {T['c_nf_per_km']} nF/km   Imax {T['max_i_ka']} kA")
    print(f"  circuit rating {S_CIRC:.1f} MVA -> {int(np.ceil(FARM_MW/S_CIRC))} circuits for {FARM_MW:.0f} MW\n", flush=True)

    lengths = np.arange(10, 210, 10)
    rows_len, rows_min = [], []
    for L in lengths:
        net = make(L)
        s0 = solve(net, L, 0.0)                              # uncompensated
        rows_len.append(dict(length_km=int(L), q_charge_mvar=q_charging(L),
                             q_pct_of_farm=100*q_charging(L)/FARM_MW,
                             **{f"unc_{k}": v for k, v in s0.items()}))
        # minimum compensation, by bisection
        if inband(s0):
            r_min = 0.0
        else:
            sf = solve(net, L, 1.0)
            if not inband(sf):
                rows_min.append(dict(length_km=int(L), min_comp_ratio=np.nan,
                                     q_comp_mvar=np.nan, feasible=False, **sf)); continue
            lo, hi = 0.0, 1.0
            for _ in range(8):
                mid = (lo + hi) / 2
                if inband(solve(net, L, mid)): hi = mid
                else: lo = mid
            r_min = hi
        s = solve(net, L, r_min)
        rows_min.append(dict(length_km=int(L), min_comp_ratio=r_min,
                             q_comp_mvar=q_charging(L)*r_min, feasible=True, **s))
    df_len, df_min = pd.DataFrame(rows_len), pd.DataFrame(rows_min)

    L_REF, net = 100, make(100)
    df_comp = pd.DataFrame([dict(comp_ratio=r, q_comp_mvar=q_charging(L_REF)*r,
                                 **solve(net, L_REF, r)) for r in np.arange(0, 1.001, 0.05)])

    for d, n in ((df_len,"length_sweep"),(df_comp,"compensation_sweep"),(df_min,"min_compensation")):
        d.to_csv(OUT+f"p02_{n}.csv", index=False)

    g = lambda df, L, c: float(df.loc[df.length_km == L, c].iloc[0])
    feas = df_min[df_min.feasible]
    summary = dict(cable=CABLE, r_ohm_per_km=float(T["r_ohm_per_km"]),
        x_ohm_per_km=float(T["x_ohm_per_km"]), c_nf_per_km=float(T["c_nf_per_km"]),
        max_i_ka=float(T["max_i_ka"]), circuit_rating_mva=S_CIRC, n_circuits=N_CIRC,
        farm_mw=FARM_MW,
        q_charge_50km=q_charging(50), q_charge_100km=q_charging(100), q_charge_200km=q_charging(200),
        q_charge_100km_pct_of_farm=100*q_charging(100)/FARM_MW,
        first_length_needing_compensation=int(df_min[df_min.min_comp_ratio.fillna(1) > 0].length_km.min()),
        max_feasible_length_km=int(feas.length_km.max()) if len(feas) else None,
        min_comp_100km=g(df_min,100,"min_comp_ratio"),
        q_comp_100km_mvar=g(df_min,100,"q_comp_mvar"),
        v_off_100km_uncomp=g(df_len,100,"unc_v_off"), v_off_100km_comp=g(df_min,100,"v_off"),
        losses_100km_uncomp_mw=g(df_len,100,"unc_losses"), losses_100km_comp_mw=g(df_min,100,"losses"),
        loading_100km_uncomp=g(df_len,100,"unc_loading"), loading_100km_comp=g(df_min,100,"loading"))
    json.dump(summary, open(OUT+"p02_summary.json","w"), indent=1)
    print(json.dumps(summary, indent=1), flush=True)
    print("\n", df_min[["length_km","min_comp_ratio","q_comp_mvar","v_off","loading","losses"]].to_string(index=False))

    fig, ax = plt.subplots(1, 3, figsize=(16, 4.4))
    ax[0].plot(df_len.length_km, df_len.q_charge_mvar, color="#4B7FA8", lw=2)
    ax[0].axhline(FARM_MW, ls="--", c="#C4714A", lw=1.2)
    ax[0].annotate(f"{FARM_MW:.0f} MW farm rating", (15, FARM_MW*1.04), fontsize=9, color="#C4714A")
    ax[0].set(xlabel="Cable length [km]", ylabel="Charging reactive power [Mvar]",
              title="Charging power scales with length")
    ax[1].plot(df_comp.comp_ratio*100, df_comp.v_off, color="#4A7C6F", lw=2)
    ax[1].axhline(V_MAX, ls="--", c="#C4714A", lw=1); ax[1].axhline(V_MIN, ls="--", c="#C4714A", lw=1)
    ax[1].set(xlabel="Compensation [% of charging Mvar]", ylabel="Offshore voltage [p.u.]",
              title=f"Voltage vs compensation, {L_REF} km")
    ax[2].plot(feas.length_km, feas.min_comp_ratio*100, "o-", color="#B89E7E", lw=2, ms=4)
    ax[2].set(xlabel="Cable length [km]", ylabel="Minimum compensation [%]",
              title="Compensation needed to hold the voltage band")
    for a in ax: a.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(OUT+"p02_results.png", dpi=160)
    print("\nfigures written", flush=True)
