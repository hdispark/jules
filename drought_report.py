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

severity_order = {"정상": 0, "약한가뭄": 1, "보통가뭄": 2, "심한가뭄": 3, "극심한가뭄": 4}

def compare_regions(old, new):
    new_regions = set(new.keys()) - set(old.keys())
    released = set(old.keys()) - set(new.keys())
    worsened = []
    improved = []
    for r in set(old.keys()) & set(new.keys()):
        old_sev = severity_order[old[r]]
        new_sev = severity_order[new[r]]
        if new_sev > old_sev:
            worsened.append((r, old[r], new[r]))
        elif new_sev < old_sev:
            improved.append((r, old[r], new[r]))
    return new_regions, released, worsened, improved

def map_region(brtc):
    mapping = {
        "서울·인천·경기도": "수도권",
        "강원특별자치도": "강원",
        "대전·세종·충청남도": "충남",
        "충청북도": "충북",
        "광주·전라남도": "전남광주",
        "전북특별자치도": "전북",
        "대구·경상북도": "대경권",
        "부산·울산·경상남도": "부울경",
        "제주특별자치도": "제주"
    }
    return mapping.get(brtc, brtc)

def format_change(diff):
    if diff > 0:
        return f"+{diff}"
    elif diff < 0:
        return f"{diff}"
    else:
        return "-"

