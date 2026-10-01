"""Aggregate latest real snapshots without inventing unavailable metrics."""
def with_social_metrics(result, campaign):
    snapshots = [metric for asset in campaign.get("assets", []) for metric in asset.get("social_metrics", {}).values()]
    if not snapshots:
        result["metrics_source"] = "simulated" if result["is_demo"] else "manual_import" if any(e.get("metrics_source") == "manual_import" for e in campaign.get("experiments", [])) else "none"
        return result
    keys = ("impressions", "clicks", "conversions", "likes", "comments", "reposts")
    rows = {p: {"platform": p, **{k: 0 for k in keys}, "availability": {k: True for k in keys}} for p in campaign["platforms"]}
    synced_assets = {a["id"] for a in campaign["assets"] if a.get("social_metrics")}
    assets = {a["id"]: a for a in campaign["assets"]}
    manual = False
    for experiment in campaign.get("experiments", []):
        # Never add manual observations of a synced asset to its API totals again.
        if experiment["asset_id"] in synced_assets or experiment["is_demo"] or experiment.get("metrics_source") != "manual_import":
            continue
        manual = True
        row = rows[assets[experiment["asset_id"]]["platform"]]
        for variant in experiment["variants"]:
            for key in ("impressions", "clicks", "conversions"):
                row[key] += variant[key]
    for metric in snapshots:
        row = rows.setdefault(metric["platform"], {"platform": metric["platform"], **{k: 0 for k in keys}, "availability": {k: True for k in keys}})
        for key in keys:
            value = metric.get(key)
            if value is None:
                row["availability"][key] = False
            else:
                row[key] += value
    availability = {key: all(row["availability"][key] for row in rows.values()) for key in keys}
    result.update({key: sum(row[key] for row in rows.values()) for key in keys})
    result.update(is_demo=False, metrics_source="mixed" if manual else "social_api", platforms=list(rows.values()),
                  availability=availability, ctr=result["clicks"] / result["impressions"] if availability["clicks"] and availability["impressions"] and result["impressions"] else 0,
                  social_snapshots=snapshots, sync=campaign.get("social_sync"),
                  observations=["Latest cumulative social API snapshots are linked to published asset versions; refresh replaces totals rather than adding snapshots.",
                                "Unavailable metrics remain unknown. Social post APIs do not establish campaign conversions or causal lift.",
                                "Manual experiment totals for assets with API snapshots are excluded to avoid counting the same publication twice."])
    return result
