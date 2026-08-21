# ShiftFlow Eval Harness

This harness checks whether the scheduling demo behaves like a reliable restaurant scheduling assistant.

The first version is deterministic and does not call an LLM. It validates business rules and data-grounding basics:

- demo data has enough stores, staff, and open shifts;
- unknown stores are not treated as real matches;
- open shifts really have staffing gaps;
- staff skills are structured;
- overtime candidates are blocked;
- role-mismatch candidates are excluded from recommendations.

## Run Locally

```bash
cd python-backend
python3.11 -m evals.shiftflow_harness
```

Expected output:

```text
ShiftFlow Harness: 6/6 passed
```

## Why This Matters

For ShiftFlow, the key product question is not only "can the assistant answer?".
It is "can we prove the assistant respects scheduling rules before a store manager trusts it?".

This harness is the first step toward that proof.
