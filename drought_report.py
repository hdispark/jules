import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta
import sys
import time

def fetch_drought_data(date_str, retries=3):
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
                print(f"\nError fetching data for {date_str}: {e}")
                return []
            time.sleep(1)

def get_drought_regions(data):
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

def main():
    target_date = datetime(2026, 9, 10)

    print(f"보고서 생성을 위한 데이터를 수집 중입니다. 기준일: {target_date.strftime('%Y-%m-%d')}...")

    initial_data = fetch_drought_data(target_date.strftime("%Y%m%d"))
    initial_regions = get_drought_regions(initial_data)

    if not initial_regions:
        print("현재 기상가뭄이 발생하고 있는 지역이 없습니다.")
        return

    history = {region: [(target_date, initial_regions[region])] for region in initial_regions.keys()}
    current_active = set(initial_regions.keys())

    days_backward = 0
    while current_active:
        days_backward += 1
        check_date = target_date - timedelta(days=days_backward)

        data = fetch_drought_data(check_date.strftime("%Y%m%d"))
        drought_regions_on_date = get_drought_regions(data)

        ended_regions = []
        for region in current_active:
            if region in drought_regions_on_date:
                history[region].append((check_date, drought_regions_on_date[region]))
            else:
                ended_regions.append(region)

        for region in ended_regions:
            current_active.remove(region)

        sys.stdout.write(f"\r추적 중: {check_date.strftime('%Y-%m-%d')} (남은 대상: {len(current_active)}개)")
        sys.stdout.flush()

        if days_backward >= 365:
            break

    print("\n")

    periods = {}
    for region, hist in history.items():
        hist.reverse() # oldest to newest
        region_periods = []

        current_level = hist[0][1]
        start_date = hist[0][0]

        for i in range(1, len(hist)):
            date, level = hist[i]
            if level != current_level:
                end_date = hist[i-1][0]
                region_periods.append((start_date, end_date, current_level))
                start_date = date
                current_level = level

        end_date = hist[-1][0]
        region_periods.append((start_date, end_date, current_level))

        periods[region] = {
            "total_days": len(hist),
            "periods": region_periods,
            "current_level": initial_regions[region]
        }

    # Generate Report
    with open('report.txt', 'w') as f:
        f.write("==========================================================\n")
        f.write(" 2026년 9월 10일 기준 기상가뭄 심층 분석 보고서\n")
        f.write("==========================================================\n\n")

        f.write("1. [요약] 전국 기상가뭄 개황\n")
        f.write("-" * 58 + "\n")
        f.write(f" - 총 가뭄 발생 시군구: {len(initial_regions)}개 지역\n")

        sorted_by_duration = sorted(periods.items(), key=lambda x: -x[1]["total_days"])
        top_regions = sorted_by_duration[:5]
        f.write(" - 최장기 가뭄 지속 지역 (Top 5):\n")
        for r_name, r_data in top_regions:
            f.write(f"   * {r_name}: {r_data['total_days']}일\n")
        f.write("\n")

        f.write("2. [지역별 현황] 시도별 가뭄 지속일 요약\n")
        f.write("-" * 58 + "\n")
        by_province = {}
        for r_name, r_data in periods.items():
            prov, city = r_name.split(" ", 1)
            if prov not in by_province:
                by_province[prov] = []
            by_province[prov].append((city, r_data))

        for prov in sorted(by_province.keys(), key=lambda x: -len(by_province[x])):
            cities = by_province[prov]
            f.write(f" [ {prov} ] - {len(cities)}개 시군구\n")
            cities_sorted = sorted(cities, key=lambda x: -x[1]["total_days"])
            avg_days = sum(c[1]["total_days"] for c in cities) / len(cities)
            max_city = cities_sorted[0]
            f.write(f"  * 평균 지속일: {avg_days:.1f}일 | 최장 지속일: {max_city[0]} ({max_city[1]['total_days']}일)\n")
        f.write("\n")

        f.write("3. [상세 보고서] 시군구별 가뭄 지속일 및 단계 변화 이력\n")
        f.write("-" * 58 + "\n")
        for prov in sorted(by_province.keys(), key=lambda x: -len(by_province[x])):
            cities = by_province[prov]
            cities_sorted = sorted(cities, key=lambda x: -x[1]["total_days"])
            f.write(f"\n▶ {prov}\n")
            for city, r_data in cities_sorted:
                total = r_data["total_days"]
                curr_lv = r_data["current_level"]
                f.write(f"  ■ {city}: 총 {total}일 지속 (현재: {curr_lv})\n")

                # Simple text-based visualization (timeline)
                # We'll map levels to characters
                char_map = {
                    "정상": ".",
                    "약한가뭄": "░",
                    "보통가뭄": "▒",
                    "심한가뭄": "▓",
                    "극심한가뭄": "█"
                }

                timeline_chars = ""
                for p_start, p_end, p_level in r_data["periods"]: # oldest to newest
                    days = (p_end - p_start).days + 1
                    char = char_map.get(p_level, "?")
                    # Scale: 1 character = 2 days (to keep lines from getting too long)
                    scaled_length = max(1, days // 2)
                    timeline_chars += char * scaled_length

                f.write(f"    [시각화: 과거-->현재] {timeline_chars} (기호: ░=약, ▒=보, ▓=심, █=극심)\n")

                # Print periods in reverse (newest to oldest) for better readability
                reversed_periods = r_data["periods"][::-1]
                for p_start, p_end, p_level in reversed_periods:
                    days = (p_end - p_start).days + 1
                    start_str = p_start.strftime("%Y-%m-%d")
                    end_str = p_end.strftime("%Y-%m-%d")
                    f.write(f"    - {start_str} ~ {end_str} ({days:2d}일): {p_level}\n")
    print("보고서 작성이 완료되어 report.txt 에 저장되었습니다.")

if __name__ == "__main__":
    main()
