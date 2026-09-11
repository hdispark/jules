import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta
import sys
import time
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
import matplotlib.font_manager as fm

# Matplotlib Korean font setting (NanumGothic)
import matplotlib.font_manager as fm
import os

# Safely add the NanumGothic font if it exists, without deleting caches
nanum_path = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
if os.path.exists(nanum_path):
    fm.fontManager.addfont(nanum_path)
    plt.rcParams['font.family'] = 'NanumGothic'
else:
    print("Warning: NanumGothic font file not found. Korean characters may not render correctly.")

plt.rcParams['axes.unicode_minus'] = False

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
                sys.exit(1)
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

def main():
    target_date = datetime(2026, 9, 10)
    print(f"데이터 수집 중... 기준일: {target_date.strftime('%Y-%m-%d')}")

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

    print("\n데이터 수집 완료. 시각화 그래프를 생성합니다...\n")

    periods = {}
    for region, hist in history.items():
        hist.reverse()
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
            "periods": region_periods
        }

    # Select Top 15 longest lasting regions
    sorted_regions = sorted(periods.items(), key=lambda x: -x[1]["total_days"])[:15]

    # Visualization using Gantt chart style
    fig, ax = plt.subplots(figsize=(14, 8))

    color_map = {
        "약한가뭄": "#a8d5e2",  # Light blue/green
        "보통가뭄": "#f9ca24",  # Yellow
        "심한가뭄": "#f0932b",  # Orange
        "극심한가뭄": "#eb4d4b"   # Red
    }

    y_labels = []

    for idx, (region, data) in enumerate(reversed(sorted_regions)):
        y_labels.append(f"{region} ({data['total_days']}일)")
        for p_start, p_end, p_level in data["periods"]:
            # + timedelta(days=1) to include the end day fully in the plot block
            start_num = mdates.date2num(p_start)
            end_num = mdates.date2num(p_end + timedelta(days=1))
            ax.barh(idx, end_num - start_num, left=start_num, height=0.5,
                    color=color_map.get(p_level, "grey"), edgecolor='black', linewidth=0.5)

    ax.set_yticks(range(len(y_labels)))
    ax.set_yticklabels(y_labels, fontsize=11)

    # Format x-axis
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    plt.xticks(rotation=45, ha='right')

    ax.set_xlabel('날짜 (2026년)', fontsize=12)
    ax.set_title(f'기상가뭄 최장 지속 지역 Top 15 타임라인 (기준일: {target_date.strftime("%Y-%m-%d")})', fontsize=16, fontweight='bold', pad=20)

    # Add legend
    legend_elements = [Patch(facecolor=color_map[k], edgecolor='black', label=k) for k in color_map.keys()]
    ax.legend(handles=legend_elements, loc='lower right', bbox_to_anchor=(1.15, 0))

    plt.grid(axis='x', linestyle='--', alpha=0.7)
    plt.tight_layout()

    plt.savefig('drought_timeline.png', dpi=300, bbox_inches='tight')
    print("그래프가 'drought_timeline.png' 파일로 저장되었습니다.")

if __name__ == "__main__":
    main()
