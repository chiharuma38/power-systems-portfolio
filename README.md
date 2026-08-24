# Power Systems Engineering Portfolio

Five open source studies in power system analysis, markets and optimisation.

Every project runs on publicly available benchmark networks and data that ships with
the libraries. No commercial software licences, no API keys, no downloads. Anyone can
clone this repository and reproduce every number in it.

Live status for each project is in [`progress.json`](./progress.json), which also drives
the badges on the portfolio site.

---

## Projects

| # | Project | Question it answers | Key result |
|---|---------|--------------------|------------|
| [01](./01_n1_contingency/) | N-1 Contingency Screening and Wind Integration | How does wind penetration change N-1 security? | Line 26 critical at 157.5% loading, violations fall 77% at 80% wind |
| [02](./02_offshore_wind/) | HVAC Export Cable for an Offshore Wind Farm | How much reactive compensation, and where does AC stop working? | Feasible to 160 km, 109 Mvar charging at 100 km |
| [03](./03_fault_detection/) | Detecting Line Outages from Bus Measurements | Can a classifier find a tripped line, and does it survive noise? | 0.962 clean, chance level at 0.5% noise |
| [04](./04_storage_optimizer/) | Where the Price Comes From, and What a Battery Is Worth | Is the price really the dual, and what is storage worth? | Duality verified exactly, zero revenue below a 1.181 price ratio |
| [05](./05_contingency_toolkit/) | A Parallel N-1 Contingency Screening Toolkit | How much does parallelism actually buy? | 2.85x on 4 cores, results verified identical |

Each folder has a README stating the question, the method, the measured results, and an
explicit limitations section. Where a modelling assumption drives a result, it is named
in the README rather than buried in the notebook.

---

## What these are for

These are learning projects. They exist to work through power system analysis, electricity
market theory, optimisation and machine learning by building things rather than reading
about them, and to leave behind something reproducible.

Three of the five have a negative or counterintuitive headline result, which is deliberate.
Project 03 finds that classifiers which look excellent on clean simulated data collapse to
chance under realistic measurement noise. Project 04 finds that battery arbitrage revenue is
exactly zero below a threshold price spread, not merely small. Project 05 finds sub-linear
parallel scaling and explains the gap. Those were more useful to me than the positive results.

---

## Data sources

| Source | Used in | Licence |
|---|---|---|
| IEEE 39-bus New England test case (Athay et al., 1979) via pandapower | 01, 03 | open benchmark |
| IEEE 118-bus test case (Christie, 1993, University of Washington) via pandapower | 04, 05 | open benchmark |
| pandapower standard line types, traced to Heuck et al. (2013) | 02 | ships with pandapower |

Full citations are in each project README.

---

## Setup

```bash
git clone https://github.com/chiharuma38/power-systems-portfolio.git
cd power-systems-portfolio
pip install -r requirements.txt
jupyter notebook
```

**Python 3.11.** pandapower 2.14.1 requires numpy below 2 and pandas below 2.2, so those
three versions are pinned together in `requirements.txt`. Changing one alone breaks the import.

---

## Progress tracking

`progress.json` is the single source of truth for project status. After editing it:

```bash
python3 sync_progress.py
```

This validates the file and propagates it to the portfolio site. See [`UPDATING.md`](./UPDATING.md).

---

## Portfolio site

[chiharuma38.github.io](https://chiharuma38.github.io)

---

## Licence

MIT, free to use with attribution.
