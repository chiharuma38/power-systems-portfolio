"""Project 03, stage 2.

Two feature sets are compared on purpose:

  SET B, all 113 measurements including line active power flows. An out of service
         line reports no flow, so the feature vector contains a direct pointer to
         the faulted element. Any classifier scores near perfectly. This is
         target leakage, and it is included to show what it looks like.

  SET A, bus voltage magnitudes and angles only, 78 features. The outage has to be
         inferred from its signature on the rest of the network. This is the
         honest problem and every headline number comes from it.
"""
import json
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, confusion_matrix)

OUT, SEED, N_BUS = "/tmp/work/out/", 42, 39
d = np.load(OUT + "p03_dataset.npz")
X_all = np.nan_to_num(d["X"], nan=0.0)          # de-energised line reports zero flow
y, yloc = d["y_bin"], d["y_loc"]
X_v = X_all[:, :2 * N_BUS]                       # voltages + angles only
print(f"samples {len(X_all)}  normal {(y==0).sum()}  fault {(y==1).sum()}")
print(f"SET A {X_v.shape[1]} features   SET B {X_all.shape[1]} features", flush=True)

def split(X):
    return train_test_split(X, y, yloc, test_size=0.3, random_state=SEED, stratify=y)

Xtr, Xte, ytr, yte, ltr, lte = split(X_v)
Btr, Bte, _, _, _, _ = split(X_all)

def sc(yt, yp):
    return dict(accuracy=accuracy_score(yt, yp),
                precision=precision_score(yt, yp, zero_division=0),
                recall=recall_score(yt, yp, zero_division=0),
                f1=f1_score(yt, yp, zero_division=0))

# ---------- 1. BASELINE, measured before any classifier ----------
# Statistical rule: flag a fault when any bus voltage deviates more than k standard
# deviations from the healthy-case profile learned on the training normal samples.
mu = Xtr[ytr == 0][:, :N_BUS].mean(axis=0)
sd = Xtr[ytr == 0][:, :N_BUS].std(axis=0) + 1e-9

def zrule(Xm, k):
    return (np.abs((Xm[:, :N_BUS] - mu) / sd).max(axis=1) > k).astype(int)

ks = [2, 3, 4, 5, 6, 8]
df_base = pd.DataFrame([dict(k=k, **sc(ytr, zrule(Xtr, k))) for k in ks])
best_k = float(df_base.loc[df_base.accuracy.idxmax(), "k"])       # tuned on TRAIN only
baseline = sc(yte, zrule(Xte, best_k))
print(f"\nBASELINE z-rule, k tuned on train = {best_k}")
print(df_base.to_string(index=False))
print("baseline on test:", {k: round(v, 4) for k, v in baseline.items()}, flush=True)

# ---------- 2. detection ----------
def mk(kind):
    m = (RandomForestClassifier(n_estimators=300, random_state=SEED, n_jobs=-1)
         if kind == "rf" else SVC(kernel="rbf", C=10, gamma="scale", random_state=SEED))
    return Pipeline([("sc", StandardScaler()), ("m", m)])

rows = [dict(model="Baseline z-rule (Set A)", features=X_v.shape[1], cv_mean=np.nan, cv_std=np.nan, **baseline)]
fitted = {}
for name, kind in (("RandomForest", "rf"), ("SVM_rbf", "svm")):
    p = mk(kind)
    cv = cross_val_score(p, Xtr, ytr, cv=StratifiedKFold(5, shuffle=True, random_state=SEED), n_jobs=-1)
    p.fit(Xtr, ytr); fitted[name] = p
    rows.append(dict(model=f"{name} (Set A)", features=X_v.shape[1],
                     cv_mean=cv.mean(), cv_std=cv.std(), **sc(yte, p.predict(Xte))))
leak = mk("rf"); leak.fit(Btr, ytr)
rows.append(dict(model="RandomForest (Set B, LEAKY)", features=X_all.shape[1],
                 cv_mean=np.nan, cv_std=np.nan, **sc(yte, leak.predict(Bte))))
df_det = pd.DataFrame(rows)
print("\nDETECTION\n", df_det.to_string(index=False), flush=True)

# ---------- 3. location ----------
mtr, mte = ltr >= 0, lte >= 0
locA = mk("rf"); locA.fit(Xtr[mtr], ltr[mtr])
pA = locA.predict(Xte[mte]); accA = accuracy_score(lte[mte], pA)
prob = locA.predict_proba(Xte[mte])
top3 = float(np.mean([lte[mte][i] in locA.classes_[np.argsort(p)[-3:]] for i, p in enumerate(prob)]))
locB = mk("rf"); locB.fit(Btr[mtr], ltr[mtr])
accB = accuracy_score(lte[mte], locB.predict(Bte[mte]))
n_cls = int(len(np.unique(ltr[mtr])))
print(f"\nLOCATION {n_cls} classes | Set A top-1 {accA:.4f} top-3 {top3:.4f} | Set B (leaky) {accB:.4f}", flush=True)

