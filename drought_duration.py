import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta
import sys

def fetch_drought_data(date_str):
    url = "https://hydro.kma.go.kr/selectDrghtAdmCntPop.do"
    data = urllib.parse.urlencode({
        "search_dt": date_str,
        "spi_type": "spi6",
        "drght_level": "total_cnt"
    }).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req) as response:
            res = response.read().decode('utf-8')
            return json.loads(res).get("dataList", [])
    except Exception as e:
        return []

def get_drought_regions(data):
    """
    Returns a dictionary mapping a unique region string to its drought level.
    Only considers regions in CASE_3 to CASE_6.
    """
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
    target_date_str = target_date.strftime("%Y%m%d")

    print(f"기준일({target_date.strftime('%Y-%m-%d')})의 가뭄 발생 지역 데이터를 수집 중입니다...")

    initial_data = fetch_drought_data(target_date_str)
    initial_regions = get_drought_regions(initial_data)

    if not initial_regions:
        print("현재 기상가뭄이 발생하고 있는 지역이 없습니다.")
        return

    drought_duration = {region: 1 for region in initial_regions.keys()}
    current_active = set(initial_regions.keys())

    print(f"총 {len(current_active)}개 시군에 대하여 과거 지속일을 역추적합니다. (잠시만 기다려주세요...)")

    days_backward = 0
    # 역추적
    while current_active:
        days_backward += 1
        check_date = target_date - timedelta(days=days_backward)
        check_date_str = check_date.strftime("%Y%m%d")

        data = fetch_drought_data(check_date_str)
        drought_regions_on_date = set(get_drought_regions(data).keys())

        ended_regions = []
        for region in current_active:
            if region in drought_regions_on_date:
                drought_duration[region] += 1
            else:
                # 더 이상 가뭄 상태가 아님 (정상으로 돌아감)
                ended_regions.append(region)

        for region in ended_regions:
            current_active.remove(region)

        # 콘솔 진행상황 표시
        sys.stdout.write(f"\r추적 중: {check_date.strftime('%Y-%m-%d')} (남은 분석 대상 지역: {len(current_active)}개)")
        sys.stdout.flush()

        # 1년(365일) 이상 지속되는 경우 루프 방지
        if days_backward >= 365:
            break

    print("\n\n==================================================")
    print(f" 가뭄 발생 지역별 지속일 분석 결과 (기준일: {target_date.strftime('%Y-%m-%d')})")
    print("==================================================")

    # 결과를 지역별(시도)로 그룹화하여 출력
    grouped_results = {}
    for region, duration in drought_duration.items():
        brtc, sigungu = region.split(" ", 1)
        if brtc not in grouped_results:
            grouped_results[brtc] = []
        grouped_results[brtc].append((sigungu, duration, initial_regions[region]))

    for brtc, regions in grouped_results.items():
        print(f"\n[ {brtc} ]")
        # 지속일 기준 내림차순 정렬, 그 다음 지역명 정렬
        sorted_regions = sorted(regions, key=lambda x: (-x[1], x[0]))
        for sigungu, duration, level in sorted_regions:
            print(f"  - {sigungu} ({level}): {duration}일 지속")

if __name__ == "__main__":
    main()
