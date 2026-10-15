"""
Your defense. Implement register(ctx) and a handler per event type.
See ../README.md for the full interface + toolkit reference, and
../RULES.md before you start.
"""
import sys
from api import Verdict


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def check_data_batch(payload, ctx):
    profile = ctx.tools.batch_profile(payload["batch_id"])
    b = ctx.baseline
    if "error" in profile:
        return Verdict(alert=False, pillar="checks")

    alert = False
    row_count = profile.get("row_count", 0)
    if row_count < b.get("row_count_min", 0) or row_count > b.get("row_count_max", 1e12):
        alert = True

    null_rate_dict = profile.get("null_rate", {})
    if isinstance(null_rate_dict, dict):
        for col, val in null_rate_dict.items():
            if val is not None and val > b.get("null_rate_max", 1.0):
                alert = True

    mean_amt = profile.get("mean_amount", 0)
    if mean_amt < b.get("mean_amount_min", -1e12) or mean_amt > b.get("mean_amount_max", 1e12):
        alert = True

    staleness = profile.get("staleness_min", 0)
    if staleness > b.get("staleness_min_max", 1e12):
        alert = True

    return Verdict(alert=alert, pillar="checks")


def check_contract_checkpoint(payload, ctx):
    diff = ctx.tools.contract_diff(payload["contract_id"], payload["checkpoint_batch_id"])
    b = ctx.baseline
    if "error" in diff:
        return Verdict(alert=False, pillar="contracts")

    alert = (
        diff.get("freshness_delay_min", 0) > b.get("freshness_delay_max_min", 1e12)
        or bool(diff.get("violations"))
    )
    return Verdict(alert=alert, pillar="contracts")


def check_lineage_run(payload, ctx):
    slice_ = ctx.tools.lineage_graph_slice(payload["run_id"])
    b = ctx.baseline
    if "error" in slice_:
        return Verdict(alert=False, pillar="lineage")

    alert = False
    # Runtime anomaly
    if slice_.get("duration_ms", 0) > b.get("lineage_duration_ms_max", 1e12):
        alert = True

    # Orphan output anomaly (no downstream consumers)
    actual_downstream = slice_.get("actual_downstream_count", 0)
    if actual_downstream == 0:
        alert = True

    # Missing upstream anomaly
    job = payload.get("job", "default")
    known_upstreams = ctx.state.setdefault("known_upstreams", {})
    actual_upstream = set(slice_.get("actual_upstream") or [])

    if job in known_upstreams:
        if actual_upstream < known_upstreams[job]:
            alert = True
        elif len(actual_upstream) > len(known_upstreams[job]):
            known_upstreams[job] = actual_upstream
    else:
        known_upstreams[job] = actual_upstream

    return Verdict(alert=alert, pillar="lineage")


def check_feature_materialization(payload, ctx):
    drift = ctx.tools.feature_drift(payload["feature_view"], payload["batch_id"])
    b = ctx.baseline
    if "error" in drift:
        return Verdict(alert=False, pillar="ai_infra")

    alert = drift.get("mean_shift_sigma", 0) > b.get("feature_mean_shift_sigma_max", 1e12)
    return Verdict(alert=alert, pillar="ai_infra")


def check_embedding_batch(payload, ctx):
    drift = ctx.tools.embedding_drift(payload["corpus"], payload["chunk_batch_id"])
    b = ctx.baseline
    if "error" in drift:
        return Verdict(alert=False, pillar="ai_infra")

    alert = (
        drift.get("centroid_shift", 0) > b.get("embedding_centroid_shift_max", 1e12)
        or drift.get("avg_doc_age_days", 0) > b.get("corpus_avg_doc_age_days_max", 1e12)
    )
    return Verdict(alert=alert, pillar="ai_infra")

