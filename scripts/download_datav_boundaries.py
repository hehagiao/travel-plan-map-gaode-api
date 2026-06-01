#!/usr/bin/env python3
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

BASE_URL = "https://geo.datav.aliyun.com/areas_v3/bound"
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "datav"
ROOT_ADCODE = "100000"


def write_json(path, payload):
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def fetch_json(adcode):
    target = OUT_DIR / f"{adcode}_full.json"
    if target.exists() and target.stat().st_size > 0:
        with target.open(encoding="utf-8") as file:
            return json.load(file)

    url = f"{BASE_URL}/{adcode}_full.json"
    for attempt in range(3):
        try:
            with urlopen(url, timeout=25) as response:
                data = json.loads(response.read().decode("utf-8"))
            write_json(target, data)
            time.sleep(0.12)
            return data
        except (HTTPError, URLError, TimeoutError) as error:
            if attempt == 2:
                print(f"skip {adcode}: {error}")
                return None
            time.sleep(0.6 * (attempt + 1))


def child_adcodes(geojson):
    codes = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        children = props.get("childrenNum", 0) or 0
        adcode = props.get("adcode")
        if children > 0 and adcode:
            codes.append(str(adcode))
    return codes


def build_combined_layers():
    groups = {"province": [], "city": [], "district": []}
    seen = {key: set() for key in groups}
    for path in sorted(OUT_DIR.glob("*_full.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            level = props.get("level")
            adcode = str(props.get("adcode") or "")
            if level not in groups or not adcode or adcode in seen[level]:
                continue
            seen[level].add(adcode)
            groups[level].append(feature)

    for level, features in groups.items():
        target = OUT_DIR / f"combined_{level}.json"
        write_json(target, {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "source": BASE_URL,
                "generatedBy": "scripts/download_datav_boundaries.py",
                "level": level,
                "featureCount": len(features),
            },
        })
        print(f"built {target.name}: {len(features)} features")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    queue = [ROOT_ADCODE]
    seen = set()

    while queue:
        adcode = queue.pop(0)
        if adcode in seen:
            continue
        seen.add(adcode)
        geojson = fetch_json(adcode)
        if not geojson:
            continue
        queue.extend(code for code in child_adcodes(geojson) if code not in seen)
        print(f"{adcode}: features={len(geojson.get('features', []))}, queued={len(queue)}")

    index = sorted(path.name for path in OUT_DIR.glob("*_full.json"))
    (OUT_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    build_combined_layers()
    print(f"downloaded {len(index)} files to {OUT_DIR}")


if __name__ == "__main__":
    main()
