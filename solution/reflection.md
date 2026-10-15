# Reflection (≤1 page)

### 1. Which fault types were hardest to catch, and why?

Across the simulation phases, the hardest faults to detect fell into two categories:

1. **Subtle-Magnitude Distribution & Infrastructure Shifts (`checks` and `ai_infra`):**
   - In `data_batch` events, extreme spikes in null rate or drastic volume drops were straightforward to identify against static ±3σ boundaries. However, subtle magnitude shifts (such as minor transaction amount deviations or slight staleness increases that hover right around normal variance) are notoriously difficult to distinguish from clean organic pipeline fluctuations.
   - For `feature_materialization` and `embedding_batch` events, drift metrics (`mean_shift_sigma` and `centroid_shift`) frequently sit near normal variance in the private phase. Setting thresholds too conservatively risks missing these subtle drifts (increasing false negatives), while setting thresholds too aggressively rapidly spikes the False Positive Rate (FPR), which is heavily penalized in the objective score (`-0.3 · FPR`).

2. **Graph-Contextual Lineage Anomalies (`lineage`):**
   - Unlike runtime anomalies (`duration_ms` exceeding baseline bounds) or orphan outputs (`actual_downstream_count == 0`), detecting `missing_upstream` dependencies required maintaining running contextual state across executions (`ctx.state["known_upstreams"]`).
   - Because events arrive as an online, single-pass stream, the system cannot verify a complete ground-truth topology beforehand; it must dynamically establish and update the baseline upstream graph for each transform job, making the first occurrence of a job vulnerable to missing contextual edges.

---

### 2. What would you change about your cost/coverage tradeoff, if you had another pass?

1. **Multi-Signal Anomaly Scoring over Hard Cutoffs:**
   - Instead of binary threshold gates for each individual metric, I would implement an adaptive, composite anomaly score (e.g., Mahalanobis distance or normalized z-score summation across volume, null rate, and amount distribution). This would catch correlated subtle shifts where no single metric independently breaches its 3σ ceiling.

2. **Dynamic Sampling & Budget-Aware Multi-Tier Verification:**
   - Currently, each event triggers a single metered tool call costing 1.0 to 2.0 credits, which fits cleanly within the ~300 credit consumption on private's 320 budget.
   - With another pass, I would design a tiered probing strategy: run cheap lightweight diagnostics first, and only dispatch expensive checks (such as full 2.0-credit `feature_drift` / `embedding_drift` profiling) when upstream schema checks or volume changes hint at higher fault probability, or when `ctx.tools.budget_remaining()` allows.

3. **Cumulative Windowing for Drift Detection:**
   - Rather than judging feature and embedding drift on isolated single batches, maintaining an online exponential moving average (EMA) of drift statistics within `ctx.state` would allow detecting persistent low-magnitude drift over time with near-zero false alarms.

