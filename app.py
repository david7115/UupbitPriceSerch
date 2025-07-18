import streamlit as st
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="업비트 코인 실시간 시세조회 _ Wis David", page_icon="📈", layout="wide")

st.title("💹 업비트 코인 실시간 시세조회 _ Wis David")
st.markdown("업비트 Open API를 통해 실시간으로 코인 가격을 조회합니다.")

# ✅ 전체 마켓 목록 불러오기 (KRW-만 필터링)
@st.cache_data(ttl=3600)
def get_markets():
    url = "https://api.upbit.com/v1/market/all"
    try:
        res = requests.get(url)
        res.raise_for_status()
        markets = res.json()
        return {
            m["market"]: m["korean_name"]
            for m in markets
            if m["market"].startswith("KRW-")
        }
    except:
        return {}

markets_dict = get_markets()

# ✅ 사용자 선택
selected_markets = st.multiselect(
    "✅ 조회할 코인을 선택하세요 (KRW 마켓):",
    options=list(markets_dict.keys()),
    format_func=lambda x: f"{markets_dict[x]} ({x})",
    default=["KRW-BTC", "KRW-ETH"]
)

# ✅ 실시간 데이터 저장용
prev_prices = {m: None for m in selected_markets}
display_boxes = {}

# ✅ 시세 가져오기 함수
def get_price(market):
    url = "https://api.upbit.com/v1/ticker"
    try:
        res = requests.get(url, params={"markets": market})
        res.raise_for_status()
        return res.json()[0]
    except:
        return None

# ✅ 실시간 시세 표시 layout 구성
time_placeholder = st.empty()

if selected_markets:
    cols = st.columns(len(selected_markets))
    for i, market in enumerate(selected_markets):
        display_boxes[market] = cols[i].empty()

# ✅ 실시간 루프 시작
while True:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    time_placeholder.markdown(f"🕒 **현재 시간:** `{now}`")

    if selected_markets:
        cols = st.columns(len(selected_markets))  # 다시 그려도 레이아웃 최적화

        for i, market in enumerate(selected_markets):
            data = get_price(market)
            coin_name = markets_dict.get(market, market)

            with cols[i]:
                if data:
                    current = data["trade_price"]
                    previous = prev_prices[market]
                    delta = None
                    arrow = ""

                    if previous is not None:
                        delta = current - previous
                        if delta > 0:
                            arrow = "🔺"
                        elif delta < 0:
                            arrow = "🔻"
                        else:
                            arrow = "⏺️"

                    # metric 덮어쓰기
                    display_boxes[market].metric(
                        label=f"💰 {coin_name}",
                        value=f"{current:,.0f} 원",
                        delta=f"{arrow} {abs(delta):,.0f} 원" if delta is not None else "데이터 수집 중..."
                    )
                    prev_prices[market] = current
                else:
                    display_boxes[market].error("API 오류")

    time.sleep(1)