def main():
    target_str = "2026-09-14"
    target_date = datetime.strptime(target_str, "%Y-%m-%d")

    print(f"Fetching data for {target_str}...")

    # 30 days of data + history backward
    daily_data = {}
    for i in range(31):
        dt = target_date - timedelta(days=i)
        dt_str = dt.strftime("%Y%m%d")
        data = fetch_drought_data(dt_str)
        daily_data[i] = get_drought_regions(data)
        time.sleep(0.1)

    today_regions = daily_data[0]
    yest_regions = daily_data[1]

    # For duration tracking
    current_active = set(today_regions.keys())
    history = {region: [(target_date, today_regions[region])] for region in current_active}

    days_backward = 0
    while current_active:
        days_backward += 1
        check_date = target_date - timedelta(days=days_backward)

        if days_backward <= 30:
            drought_regions_on_date = daily_data[days_backward]
        else:
            data = fetch_drought_data(check_date.strftime("%Y%m%d"))
            drought_regions_on_date = get_drought_regions(data)
            time.sleep(0.05)

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

    report = []

    # ① 일일 요약(1페이지)
    report.append("① 일일 요약(1페이지)\n")
    report.append("관리자가 가장 먼저 보는 페이지\n")
    report.append("기상가뭄 일일 현황\n")
    report.append(f"기준시각 : {target_date.strftime('%Y.%m.%d')} 10:00\n")

    def count_by_level(regs):
        c = {"약한가뭄": 0, "보통가뭄": 0, "심한가뭄": 0, "극심한가뭄": 0}
        for v in regs.values():
            if v in c: c[v] += 1
        return c

    tc = count_by_level(today_regions)
    yc = count_by_level(yest_regions)

    report.append("구분\t전일\t금일\t증감")
    report.append(f"전체 가뭄지역\t{len(yest_regions)}\t{len(today_regions)}\t{format_change(len(today_regions) - len(yest_regions))}")
    report.append(f"약한가뭄\t{yc['약한가뭄']}\t{tc['약한가뭄']}\t{format_change(tc['약한가뭄'] - yc['약한가뭄'])}")
    report.append(f"보통가뭄\t{yc['보통가뭄']}\t{tc['보통가뭄']}\t{format_change(tc['보통가뭄'] - yc['보통가뭄'])}")
    report.append(f"심한가뭄\t{yc['심한가뭄']}\t{tc['심한가뭄']}\t{format_change(tc['심한가뭄'] - yc['심한가뭄'])}")

    report.append("\n주요 변화\n")

    new_regions, released, worsened, improved = compare_regions(yest_regions, today_regions)

    report.append("신규 발생\n")
    if new_regions:
        for r in new_regions:
            city = r.split()[1] if len(r.split())>1 else r
            report.append(city)
    else:
        report.append("없음")

    report.append("\n단계 상향\n")
    if worsened:
        for r, o, n in worsened:
            city = r.split()[1] if len(r.split())>1 else r
            report.append(f"{city} ({o}→{n})")
    else:
        report.append("없음")

    report.append("\n해제\n")
    if released:
        for r in released:
            city = r.split()[1] if len(r.split())>1 else r
            report.append(city)
    else:
        report.append("없음")

    report.append("\n종합판단\n")
    inc = len(today_regions) - len(yest_regions)
    if inc > 0:
        report.append(f"전일 대비 {inc}개 시군 증가.")
    elif inc < 0:
        report.append(f"전일 대비 {abs(inc)}개 시군 감소.")
    else:
        report.append("전일 대비 변동 없음.")


    # ② 권역별 현황
    report.append("\n② 권역별 현황\n")
    report.append("자동 생성이 쉬움\n")

    def get_prov_counts(regs):
        provs = {}
        for r, l in regs.items():
            p = map_region(r.split()[0])
            if p not in provs:
                provs[p] = {"약한": 0, "보통": 0, "심한": 0, "합계": 0}
            if "약한" in l: provs[p]["약한"] += 1
            if "보통" in l: provs[p]["보통"] += 1
            if "심한" in l or "극심" in l: provs[p]["심한"] += 1
            provs[p]["합계"] += 1
        return provs

    tp = get_prov_counts(today_regions)
    yp = get_prov_counts(yest_regions)

    report.append("권역\t약한\t보통\t합계")
    for p in ["수도권", "강원", "대경권", "부울경", "충북", "충남", "전북", "전남광주", "제주"]:
        if p in tp:
            c = tp[p]
            report.append(f"{p}\t{c['약한']}\t{c['보통']}\t{c['합계']}")

    report.append("\n전일 비교")
    report.append("권역\t전일\t금일\t증감")
    all_p = set(tp.keys()) | set(yp.keys())
    for p in ["수도권", "강원", "대경권", "부울경", "충북", "충남", "전북", "전남광주", "제주"]:
        if p in all_p:
            t_tot = tp.get(p, {}).get("합계", 0)
            y_tot = yp.get(p, {}).get("합계", 0)
            report.append(f"{p}\t{y_tot}\t{t_tot}\t{format_change(t_tot - y_tot)}")

    # ③ 변화지역 분석
    report.append("\n③ 변화지역 분석\n")
    report.append("실무자가 가장 좋아하는 부분\n")

    report.append("신규 가뭄지역")
    if new_regions:
        for r in new_regions:
            city = r.split()[1] if len(r.split())>1 else r
            report.append(city)
    else:
        report.append("없음")

    report.append("해제지역")
    if released:
        for r in released:
            city = r.split()[1] if len(r.split())>1 else r
            report.append(city)
    else:
        report.append("없음")

    report.append("단계 상향")
    if worsened:
        for r, o, n in worsened:
            city = r.split()[1] if len(r.split())>1 else r
            report.append(city)
            short_o = o.replace("가뭄","")
            short_n = n.replace("가뭄","")
            report.append(f"{short_o} → {short_n}")
    else:
        report.append("없음")

    report.append("단계 완화")
    if improved:
        for r, o, n in improved:
            city = r.split()[1] if len(r.split())>1 else r
            report.append(city)
            short_o = o.replace("가뭄","")
            short_n = n.replace("가뭄","")
            report.append(f"{short_o} → {short_n}")
    else:
        report.append("없음")

    # ④ 최근 7일 추세
    report.append("\n④ 최근 7일 추세\n")
    report.append("매우 중요\n")
    report.append("전국 가뭄 시군 수")
    report.append("날짜\t시군수")

    counts_7d = []
    dates_7d = []
    for i in range(6, -1, -1):
        dt = target_date - timedelta(days=i)
        cnt = len(daily_data[i])
        report.append(f"{dt.month}/{dt.day}\t{cnt}")
        counts_7d.append(cnt)
        dates_7d.append(f"{dt.month}/{dt.day}")

    report.append("그래프")

    max_c = max(counts_7d)
    min_c = min(counts_7d)
    top = ((max_c // 5) + 1) * 5
    bottom = (min_c // 5) * 5

    for y in range(top, bottom - 1, -5):
        line = f"{y:2d} |"
        for i, c in enumerate(counts_7d):
            if c >= y and c < y+5:
                line += " " * 4 + "●"
            elif y == top and c >= y:
                line += " " * 4 + "●"
            else:
                line += " " * 5
        report.append(line.rstrip())

    # ⑤ 위험지역 TOP 10
    report.append("\n⑤ 위험지역 TOP 10\n")
    report.append("실제 업무에서 매우 유용\n")
    report.append("단순 가뭄 발생보다\n")
    report.append('"얼마나 오래 지속되는가"\n')
    report.append("가 중요\n")

    report.append("시군\t현재등급\t지속일수")
    sorted_durations = sorted(durations.items(), key=lambda x: -x[1])
    for r, d in sorted_durations[:10]:
        city = r.split()[1] if len(r.split())>1 else r
        lvl = today_regions[r]
        short_lvl = lvl.replace("가뭄", "")
        report.append(f"{city}\t{short_lvl}\t{d}일")

    report.append("\n이 표는 시간이 갈수록 가치가 커짐\n")

    # ⑥ 장기추세 분석
    report.append("⑥ 장기추세 분석\n")
    report.append("월간·분기용\n")

    counts_30d = [len(daily_data[i]) for i in range(30)]
    max_30 = max(counts_30d)
    min_30 = min(counts_30d)
    avg_30 = sum(counts_30d) // 30

    report.append("최근 30일")
    report.append(f"최대 발생 : {max_30}개")
    report.append(f"최소 발생 : {min_30}개")
    report.append(f"평균 발생 : {avg_30}개")

    report.append("증가속도")
    inc_7 = len(today_regions) - len(daily_data[7])
    inc_30 = len(today_regions) - len(daily_data[30])

    report.append(f"최근 7일 증가 : {'+' if inc_7 > 0 else ''}{inc_7}")
    report.append(f"최근 30일 증가 : {'+' if inc_30 > 0 else ''}{inc_30}")

    report.append("권역별 확대속도")
    tp30 = get_prov_counts(daily_data[30])
    for p in ["수도권", "강원", "대경권", "부울경", "충북", "충남", "전북", "전남광주", "제주"]:
        if p in all_p:
            t_tot = tp.get(p, {}).get("합계", 0)
            t30_tot = tp30.get(p, {}).get("합계", 0)
            diff = t_tot - t30_tot
            report.append(f"{p} {'+' if diff > 0 else ''}{diff}")

    with open("report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print("Report written to report.txt")

if __name__ == "__main__":
    main()
