# USIF Property System

USIF separates structure-level properties (`energy`, `stress`, `volume`, `pressure`, `temperature`, and `custom`) from atom-level properties (`force`, `charge`, `magmom`, `velocity`, and `custom`). Per-atom properties require full-atom storage. `force_symmetric=True` rejects per-atom properties by default unless `drop_atomic_properties=True` or `fallback_full_atomic=True` is explicitly provided.
