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
                print(f"\n[오류] API 호출 실패 (날짜: {date_str}): {e}")
                sys.exit(1) # Stop execution rather than corrupting data
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
        # Add a small delay to prevent rate-limiting
        time.sleep(0.1)

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

    print("\n데이터 수집 완료. 보고서를 생성합니다...\n")

    periods = {}
    level_counts = {"약한가뭄": 0, "보통가뭄": 0, "심한가뭄": 0, "극심한가뭄": 0}

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

        curr_lv = initial_regions[region]
        level_counts[curr_lv] += 1

        periods[region] = {
            "total_days": len(hist),
            "periods": region_periods,
            "current_level": curr_lv
        }

    # Generate Report based on proposed structure
    with open('report.txt', 'w') as f:
        f.write("==========================================================\n")
        f.write(" 💡 기상가뭄 현황 심층 분석 보고서 \n")
        f.write(f" (기준일: {target_date.strftime('%Y년 %m월 %d일')})\n")
        f.write("==========================================================\n\n")

        # 1. Executive Summary
        f.write("1. [핵심 요약] Executive Summary\n")
        f.write("-" * 58 + "\n")
        f.write(f" ▶ 전국 가뭄 위기 경보 수준: 총 {len(initial_regions)}개 시군구에서 가뭄 발생 중.\n")

        # Find some key insights
        severe_count = level_counts["심한가뭄"] + level_counts["극심한가뭄"]
        if severe_count > 0:
            f.write(f" ▶ 주요 이슈: '심한가뭄' 이상 단계 지역이 {severe_count}곳 존재하여 집중 관리가 필요합니다.\n")

        long_term_count = sum(1 for d in periods.values() if d["total_days"] >= 30)
        f.write(f" ▶ 지속성 우려: 30일 이상 장기 가뭄이 지속되는 지역이 {long_term_count}곳에 달합니다.\n\n")

        sorted_by_duration = sorted(periods.items(), key=lambda x: -x[1]["total_days"])
        f.write(" ▶ 최우선 모니터링 대상 (최장기 지속 Top 5):\n")
        for r_name, r_data in sorted_by_duration[:5]:
            lv_emoji = get_emoji(r_data["current_level"])
            f.write(f"   * {r_name} {lv_emoji} (현재 {r_data['current_level']}, {r_data['total_days']}일 지속)\n")
        f.write("\n")

        # 2. Severity Distribution
        f.write("2. [분포 현황] 가뭄 단계별 비중\n")
        f.write("-" * 58 + "\n")
        total = len(initial_regions)
        for lv in ["극심한가뭄", "심한가뭄", "보통가뭄", "약한가뭄"]:
            count = level_counts[lv]
            if count > 0:
                pct = (count / total) * 100
                f.write(f" {get_emoji(lv)} {lv}: {count}곳 ({pct:.1f}%)\n")
        f.write("\n")

        # 3. Regional Trend (Provincial)
        f.write("3. [권역별 현황] 가뭄 집중도 및 지속 시간\n")
        f.write("-" * 58 + "\n")
        by_province = {}
        for r_name, r_data in periods.items():
            prov, city = r_name.split(" ", 1)
            if prov not in by_province:
                by_province[prov] = []
            by_province[prov].append((city, r_data))

        for prov in sorted(by_province.keys(), key=lambda x: -len(by_province[x])):
            cities = by_province[prov]
            avg_days = sum(c[1]["total_days"] for c in cities) / len(cities)
            max_city = sorted(cities, key=lambda x: -x[1]["total_days"])[0]
            f.write(f" 📍 [ {prov} ] : 총 {len(cities)}개 시군구 발생\n")
            f.write(f"    - 평균 지속기간: {avg_days:.1f}일\n")
            f.write(f"    - 최장기 지역: {max_city[0]} ({max_city[1]['total_days']}일 지속)\n")
        f.write("\n")

        # 4. Detailed Monitor List
        f.write("4. [상세 부록] 시군구별 가뭄 지속일 및 타임라인\n")
        f.write("-" * 58 + "\n")
        f.write(" * 범례: 🟢약한가뭄 🟡보통가뭄 🟠심한가뭄 🔴극심한가뭄 (타임라인은 1글자=2일, 과거→현재 순)\n\n")
        for prov in sorted(by_province.keys(), key=lambda x: -len(by_province[x])):
            cities = by_province[prov]
            cities_sorted = sorted(cities, key=lambda x: -x[1]["total_days"])
            f.write(f"▣ {prov}\n")
            for city, r_data in cities_sorted:
                total = r_data["total_days"]
                curr_lv = r_data["current_level"]
                f.write(f"  ■ {city}: 총 {total}일 지속 (현재: {get_emoji(curr_lv)} {curr_lv})\n")

                # Visual timeline
                char_map = {
                    "약한가뭄": "🟢",
                    "보통가뭄": "🟡",
                    "심한가뭄": "🟠",
                    "극심한가뭄": "🔴"
                }

                timeline_chars = ""
                for p_start, p_end, p_level in r_data["periods"]: # oldest to newest
                    days = (p_end - p_start).days + 1
                    char = char_map.get(p_level, "⚪")
                    # Scale: 1 character = 2 days
                    scaled_length = max(1, days // 2)
                    timeline_chars += char * scaled_length

                f.write(f"    [시각화] {timeline_chars}\n")

                reversed_periods = r_data["periods"][::-1]
                for p_start, p_end, p_level in reversed_periods:
                    days = (p_end - p_start).days + 1
                    start_str = p_start.strftime("%Y-%m-%d")
                    end_str = p_end.strftime("%Y-%m-%d")
                    f.write(f"    - {start_str} ~ {end_str} ({days:2d}일): {p_level}\n")
            f.write("\n")

    print("보고서 생성이 완료되었습니다: report.txt")

if __name__ == "__main__":
    main()
