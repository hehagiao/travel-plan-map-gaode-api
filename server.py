#!/usr/bin/env python3
import json
import os
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
AMAP_TRANSIT_URL = "https://restapi.amap.com/v3/direction/transit/integrated"


def load_dotenv():
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


class ChinaMapHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path.startswith("/data/china-map/"):
            self.path = "/" + self.path.removeprefix("/data/china-map/")
        super().do_GET()

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/transit":
            self.send_error(404)
            return

        key = os.environ.get("AMAP_KEY") or os.environ.get("AMAP_MAPS_API_KEY")
        if not key:
            self.send_json(503, {
                "ok": False,
                "error": "未配置 AMAP_KEY。请先复制 .env.example 为 .env，并填入你自己的高德 Key 后再启动 server.py。"
            })
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            origin = payload["origin"]
            destinations = payload.get("destinations", [])
            if not destinations:
                raise ValueError("缺少 destinations")
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": f"请求参数错误：{exc}"})
            return

        results = []
        for destination in destinations:
            query = {
                "key": key,
                "origin": f"{origin['lng']},{origin['lat']}",
                "destination": f"{destination['lng']},{destination['lat']}",
                "city": origin.get("city") or origin.get("name") or "",
                "cityd": destination.get("city") or destination.get("name") or "",
                "extensions": "all",
                "strategy": "0",
                "nightflag": "0",
                "output": "json",
            }
            try:
                with urlopen(f"{AMAP_TRANSIT_URL}?{urlencode(query)}", timeout=15) as response:
                    data = json.loads(response.read().decode("utf-8"))
                results.append(summarize_transit(destination, data))
                time.sleep(0.08)
            except Exception as exc:
                results.append({
                    "destination": destination,
                    "ok": False,
                    "error": str(exc)
                })

        self.send_json(200, {"ok": True, "origin": origin, "results": results})


def seconds_to_text(value):
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return "未知"
    hours, rem = divmod(seconds, 3600)
    minutes = round(rem / 60)
    if hours:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分钟"


def meters_to_text(value):
    try:
        meters = float(value)
    except (TypeError, ValueError):
        return "未知"
    if meters >= 1000:
        return f"{meters / 1000:.1f}公里"
    return f"{meters:.0f}米"


def normalize_list(value):
    if not value:
        return []
    return value if isinstance(value, list) else [value]


def train_category(railway):
    trip = str(railway.get("trip") or "")
    text = f"{railway.get('name', '')} {railway.get('type', '')}"
    if trip.startswith(("G", "D", "C")) or any(token in text for token in ("高铁", "动车", "城际")):
        return "highspeed"
    return "regular"


def prices_from_spaces(spaces):
    prices = []
    for space in normalize_list(spaces):
        try:
            cost = float(space.get("cost"))
        except (TypeError, ValueError):
            continue
        prices.append({
            "seat": space.get("code") or "席别",
            "cost": cost,
            "costText": f"{cost:g}元",
        })
    prices.sort(key=lambda item: item["cost"])
    return prices


def railway_summary(railway):
    departure = railway.get("departure_stop", {}) or {}
    arrival = railway.get("arrival_stop", {}) or {}
    duration = railway.get("time") or railway.get("duration")
    prices = prices_from_spaces(railway.get("spaces"))
    return {
        "name": railway.get("name") or railway.get("trip") or "铁路",
        "trip": railway.get("trip") or "",
        "type": railway.get("type") or "",
        "category": train_category(railway),
        "from": departure.get("name") or "",
        "to": arrival.get("name") or "",
        "departureTime": departure.get("time") or "",
        "arrivalTime": arrival.get("time") or "",
        "duration": duration,
        "durationText": seconds_to_text(duration),
        "distance": railway.get("distance"),
        "distanceText": meters_to_text(railway.get("distance")),
        "prices": prices[:6],
        "minCost": prices[0]["cost"] if prices else None,
        "minCostText": prices[0]["costText"] if prices else "未知",
    }


def extract_railways(transit):
    railways = []
    for segment in transit.get("segments", []):
        railways.extend(railway for railway in normalize_list(segment.get("railway")) if railway)
    return [railway_summary(railway) for railway in railways if railway.get("name") or railway.get("trip")]


def rail_plan(transit):
    railways = extract_railways(transit)
    if not railways:
        return None
    duration_seconds = 0
    known_duration = True
    min_cost = 0
    known_cost = True
    distance = 0
    known_distance = True
    for railway in railways:
        try:
            duration_seconds += int(float(railway["duration"]))
        except (TypeError, ValueError):
            known_duration = False
        if railway["minCost"] is None:
            known_cost = False
        else:
            min_cost += railway["minCost"]
        try:
            distance += float(railway["distance"])
        except (TypeError, ValueError):
            known_distance = False

    categories = {railway["category"] for railway in railways}
    category = "highspeed" if categories == {"highspeed"} else "regular"
    if "highspeed" in categories and "regular" in categories:
        category = "mixed"

    return {
        "direct": len(railways) == 1,
        "category": category,
        "railways": railways,
        "duration": duration_seconds if known_duration else None,
        "durationText": seconds_to_text(duration_seconds) if known_duration else "未知",
        "minCost": min_cost if known_cost else None,
        "minCostText": f"{min_cost:g}元" if known_cost else "未知",
        "distance": distance if known_distance else None,
        "distanceText": meters_to_text(distance) if known_distance else "未知",
        "totalDurationText": seconds_to_text(transit.get("duration")),
        "totalCostText": f"{float(transit.get('cost')):g}元" if transit.get("cost") not in (None, [], "") else "未知",
    }


def choose_rail_plans(transits):
    plans = [plan for plan in (rail_plan(transit) for transit in transits) if plan]
    direct = [plan for plan in plans if plan["direct"]]
    transfer = [plan for plan in plans if not plan["direct"]]

    def sort_key(plan):
      return (
          0 if plan["category"] == "highspeed" else 1,
          plan["duration"] if plan["duration"] is not None else 10**12,
          plan["minCost"] if plan["minCost"] is not None else 10**12,
      )

    return {
        "direct": sorted(direct, key=sort_key)[:3],
        "transfer": sorted(transfer, key=sort_key)[:3],
        "all": sorted(plans, key=sort_key)[:6],
    }


def summarize_transit(destination, data):
    if data.get("status") != "1":
        return {
            "destination": destination,
            "ok": False,
            "error": data.get("info") or "高德接口返回失败",
        }

    route = data.get("route", {})
    transits = route.get("transits", []) or []
    if not transits:
        return {
            "destination": destination,
            "ok": False,
            "error": "未找到公共交通方案",
        }

    rail_options = choose_rail_plans(transits)
    best = transits[0]
    return {
        "destination": destination,
        "ok": True,
        "railOptions": rail_options,
        "fallbackTotal": {
            "cost": best.get("cost") or "未知",
            "duration": best.get("duration"),
            "durationText": seconds_to_text(best.get("duration")),
            "distance": best.get("distance"),
            "distanceText": meters_to_text(best.get("distance")),
        },
    }


def main():
    load_dotenv()
    port = int(os.environ.get("CHINA_MAP_PORT", "8788"))
    server = ThreadingHTTPServer(("127.0.0.1", port), ChinaMapHandler)
    print(f"China map server: http://localhost:{port}/preview.html")
    if not (os.environ.get("AMAP_KEY") or os.environ.get("AMAP_MAPS_API_KEY")):
        print("AMAP_KEY is not set; /api/transit will return a configuration hint.", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()
