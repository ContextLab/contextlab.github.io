# Quickstart: People & Lab-Manual Synchronization

## Prerequisites

- Python 3.9+
- `pip install -r requirements-build.txt`
- Git submodule initialized: `git submodule update --init`
- Push access to both ContextLab/contextlab.github.io and ContextLab/lab-manual

## One-Time Setup

```bash
# Add lab-manual as submodule (if not already done)
git submodule add https://github.com/ContextLab/lab-manual.git lab-manual

# Initialize submodule
git submodule update --init
```

## Reconcile All Sources

```bash
# Run reconciliation (report only, no changes)
cd scripts && python reconcile_people.py --dry-run

# Run reconciliation and apply auto-fixes
cd scripts && python reconcile_people.py

# After reconciliation, rebuild the people page
cd scripts && python build.py
```

## Onboard a New Member (All Destinations)

```bash
cd scripts
python onboard_member.py "First Last" --rank "grad student"
# This now updates: people.xlsx + JRM_CV.tex + lab_manual.tex
```

## Offboard a Member (All Destinations)

```bash
cd scripts
python offboard_member.py "member name" --end-year 2026
# This now updates: people.xlsx + JRM_CV.tex + lab_manual.tex
```

## Verify Sync Status

```bash
# Check for discrepancies without making changes
cd scripts && python reconcile_people.py --dry-run

# Run full test suite
python -m pytest tests/ -v
```
