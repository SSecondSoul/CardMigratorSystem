# formal_30_v2 manual-validation freeze

This directory is an evidence-only snapshot of the completed formal_30_v2
manual-validation and targeted-repair layer.

Scope: 14 registered samples, all manually passed. This is not a new automatic
run of all 30 formal_30_v1 samples and must not be reported as a 30-sample
automatic pass rate.

The snapshot contains the exact final San artifact for every registered sample,
the corresponding pre-repair or unchanged baseline San artifact, Vue source,
manual report, available experiment notebooks, the manual test runners, and
parent formal_30_v1 evidence references.

Verify integrity from the repository root with:

    python <snapshot-directory>/verify_snapshot.py

Do not edit this snapshot. Any later repair or reinterpretation requires a new
version and a new snapshot directory.
