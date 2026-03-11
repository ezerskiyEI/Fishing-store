import json
import time
import requests

with open("static/data/points.json", "r", encoding="utf-8") as f:
    points = json.load(f)

def geocode(address):

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": address,
        "format": "json",
        "limit": 1
    }

    headers = {
        "User-Agent": "geo-script"
    }

    r = requests.get(url, params=params, headers=headers)
    data = r.json()

    if len(data) == 0:
        return None

    return [float(data[0]["lat"]), float(data[0]["lon"])]

for i, point in enumerate(points):

    print(i + 1, point["addr"])

    coords = geocode(point["addr"])

    point["coords"] = coords

    time.sleep(1)

with open("points_ready.json", "w", encoding="utf-8") as f:
    json.dump(points, f, ensure_ascii=False, indent=2)

print("ГОТОВО")