# ---------- 4. noise sensitivity ----------
rng = np.random.default_rng(SEED)
scale = np.abs(Xte).mean(axis=0)
rows = []
for nl in [0.0, 0.001, 0.005, 0.01, 0.02, 0.05]:
    Xn = Xte + rng.normal(0, nl * scale, Xte.shape)
    r = dict(noise_pct=nl * 100, baseline=accuracy_score(yte, zrule(Xn, best_k)))
    for n, m in fitted.items():
        r[n] = accuracy_score(yte, m.predict(Xn))
    r["location"] = accuracy_score(lte[mte], locA.predict(Xn[mte]))
    rows.append(r)
df_noise = pd.DataFrame(rows)
print("\nNOISE\n", df_noise.to_string(index=False), flush=True)

for df, n in ((df_base, "baseline"), (df_det, "detection"), (df_noise, "noise")):
    df.to_csv(OUT + f"p03_{n}.csv", index=False)

rf = df_det[df_det.model == "RandomForest (Set A)"].iloc[0]
S = dict(n_samples=int(len(X_all)), n_normal=int((y == 0).sum()), n_fault=int((y == 1).sum()),
    n_features_setA=int(X_v.shape[1]), n_features_setB=int(X_all.shape[1]),
    n_test=int(len(yte)), n_location_classes=n_cls, baseline_k=best_k,
    baseline_accuracy=round(float(baseline["accuracy"]), 4),
    baseline_recall=round(float(baseline["recall"]), 4),
    rf_accuracy=round(float(rf.accuracy), 4), rf_cv_mean=round(float(rf.cv_mean), 4),
    rf_cv_std=round(float(rf.cv_std), 4),
    svm_accuracy=round(float(df_det[df_det.model == "SVM_rbf (Set A)"].iloc[0].accuracy), 4),
    leaky_accuracy=round(float(df_det[df_det.model.str.contains("LEAKY")].iloc[0].accuracy), 4),
    location_top1=round(float(accA), 4), location_top3=round(top3, 4),
    location_top1_leaky=round(float(accB), 4),
    rf_at_1pct_noise=round(float(df_noise[df_noise.noise_pct == 1.0].RandomForest.iloc[0]), 4),
    rf_at_5pct_noise=round(float(df_noise[df_noise.noise_pct == 5.0].RandomForest.iloc[0]), 4),
    location_at_1pct_noise=round(float(df_noise[df_noise.noise_pct == 1.0].location.iloc[0]), 4),
    gain_over_baseline_pp=round(100 * float(rf.accuracy - baseline["accuracy"]), 2))
json.dump(S, open(OUT + "p03_summary.json", "w"), indent=1)
print("\n", json.dumps(S, indent=1), flush=True)

fig, ax = plt.subplots(1, 3, figsize=(16.5, 4.5))
b = df_det.set_index("model")["accuracy"]
ax[0].barh(range(len(b)), b.values, color=["#B89E7E", "#4A7C6F", "#4B7FA8", "#C4714A"])
ax[0].set_yticks(range(len(b)))
ax[0].set_yticklabels([m.replace(" (", "\n(") for m in b.index], fontsize=8)
ax[0].set(xlim=(0.4, 1.05), xlabel="Test accuracy", title="Detection, and what leakage looks like")
for i, v in enumerate(b.values): ax[0].text(v + .01, i, f"{v:.3f}", va="center", fontsize=8)
for c, col, lab in (("baseline", "#B89E7E", "z-rule baseline"), ("RandomForest", "#4A7C6F", "Random forest"),
                    ("SVM_rbf", "#4B7FA8", "SVM (RBF)"), ("location", "#C4714A", "Location, top-1")):
    ax[1].plot(df_noise.noise_pct, df_noise[c], "o-", color=col, lw=2, ms=4, label=lab)
ax[1].set(xlabel="Measurement noise [% of mean]", ylabel="Accuracy", title="Degradation with noise")
ax[1].legend(fontsize=8)
cm = confusion_matrix(lte[mte], pA, labels=locA.classes_)
im = ax[2].imshow(cm, cmap="YlOrBr")
ax[2].set(xlabel="Predicted line", ylabel="True line", title=f"Location confusion, Set A, top-1 {accA:.2f}")
plt.colorbar(im, ax=ax[2], fraction=.046)
for a in ax[:2]: a.grid(alpha=.3)
plt.tight_layout(); plt.savefig(OUT + "p03_results.png", dpi=160)
print("figures written", flush=True)
