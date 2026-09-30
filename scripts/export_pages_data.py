import urllib.request
import json
import os

os.makedirs("dashboard/data", exist_ok=True)

endpoints = {
    "summary.json": "dashboard/summary",
    "alerts.json": "alerts?limit=50",
    "transfers.json": "transfers?limit=50",
    "federation.json": "dashboard/federation",
    "timeline.json": "dashboard/outbreak_timeline?district=Kolar"
}

for filename, ep in endpoints.items():
    url = f"http://127.0.0.1:8000/api/v1/{ep}"
    try:
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            out_path = os.path.join("dashboard/data", filename)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"[OK] Exported {out_path} ({len(json.dumps(data))} bytes)")
    except Exception as e:
        print(f"[FAIL] Error exporting {ep}: {e}")
