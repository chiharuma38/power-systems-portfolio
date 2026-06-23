cat > README.md << 'EOF'
# Power Systems Engineering Portfolio
**Chiharu Mamiya** — Power Systems Engineer | KTH SENSE MSc (Aug 2025)

[LinkedIn](https://linkedin.com/in/chiharumamiya) · Built with pandapower, PyPSA, scikit-learn · All data publicly available

---

## About

Power systems engineer with hands-on PSS®E and TSAT automation experience from GE Vernova and Siemens. This portfolio replicates real transmission planning workflows using open-source tools and publicly available benchmark networks — no commercial licenses required.

**Professional context:** At Siemens I automated PSS®E contingency analysis workflows in Python, reducing runtime by 70%. At GE Vernova I performed short-circuit and load flow studies in PowerFactory for utility clients. These projects demonstrate the same engineering methodology using pandapower and PyPSA.

---

## Projects

| # | Project | Tools | Data | Key Result |
|---|---------|-------|------|------------|
| [01](./01_n1_contingency/) | N-1 Contingency Screening + Wind Integration | pandapower, matplotlib | IEEE 39-bus (built-in) | Line 26 most critical at 157.5% loading; violations drop 71% with higher wind |
| [02](./02_offshore_wind/) | Offshore Wind Farm Grid Integration | PyPSA | ENTSO-E real DK1 wind data | Coming soon |
| [03](./03_fault_detection/) | ML-Based Grid Fault Detection | pandapower, scikit-learn | Synthetic (pandapower) | Coming soon |
| [04](./04_storage_optimizer/) | Battery Storage Dispatch Optimizer | scipy | ENTSO-E prices + wind | Coming soon |
| [05](./05_psse_case_study/) | PSS/E Automation Case Study | Python OOP, pandapower | IEEE 118-bus (built-in) | Coming soon |

---

## Quick Start

```bash
git clone https://github.com/chiharumamiya/power-systems-portfolio.git
cd power-systems-portfolio
pip install -r requirements.txt
jupyter notebook
```

All projects run without commercial software licenses.

---

## Technical Stack

`pandapower` `PyPSA` `scikit-learn` `scipy` `Python 3.11` `pandas` `matplotlib` `plotly` `numpy` `Jupyter`

---

## Engineering Background

- **GE Vernova** — Grid Solutions Graduate Engineer (2025): PowerFactory + PSS®E studies for utilities
- **Siemens** — Grid Software Power Systems Consultant (2025): PSS®E and TSAT Python automation, 70–94% runtime reduction
- **KTH Royal Institute of Technology** — MSc SENSE incoming August 2025: offshore wind, HVDC, smart grid
EOF