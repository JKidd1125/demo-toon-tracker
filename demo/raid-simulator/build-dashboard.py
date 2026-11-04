import json
from pathlib import Path

datasource = {
    "type": "prometheus",
    "uid": "${DS_PROMETHEUS}",
}
app = 'namespace="raid-demo",job="raid-simulator"'
deployment = 'namespace="raid-demo",deployment="raid-simulator"'
hpa = 'namespace="raid-demo",horizontalpodautoscaler="raid-simulator"'

ready = f'max(kube_deployment_status_replicas_available{{{deployment}}})'
traffic = f'sum(rate(raid_requests_total{{{app}}}[30s]))'
errors = f'sum(rate(raid_requests_total{{{app},status="500"}}[30s]))'
desired = f'max(kube_horizontalpodautoscaler_status_desired_replicas{{{hpa}}})'

cpu = (
    '1000 * sum by (pod) (rate(container_cpu_usage_seconds_total{'
    'namespace="raid-demo",container="simulator",'
    'job="kubelet",metrics_path="/metrics/cadvisor"}[1m]))'
)

latency = (
    'histogram_quantile(0.95, sum by (le) (rate('
    f'raid_request_duration_seconds_bucket{{{app}}}[30s])))'
)

panels = []


def panel(title, kind, x, y, w, h, unit, queries, description):
    targets = []
    for index, (expression, legend) in enumerate(queries):
        targets.append({
            "refId": chr(65 + index),
            "expr": expression,
            "legendFormat": legend,
            "datasource": datasource,
            "instant": kind == "stat",
            "range": kind != "stat",
        })

    defaults = {
        "unit": unit,
        "min": 0,
        "color": {"mode": "palette-classic"},
        "thresholds": {
            "mode": "absolute",
            "steps": [{"color": "green", "value": None}],
        },
    }

    if kind == "timeseries":
        defaults["custom"] = {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 2,
            "fillOpacity": 10,
            "showPoints": "never",
            "spanNulls": False,
        }
        options = {
            "legend": {"displayMode": "list", "placement": "bottom"},
            "tooltip": {"mode": "multi"},
        }
    else:
        options = {
            "reduceOptions": {
                "calcs": ["lastNotNull"],
                "fields": "",
                "values": False,
            },
            "colorMode": "value",
            "graphMode": "none",
            "textMode": "auto",
            "justifyMode": "center",
        }

    panels.append({
        "id": len(panels) + 1,
        "title": title,
        "description": description,
        "type": kind,
        "datasource": datasource,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": targets,
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": options,
    })


panel("Ready pods", "stat", 0, 0, 8, 4, "short",
      [(ready, "Ready")],
      "Available replicas of the simulator Deployment.")

panel("Requests / second", "stat", 8, 0, 8, 4, "reqps",
      [(traffic, "Requests")],
      "Completed work requests, averaged over 30 seconds.")

panel("Application errors / second", "stat", 16, 0, 8, 4, "ops",
      [(errors, "Errors")],
      "HTTP 500 processing failures. Connection failures must be measured by the client.")

panel("Scaling: desired vs ready pods", "timeseries", 0, 4, 8, 10, "short",
      [(desired, "HPA desired"), (ready, "Ready")],
      "The HPA requests replicas; new pods then become ready.")

panel("CPU usage per pod", "timeseries", 8, 4, 8, 10, "suffix:mCPU",
      [(cpu, "{{pod}}"), ("vector(60)", "Target reference: 60m")],
      "CPU usage in millicores. HPA targets an average of 60m per pod; its measurement window differs.")

panel("Processing time — estimated p95", "timeseries", 16, 4, 8, 10, "s",
      [(latency, "p95")],
      "Estimated processing time covering 95% of completed requests. Excludes network time; blank without traffic.")

dashboard = {
    "id": None,
    "uid": "demo-toon-raid-demo",
    "title": "Raid Traffic — Scaling & Recovery",
    "description": (
        "Synthetic load demonstration on a local, single-node K3s cluster. "
        "Separate from the live Uther character tracker."
    ),
    "tags": ["demo-toon", "demo", "autoscaling"],
    "timezone": "browser",
    "schemaVersion": 39,
    "version": 1,
    "refresh": "5s",
    "time": {"from": "now-5m", "to": "now"},
    "__inputs": [{
        "name": "DS_PROMETHEUS",
        "label": "Prometheus",
        "type": "datasource",
        "pluginId": "prometheus",
        "pluginName": "Prometheus",
    }],
    "panels": panels,
}

output = Path("deploy/grafana/raid-simulator.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(dashboard, indent=2) + "\n")
print(f"Created {output} with {len(panels)} panels.")
