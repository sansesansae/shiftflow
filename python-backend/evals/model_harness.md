# ShiftFlow Model Harness

This harness is a smoke test for labor-hour forecasting. It is intentionally small,
deterministic, and dependency-free so it can run before every deploy.

## What It Checks

- The model uses a time-based train/test split.
- Training data dates are earlier than test data dates.
- Predictions are non-negative.
- MAE, MAPE, and badcase rate stay under committed thresholds.
- Re-running the same fixture produces the same prediction signature.

## Current Model

The current implementation uses a simple baseline:

```text
predicted labor hours = mean historical labor hours for the same hour and role
```

Then it applies small explainable adjustments for weekend, holiday, promotion, and
rain. This keeps the first harness easy to reason about.

## Why Not LightGBM Yet

LightGBM should be added after the harness is stable. The harness contract should
stay the same when the model changes:

```text
metrics fixture -> train/evaluate -> MAE/MAPE/badcase/reproducibility checks
```

When LightGBM is introduced, keep deterministic settings such as fixed seed,
CPU mode, and deterministic column handling.
