"""Project 04: where does the price come from, and what is a battery worth?

Stage 1. Economic dispatch on the IEEE 118-bus generator cost data by lambda
         iteration. The multiplier on the energy balance constraint is the system
         marginal price. This is the LP/QP duality result in Kirschen and Strbac
         and in Bohn, Caramanis and Schweppe (1984), reproduced from published
         cost data rather than asserted.

Stage 2. Battery arbitrage against that price series, solved as a linear program.

The only assumed input is the shape of the daily demand profile, which is stated
explicitly below. Every conclusion is reported as a sensitivity so that no single
assumed number carries the result.
"""
import json
import numpy as np, pandas as pd
import pandapower.networks as pn
from scipy.optimize import linprog
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT, SEED = "/tmp/work/out/", 42
rng = np.random.default_rng(SEED)

# ---------------- generator cost data, from the published test case -------------
net = pn.case118()
pc = net.poly_cost[net.poly_cost.et == "gen"].set_index("element")
gen = net.gen.loc[pc.index]
A = pc.cp1_eur_per_mw.values.astype(float)          # linear term, EUR/MWh
B = pc.cp2_eur_per_mw2.values.astype(float)         # quadratic term, EUR/MWh^2
PMAX = gen.max_p_mw.values.astype(float)
PMIN = np.zeros_like(PMAX)
D_NOM = float(net.load.p_mw.sum())

def dispatch(demand):
    """Lambda iteration. Returns (price, output vector, total cost).

    For each unit, marginal cost is A + 2 B P, so at the optimum every dispatched
    unit runs where its marginal cost equals the system price lambda.
    """
    lo, hi = 0.0, float((A + 2 * B * PMAX).max()) + 1.0
    for _ in range(80):
        lam = 0.5 * (lo + hi)
        p = np.clip((lam - A) / (2 * B), PMIN, PMAX)
        if p.sum() < demand: lo = lam
        else: hi = lam
    lam = 0.5 * (lo + hi)
    p = np.clip((lam - A) / (2 * B), PMIN, PMAX)
    return lam, p, float((A * p + B * p ** 2).sum())

# check the duality result numerically
lam0, p0, _ = dispatch(D_NOM)
marg = A + 2 * B * p0
interior = (p0 > 1e-6) & (p0 < PMAX - 1e-6)
dual_err = float(np.abs(marg[interior] - lam0).max())
eps = 1.0
num_dl = (dispatch(D_NOM + eps)[2] - dispatch(D_NOM - eps)[2]) / (2 * eps)
print(f"price at nominal demand {D_NOM:.0f} MW: {lam0:.3f} EUR/MWh")
print(f"max |marginal cost - lambda| over dispatched units: {dual_err:.2e}")
print(f"numerical dCost/dDemand: {num_dl:.4f}  vs lambda {lam0:.4f}", flush=True)

# ---------------- price as a function of demand -------------------------------
levels = np.linspace(0.45, 1.25, 60) * D_NOM
curve = pd.DataFrame([dict(demand_mw=d, price=dispatch(d)[0]) for d in levels])

# ---------------- demand profile: THE assumption ------------------------------
# Two-peak daily shape, morning and evening, expressed as a fraction of nominal.
# Amplitude and day-to-day variation are stated here and swept later.
HOURS, DAYS = 24, 90
h = np.arange(HOURS)
shape = (0.78 + 0.13 * np.exp(-0.5 * ((h - 8) / 2.2) ** 2)
              + 0.22 * np.exp(-0.5 * ((h - 19) / 2.6) ** 2)
              - 0.06 * np.exp(-0.5 * ((h - 3) / 2.5) ** 2))

AMP = 2.5          # profile amplitude, chosen so demand exercises the merit order
def price_series(days=DAYS, amp=AMP, daily_sigma=0.05, hour_sigma=0.03, gen=None):
    g = gen or np.random.default_rng(SEED)
    m = shape.mean()
    prof = np.concatenate([(1 + g.normal(0, daily_sigma)) * (m + amp * (shape - m))
                           * (1 + g.normal(0, hour_sigma, HOURS))
                           for _ in range(days)])
    return np.array([dispatch(D_NOM * f)[0] for f in prof]), prof

