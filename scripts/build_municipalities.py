"""市区町村マスタ（app/data/municipalities.json）を国土地理院の公開データから生成する。

取得元: 地理院地図が使う自治体一覧 https://maps.gsi.go.jp/js/muni.js
コード体系: 全国地方公共団体コード（JIS X 0401/0402）の5桁（検査数字なし）。
           GPS変換に使う国土地理院の逆ジオコーダ（muniCd）と同じ体系。

方針:
- 政令指定都市は行政区単位で扱う。「札幌市」のような市そのものの行は、
  同名で始まる行政区の行があるときだけ除く（「倶知安町」のように下2桁が00でも
  区を持たない自治体は残す）。
- 名称に含まれる全角スペース（"札幌市　中央区"）は取り除く。
- 廃止・統合された自治体はこのファイルには含まれない（地理院地図が現行の
  自治体だけを配信している）。過去データに古いコードが残る場合は、
  再生成時に差分を確認して corrective migration で扱う。

使い方:
    .venv/Scripts/python.exe scripts/build_municipalities.py
"""

from __future__ import annotations

import datetime
import json
import re
import urllib.request
from pathlib import Path

SOURCE_URL = "https://maps.gsi.go.jp/js/muni.js"
OUTPUT = Path(__file__).resolve().parent.parent / "app" / "data" / "municipalities.json"
ENTRY = re.compile(r"GSI\.MUNI_ARRAY\[\"(\d+)\"\]\s*=\s*'([^']*)'")


def fetch_source() -> str:
    with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
        return response.read().decode("utf-8")


def parse(raw: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for match in ENTRY.finditer(raw):
        pref_code, pref_name, muni_code, muni_name = match.group(2).split(",")
        name = muni_name.replace("　", "").replace(" ", "")
        rows.append({
            "prefectureCode": pref_code.zfill(2),
            "prefectureName": pref_name,
            "areaCode": muni_code.zfill(5),
            "municipalityName": name,
            "displayName": f"{pref_name}{name}",
        })
    rows.sort(key=lambda row: row["areaCode"])
    codes = [row["areaCode"] for row in rows]
    if len(codes) != len(set(codes)):
        raise SystemExit("自治体コードが重複しています")
    return drop_designated_city_parents(rows)


def drop_designated_city_parents(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """行政区を持つ市（例: 札幌市）の親行を除き、区の行だけを残す。"""
    names = {row["municipalityName"] for row in rows}

    def has_wards(row: dict[str, str]) -> bool:
        name = row["municipalityName"]
        return name.endswith("市") and any(
            other != name and other.startswith(name) and other.endswith("区")
            for other in names
        )

    return [row for row in rows if not has_wards(row)]


def main() -> None:
    rows = parse(fetch_source())
    payload = {
        "source": f"国土地理院 地理院地図 muni.js ({SOURCE_URL})",
        "fetchedAt": datetime.date.today().isoformat(),
        "codeSystem": "全国地方公共団体コード（JIS X 0401/0402、5桁・検査数字なし）。政令指定都市は行政区単位。",
        "municipalities": rows,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    prefectures = {row["prefectureCode"] for row in rows}
    print(f"wrote {OUTPUT} rows={len(rows)} prefectures={len(prefectures)}")


if __name__ == "__main__":
    main()
