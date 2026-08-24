# Project 1: N-1 Contingency Screening + Wind Integration

**Tools:** pandapower · Python · matplotlib  
**Data:** IEEE 39-bus New England test network (built into pandapower)  
**Notebook:** [Project1.ipynb](./Project1.ipynb)

---

## What this does

Automated N-1 contingency analysis on the IEEE 39-bus benchmark transmission network. For each of the 35 transmission lines: removes it from service, re-solves AC power flow using Newton-Raphson, checks thermal and voltage violations, restores it.

Extended across five wind generation levels (20% to 100%) to study how renewable penetration affects grid reliability under single-element contingency stress.

This is the same methodology required by NERC TPL-001 for transmission planning studies at PJM, MISO, and CAISO.

---

## Results

| Metric | Value |
|--------|-------|
| Contingencies tested | 35 |
| Most critical line | Line 26 at 157.5% loading |
| Violations at 20% wind | 35 / 35 |
| Violations at 80% wind | 8 / 35 |
| Reduction | 77% |

**Key finding:** Violations drop sharply as wind penetration increases from 20% to 80%, then tick back up slightly at 100%. The uptick reflects a real phenomenon in high-renewable grids: power flow patterns shift at very high wind penetration, creating new stress points on lines that were previously lightly loaded.

---

## Files

```
01_n1_contingency/
├── Project1.ipynb        # Main analysis notebook
└── results/
    ├── n1_results.csv    # Full contingency results table
    ├── wind_scenario.csv # Violation counts by wind level
    ├── n1_results.png    # Contingency severity chart
    └── wind_scenario.png # Wind penetration vs violations chart
```

---

## How to run

```bash
pip install pandapower==2.14.1 "numpy==1.26.4" "pandas==2.1.4" matplotlib
jupyter notebook Project1.ipynb
```

---

## Full documentation

[chiharuma38.github.io/projects/n1_contingency.html](https://chiharuma38.github.io/projects/n1_contingency.html)
