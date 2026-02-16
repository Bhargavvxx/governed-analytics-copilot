# Semantic Layer

This directory holds the **single source of truth** for all approved metrics,
dimensions, join paths, and security rules.

The file `semantic_model.yml` is loaded at runtime by `src/governance/semantic_loader.py`.
All generated SQL must conform to the definitions here.

See `docs/data_dictionary.md` for a human-readable description of every metric.
