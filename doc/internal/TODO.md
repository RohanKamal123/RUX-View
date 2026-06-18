# TODO — Comprehensive AI Performance Runner

- [ ] Update `test_ai_performance.py` to fully cover all AI client modalities (including `analyse_frame_with_second_pass`).
- [ ] Fix/replace fragile argument mapping in text tests with explicit kwargs per function.
- [ ] Harden rate-limiting verification (reduce network/timing flakiness).
- [ ] Improve JSON reporting (timestamps, success/duration, rate-limited inference, per-call metadata).
- [ ] Save partial JSON after each major section.
- [ ] Run `python test_ai_performance.py` in ACT mode and confirm `ai_performance_results.json` output.