prices, prof = price_series()
print(f"\nprice series {len(prices)} h  mean {prices.mean():.2f}  min {prices.min():.2f}  "
      f"max {prices.max():.2f}  std {prices.std():.2f} EUR/MWh", flush=True)

# ---------------- battery arbitrage LP ----------------------------------------
def arbitrage(pi, p_max, e_max, eta_c=0.92, eta_d=0.92, soc0=0.5, cyclic=True):
    """max sum pi_t (d_t - c_t)  s.t. SoC dynamics and limits. Vars: [c, d].

    cyclic=True forces the final state of charge back to the initial value. Without
    it a finite horizon lets the battery sell its starting energy and end empty,
    which inflates revenue and makes any day-by-day comparison meaningless.
    """
    T = len(pi)
    c = np.concatenate([pi, -pi])                       # linprog minimises
    # SoC_t = soc0*e_max + sum_{k<=t} (eta_c c_k - d_k/eta_d)   in [0, e_max]
    L = np.tril(np.ones((T, T)))
    Aub = np.vstack([np.hstack([ L * eta_c, -L / eta_d]),
                     np.hstack([-L * eta_c,  L / eta_d])])
    bub = np.concatenate([np.full(T, e_max * (1 - soc0)), np.full(T, e_max * soc0)])
    Aeq = beq = None
    if cyclic:
        Aeq = np.hstack([np.full(T, eta_c), np.full(T, -1.0 / eta_d)]).reshape(1, -1)
        beq = np.array([0.0])
    r = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq,
                bounds=[(0, p_max)] * (2 * T), method="highs")
    if not r.success: return None
    ch, di = r.x[:T], r.x[T:]
    soc = soc0 * e_max + np.cumsum(eta_c * ch - di / eta_d)
    return dict(revenue=float(pi @ (di - ch)), charge=ch, discharge=di, soc=soc,
                cycles=float(di.sum() / e_max))

P_MW = 50.0
runs = []
for dur in (1, 2, 4, 8):
    r = arbitrage(prices, P_MW, P_MW * dur)
    runs.append(dict(duration_h=dur, energy_mwh=P_MW * dur, revenue_eur=r["revenue"],
                     rev_per_mwh_installed=r["revenue"] / (P_MW * dur),
                     cycles=r["cycles"], annualised_eur=r["revenue"] * 365 / DAYS))
df_dur = pd.DataFrame(runs)
print("\nDURATION SCAN\n", df_dur.to_string(index=False), flush=True)

# Perfect foresight vs a naive persistence forecast.
# Both optimise one day at a time with a cyclic SoC, so the only difference is
# which price vector the schedule was built on.
def daily_backtest(pi, p_max, e_max, foresight=True):
    tot = 0.0
    for d in range(1, DAYS):
        today, yday = pi[d*24:(d+1)*24], pi[(d-1)*24:d*24]
        plan = arbitrage(today if foresight else yday, p_max, e_max)
        if plan: tot += float(today @ (plan["discharge"] - plan["charge"]))
    return tot

E4 = P_MW * 4
pf = daily_backtest(prices, P_MW, E4, foresight=True)
nv = daily_backtest(prices, P_MW, E4, foresight=False)
bias = 100 * (pf - nv) / pf if pf else float("nan")
print(f"\n4 h battery, {DAYS-1} days, daily cyclic dispatch:")
print(f"  perfect foresight {pf:,.0f} EUR   naive persistence {nv:,.0f} EUR   "
      f"foresight premium {bias:.1f}%", flush=True)

# Break even price ratio. Arbitrage only pays if the high/low ratio beats the
# round trip efficiency, so there is a spread below which revenue is exactly zero.
ETA = 0.92 * 0.92
print(f"\nround trip efficiency {ETA:.3f}  ->  break even price ratio {1/ETA:.3f}")
print(f"observed max/min price ratio {prices.max()/prices.min():.3f}", flush=True)

