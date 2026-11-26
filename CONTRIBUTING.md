# Contributing to ArchiCord 🤝

Bug fixes, documentation improvements, tests and well-scoped Universal Tracker diagnostics are welcome.

1. Fork the repository and create a descriptive working branch.
2. **Never commit** `.env`, private YAMLs, APWorld archives, seed ZIPs, spoiler files or bot runtime data.
3. Install development requirements and run the tests:

   ```bash
   python -m pip install -r requirements-dev.txt
   python -m pytest -q
   ```

4. Submit a pull request describing the change, user-facing behavior, and the tests you ran.

**Compatibility is important.** Preserve Discord commands, DeathLink milestones, hint behavior, stored seed state and existing configuration keys unless an intentional breaking change is clearly documented.

When changing the Universal Tracker bridge, distinguish harmless launcher diagnostics, unknown locations, and actual YAML/world-logic failures. **Never invent doable checks** from missing-location lists or uncertain output. Do not claim Windows/Discord/Archipelago integration was verified unless it was actually tested.
