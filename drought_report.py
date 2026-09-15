import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta
import sys
import time

def fetch_drought_data(date_str, retries=5):
    url = "https://hydro.kma.go.kr/selectDrghtAdmCntPop.do"
    data = urllib.parse.urlencode({
        "search_dt": date_str,
        "spi_type": "spi6",
        "drght_level": "total_cnt"
    }).encode('utf-8')
    req = urllib.request.Request(url, data=data)

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res = response.read().decode('utf-8')
                return json.loads(res).get("dataList", [])
        except Exception as e:
            if attempt == retries - 1:
                print(f"Error fetching {date_str}: {e}")
                return []
            time.sleep(1)

def get_drought_regions(data):
    if not data:
        return {}

    drought_map = {
        "CASE_3": "약한가뭄",
        "CASE_4": "보통가뭄",
        "CASE_5": "심한가뭄",
        "CASE_6": "극심한가뭄"
    }

    regions = {}
    for item in data:
        kind = item.get("DRIDX_VALUE_TRAN")
        if kind in drought_map:
            brtc = item.get("BRTC_NM", "").strip()
            if "(" in brtc:
                brtc = brtc[:brtc.find("(")].strip()

            sigungus = item.get("SIGUNGU_ARR", "").split(",")
            for sigungu in sigungus:
                sigungu = sigungu.strip()
                if sigungu:
                    region_key = f"{brtc} {sigungu}"
                    regions[region_key] = drought_map[kind]
    return regions

def get_emoji(level):
    return {
        "정상": "⚪",
        "약한가뭄": "🟢",
        "보통가뭄": "🟡",
        "심한가뭄": "🟠",
        "극심한가뭄": "🔴"
    }.get(level, "❓")

severity_order = {"정상": 0, "약한가뭄": 1, "보통가뭄": 2, "심한가뭄": 3, "극심한가뭄": 4}

def compare_regions(old, new):
    new_regions = set(new.keys()) - set(old.keys())
    released = set(old.keys()) - set(new.keys())
    worsened = []
    improved = []
    same = []
    for r in set(old.keys()) & set(new.keys()):
        old_sev = severity_order[old[r]]
        new_sev = severity_order[new[r]]
        if new_sev > old_sev:
            worsened.append(r)
        elif new_sev < old_sev:
            improved.append(r)
        else:
            same.append(r)
    return new_regions, released, worsened, improved, same