# volatility sensitivity
vol = []
for amp in (0.5, 0.75, 1.0, 1.5, 2.0):
    pr, _ = price_series(days=30, amp=amp)
    r = arbitrage(pr, P_MW, E4)
    vol.append(dict(amplitude=amp, price_std=float(pr.std()),
                    spread=float(pr.max() - pr.min()),
                    revenue_30d=r["revenue"], rev_per_mw=r["revenue"] / P_MW))
df_vol = pd.DataFrame(vol)
print("\nVOLATILITY SENSITIVITY\n", df_vol.to_string(index=False), flush=True)

curve.to_csv(OUT+"p04_price_vs_demand.csv", index=False)
df_dur.to_csv(OUT+"p04_duration.csv", index=False)
df_vol.to_csv(OUT+"p04_volatility.csv", index=False)
pd.DataFrame(dict(hour=np.arange(len(prices)), price=prices, demand_frac=prof)).to_csv(OUT+"p04_prices.csv", index=False)

S = dict(n_gen=int(len(gen)), total_capacity_mw=float(PMAX.sum()), nominal_demand_mw=D_NOM,
    price_at_nominal=round(float(lam0), 3), duality_max_error=float(dual_err),
    numerical_dcost_ddemand=round(float(num_dl), 4),
    hours=int(len(prices)), price_mean=round(float(prices.mean()), 2),
    price_min=round(float(prices.min()), 2), price_max=round(float(prices.max()), 2),
    price_std=round(float(prices.std()), 2),
    best_duration_h=int(df_dur.loc[df_dur.rev_per_mwh_installed.idxmax(), "duration_h"]),
    revenue_4h_90d=round(float(df_dur[df_dur.duration_h==4].revenue_eur.iloc[0]), 0),
    annualised_4h=round(float(df_dur[df_dur.duration_h==4].annualised_eur.iloc[0]), 0),
    perfect_foresight_eur=round(pf, 0), naive_forecast_eur=round(nv, 0),
    foresight_bias_pct=round(float(bias), 1),
    break_even_price_ratio=round(1/ETA, 4),
    observed_price_ratio=round(float(prices.max()/prices.min()), 4),
    zero_revenue_below_amplitude=float(df_vol[df_vol.revenue_30d <= 0].amplitude.max())
        if (df_vol.revenue_30d <= 0).any() else None,
    revenue_at_amp2_per_mw=round(float(df_vol[df_vol.amplitude==2.0].rev_per_mw.iloc[0]), 1))
json.dump(S, open(OUT+"p04_summary.json","w"), indent=1)
print("\n", json.dumps(S, indent=1), flush=True)

fig, ax = plt.subplots(1, 3, figsize=(16.5, 4.5))
ax[0].plot(curve.demand_mw/1000, curve.price, color="#4A7C6F", lw=2)
ax[0].axvline(D_NOM/1000, ls="--", c="#9B948C", lw=1)
ax[0].annotate("nominal demand", (D_NOM/1000*1.01, curve.price.min()*1.05), fontsize=8, color="#5C5650")
ax[0].set(xlabel="System demand [GW]", ylabel="Marginal price [EUR/MWh]",
          title="Price is the dual of the balance constraint")
d0 = slice(0, 72)
ax[1].plot(prices[d0], color="#4B7FA8", lw=1.6)
ax[1].set(xlabel="Hour", ylabel="Price [EUR/MWh]", title="First three days of the price series")
ax[2].bar(df_dur.duration_h.astype(str), df_dur.rev_per_mwh_installed, color="#B89E7E")
ax[2].set(xlabel="Battery duration [h]", ylabel="Revenue per MWh installed [EUR]",
          title=f"Shorter duration earns more per MWh ({DAYS} days)")
for a in ax: a.grid(alpha=.3)
plt.tight_layout(); plt.savefig(OUT+"p04_results.png", dpi=160)
print("figures written", flush=True)
