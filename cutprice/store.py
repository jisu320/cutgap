"""데이터 저장 구조.

docs/data/
  index.json                 지역 목록 + 갱신 현황 (사이트가 처음 읽는 파일)
  places/{시도}_{시군구}.json  업소 배열 (지역 하나만 골라 받는다)
  regions.json               탐색해서 알아낸 지역 트리 (수집기 내부용)
"""

import json
import os
import re
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "data")
PLACES = os.path.join(DATA, "places")

_SAFE = re.compile(r"[^0-9A-Za-z가-힣]+")


def shard_key(region):
    """'서울 마포구' -> '서울_마포구'"""
    return _SAFE.sub("_", (region or "기타").strip()).strip("_") or "기타"


def _path(key):
    return os.path.join(PLACES, key + ".json")


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(obj, fp, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        fp.write("\n")
    os.replace(tmp, path)


def load_shard(key):
    return read_json(_path(key), default={"region": key, "places": []})


def save_shard(key, shard):
    write_json(_path(key), shard)


def all_shard_keys():
    if not os.path.isdir(PLACES):
        return []
    return sorted(f[:-5] for f in os.listdir(PLACES) if f.endswith(".json"))


def upsert_places(key, region, found):
    """목록 수집 결과를 병합한다. 이미 있던 가격 정보는 보존한다."""
    shard = load_shard(key)
    shard["region"] = region
    by_id = {p["id"]: p for p in shard.get("places", [])}
    added = 0
    for item in found:
        cur = by_id.get(item["id"])
        if cur is None:
            cur = {"id": item["id"], "checked": None, "w": None, "m": None}
            by_id[item["id"]] = cur
            added += 1
        cur.update({
            "name": item["name"],
            "road": item["road"],
            "x": round(item["x"], 6),
            "y": round(item["y"], 6),
            "rep": item["rep"],
        })
    shard["places"] = sorted(by_id.values(), key=lambda p: p["id"])
    shard["listed"] = date.today().isoformat()
    save_shard(key, shard)
    return added, len(shard["places"])


def rebuild_index():
    """샤드들을 훑어 index.json을 다시 쓴다."""
    entries = []
    for key in all_shard_keys():
        shard = load_shard(key)
        places = shard.get("places", [])
        if not places:
            continue
        priced = [p for p in places if (p.get("w") or p.get("m"))]
        xs = [p["x"] for p in places if "x" in p]
        ys = [p["y"] for p in places if "y" in p]
        checked = [p["checked"] for p in places if p.get("checked")]
        entries.append({
            "key": key,
            "region": shard.get("region", key),
            "count": len(places),
            "priced": len(priced),
            "updated": max(checked) if checked else None,
            "cx": round(sum(xs) / len(xs), 6) if xs else None,
            "cy": round(sum(ys) / len(ys), 6) if ys else None,
        })
    entries.sort(key=lambda e: e["region"])
    total = sum(e["count"] for e in entries)
    priced = sum(e["priced"] for e in entries)
    write_json(os.path.join(DATA, "index.json"), {
        "generated": date.today().isoformat(),
        "total": total,
        "priced": priced,
        "regions": entries,
    })
    return entries
