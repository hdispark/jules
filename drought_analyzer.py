import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta

def fetch_drought_data(date_str):
    url = "https://hydro.kma.go.kr/selectDrghtAdmCntPop.do"
    data = urllib.parse.urlencode({
        "search_dt": date_str,
        "spi_type": "spi6",
        "drght_level": "total_cnt"
    }).encode('utf-8')

    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req) as response:
        res = response.read().decode('utf-8')
        return json.loads(res).get("dataList", [])

def parse_drought_status(data):
    # 기상가뭄 단계 매핑 (CASE_3: 약한가뭄, CASE_4: 보통가뭄, CASE_5: 심한가뭄, CASE_6: 극심한가뭄)
    drought_map = {
        "CASE_3": "약한가뭄",
        "CASE_4": "보통가뭄",
        "CASE_5": "심한가뭄",
        "CASE_6": "극심한가뭄"
    }

    status = {}
    for item in data:
        kind = item.get("DRIDX_VALUE_TRAN")
        if kind not in drought_map:
            continue

        level_name = drought_map[kind]
        if level_name not in status:
            status[level_name] = {"count": 0, "regions": []}

        brtc = item.get("BRTC_NM", "").strip()
        sigungu = item.get("SIGUNGU_ARR", "")
        count = item.get("SUBCNT", 0)

        status[level_name]["count"] += count
        status[level_name]["regions"].append(f"{brtc} ({sigungu})")

    return status

def main():
    target_date = datetime(2026, 9, 10)
    past_date = target_date - timedelta(days=30)

    target_date_str = target_date.strftime("%Y%m%d")
    past_date_str = past_date.strftime("%Y%m%d")

    print(f"==================================================")
    print(f" 기상가뭄 정보 분석 결과")
    print(f"==================================================")
    print(f" - 기준일: {target_date.strftime('%Y년 %m월 %d일')}")
    print(f" - 비교일(30일 전): {past_date.strftime('%Y년 %m월 %d일')}")
    print(f"==================================================\n")

    target_data = fetch_drought_data(target_date_str)
    past_data = fetch_drought_data(past_date_str)

    target_status = parse_drought_status(target_data)
    past_status = parse_drought_status(past_data)

    print("1. 9월 10일 기상가뭄 단계별 상황")
    if not target_status:
        print(" - 가뭄 발생 지역이 없습니다.")
    for level in ["약한가뭄", "보통가뭄", "심한가뭄", "극심한가뭄"]:
        if level in target_status:
            print(f" ▷ {level}: 총 {target_status[level]['count']}개 시군")
            for region in target_status[level]['regions']:
                print(f"    * {region}")

    print("\n--------------------------------------------------\n")
    print("2. 과거 30일 동안의 기상가뭄 변화 (8월 11일 -> 9월 10일)")
    levels = ["약한가뭄", "보통가뭄", "심한가뭄", "극심한가뭄"]
    for level in levels:
        past_count = past_status.get(level, {}).get("count", 0)
        target_count = target_status.get(level, {}).get("count", 0)

        diff = target_count - past_count
        diff_str = ""
        if diff > 0:
            diff_str = f"({diff}개 시군 증가 ▲)"
        elif diff < 0:
            diff_str = f"({abs(diff)}개 시군 감소 ▼)"
        else:
            diff_str = "(변동 없음 -)"

        print(f" ▷ {level}: {past_count}개 시군 -> {target_count}개 시군 {diff_str}")

    print(f"\n==================================================")

if __name__ == "__main__":
    main()