def main():
    target_str = "2026-09-14"
    target_date = datetime.strptime(target_str, "%Y-%m-%d")

    print(f"Fetching data for {target_str}...")

    dates_to_fetch = {
        "today": target_date,
        "yesterday": target_date - timedelta(days=1),
        "7days": target_date - timedelta(days=7),
        "30days": target_date - timedelta(days=30)
    }

    data_by_period = {}
    for key, dt in dates_to_fetch.items():
        dt_str = dt.strftime("%Y%m%d")
        data = fetch_drought_data(dt_str)
        data_by_period[key] = get_drought_regions(data)
        time.sleep(0.5)

    # For duration tracking
    current_active = set(data_by_period["today"].keys())
    history = {region: [(target_date, data_by_period["today"][region])] for region in current_active}

    days_backward = 0
    while current_active:
        days_backward += 1
        check_date = target_date - timedelta(days=days_backward)
        if days_backward == 1:
            drought_regions_on_date = data_by_period["yesterday"]
        elif days_backward == 7:
            drought_regions_on_date = data_by_period["7days"]
        elif days_backward == 30:
            drought_regions_on_date = data_by_period["30days"]
        else:
            data = fetch_drought_data(check_date.strftime("%Y%m%d"))
            drought_regions_on_date = get_drought_regions(data)
            time.sleep(0.1)

        ended_regions = []
        for region in current_active:
            if region in drought_regions_on_date:
                history[region].append((check_date, drought_regions_on_date[region]))
            else:
                ended_regions.append(region)

        for region in ended_regions:
            current_active.remove(region)

        if days_backward >= 365:
            break

    # Calculate durations
    durations = {}
    for region, hist in history.items():
        durations[region] = len(hist)

    # 1페이지 요약
    today_regions = data_by_period["today"]
    yest_regions = data_by_period["yesterday"]

    today_counts = {"약한가뭄": 0, "보통가뭄": 0, "심한가뭄": 0, "극심한가뭄": 0}
    for r, lvl in today_regions.items():
        today_counts[lvl] += 1

    yest_counts = {"약한가뭄": 0, "보통가뭄": 0, "심한가뭄": 0, "극심한가뭄": 0}
    for r, lvl in yest_regions.items():
        yest_counts[lvl] += 1

    new_regions, released, worsened, improved, same = compare_regions(yest_regions, today_regions)

    report = []
    report.append("==========================================================")
    report.append(f" 기상가뭄 현황 및 변화 경향 보고서 ({target_date.strftime('%Y년 %m월 %d일')})")
    report.append("==========================================================\n")

    report.append("[ 1페이지: 요약 ]\n")
    report.append("■ 오늘 현황")
    report.append(f" - 총 가뭄 발생 지역: {len(today_regions)}곳")
    for lvl in ["극심한가뭄", "심한가뭄", "보통가뭄", "약한가뭄"]:
        if today_counts[lvl] > 0:
            report.append(f" - {lvl}: {today_counts[lvl]}곳")

    report.append("\n■ 전일 대비 변화")
    report.append(f" - 총 {len(today_regions) - len(yest_regions)}곳 증감")
    if worsened:
        report.append(f" - 악화된 지역: {len(worsened)}곳")
    if improved:
        report.append(f" - 호전된 지역: {len(improved)}곳")

    report.append("\n■ 신규/해제")
    report.append(f" - 신규 가뭄 발생 지역: {len(new_regions)}곳 " + (f"({', '.join(new_regions)})" if new_regions else ""))
    report.append(f" - 가뭄 해제 지역: {len(released)}곳 " + (f"({', '.join(released)})" if released else ""))

    report.append("\n■ 종합평가")
    if len(today_regions) > len(yest_regions):
        eval_txt = "전일 대비 가뭄 지역이 증가하여 주의가 필요합니다."
    elif len(today_regions) < len(yest_regions):
        eval_txt = "전일 대비 가뭄 지역이 감소하여 호전되는 추세입니다."
    else:
        eval_txt = "전일과 유사한 수준의 가뭄이 지속되고 있습니다."

    if today_counts["극심한가뭄"] > 0 or today_counts["심한가뭄"] > 0:
        eval_txt += f" 특히, 심한 가뭄 이상의 지역이 {today_counts['극심한가뭄'] + today_counts['심한가뭄']}곳 존재하여 집중 관리가 요구됩니다."
    report.append(f" - {eval_txt}")

    report.append("\n" + "="*58 + "\n")

    report.append("[ 2페이지: 권역 분석 ]\n")

    def get_provincial_data(regions_dict):
        prov = {}
        for r, lvl in regions_dict.items():
            p = r.split()[0]
            if p not in prov:
                prov[p] = 0
            prov[p] += 1
        return prov

    today_prov = get_provincial_data(today_regions)
    yest_prov = get_provincial_data(yest_regions)

    report.append("■ 권역별 현황")
    for p in sorted(today_prov.keys()):
        report.append(f" - {p}: {today_prov[p]}곳")

    report.append("\n■ 증감 (전일 대비)")
    all_provs = set(today_prov.keys()) | set(yest_prov.keys())
    for p in sorted(all_provs):
        diff = today_prov.get(p, 0) - yest_prov.get(p, 0)
        if diff > 0:
            report.append(f" - {p}: {diff}곳 증가 🔺")
        elif diff < 0:
            report.append(f" - {p}: {abs(diff)}곳 감소 🔽")
        else:
            report.append(f" - {p}: 변동 없음 (-)")

    report.append("\n" + "="*58 + "\n")

    report.append("[ 3페이지: 추세 분석 ]\n")

    def get_trend_str(old_dict, new_dict):
        diff = len(new_dict) - len(old_dict)
        if diff > 0:
            return f"가뭄 지역 {diff}곳 증가 (악화)"
        elif diff < 0:
            return f"가뭄 지역 {abs(diff)}곳 감소 (호전)"
        else:
            return "변동 없음"

    report.append("■ 1일 추세 (전일 대비)")
    report.append(f" - {get_trend_str(yest_regions, today_regions)}")

    report.append("\n■ 7일 추세 (7일 전 대비)")
    report.append(f" - {get_trend_str(data_by_period['7days'], today_regions)}")

    report.append("\n■ 30일 추세 (30일 전 대비)")
    report.append(f" - {get_trend_str(data_by_period['30days'], today_regions)}")

    report.append("\n■ 지속일수 상위지역 (Top 10)")
    sorted_durations = sorted(durations.items(), key=lambda x: -x[1])
    for i, (r, d) in enumerate(sorted_durations[:10]):
        lvl = today_regions[r]
        report.append(f" {i+1}. {r}: {d}일 지속 (현재: {lvl})")

    with open("report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print("Report written to report.txt")

if __name__ == "__main__":
    main()
