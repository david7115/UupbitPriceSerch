import streamlit as st
import requests
from datetime import datetime
import time

# Streamlit 페이지 설정
st.set_page_config(page_title="업비트 코인 실시간 시세조회 _ Wis David", page_icon="📈")

st.title("💹 업비트 코인 실시간 시세조회 _ Wis David")
st.markdown("업비트 Open API를 통해 실시간으로 코인 가격을 조회합니다.")

# ✅ 1. 업비트 마켓 목록 불러오기 (KRW 마켓만)
@st.cache_data(ttl=3600)
def get_markets():
    url = "https://api.upbit.com/v1/market/all"
    try:
        res = requests.get(url)
        res.raise_for_status()
        markets = res.json()
        krw_markets = [m for m in markets if m['market'].startswith("KRW-")]
        return {
            m['market']: m['korean_name']
            for m in krw_markets
        }
    except:
        return {}

markets_dict = get_markets()

# ✅ 2. 사용자 선택: 복수 선택
selected_markets = st.multiselect(
    "✅ 조회할 코인을 선택하세요 (KRW 마켓):",
    options=list(markets_dict.keys()),
    format_func=lambda x: f"{markets_dict[x]} ({x})",
    default=["KRW-BTC", "KRW-ETH"]
)

# ✅ 3. 시간 및 시세 표시 구역
time_placeholder = st.empty()
cols = st.columns(len(selected_markets)) if selected_markets else []

# ✅ 4. 이전 가격 저장용
prev_prices = {m: None for m in selected_markets}

# ✅ 5. 시세 불러오기 함수
def get_price(market):
    url = "https://api.upbit.com/v1/ticker"
    params = {"markets": market}
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json()[0]
    except:
        return None

# ✅ 6. 자동 갱신 루프
while True:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    time_placeholder.markdown(f"🕒 **현재 시간:** `{now}`")

    for i, market in enumerate(selected_markets):
        data = get_price(market)
        with cols[i]:
            st.markdown(f"### {markets_dict.get(market, market)}")
            if data:
                current = data["trade_price"]
                previous = prev_prices[market]
                diff = None
                arrow = ""

                if previous is not None:
                    diff = current - previous
                    if diff > 0:
                        arrow = "🔺"
                    elif diff < 0:
                        arrow = "🔻"
                    else:
                        arrow = "⏺️"

                st.metric(
                    label="현재가",
                    value=f"{current:,.0f} 원",
                    delta=f"{arrow} {abs(diff):,.0f} 원" if diff is not None else "수집 중..."
                )
                prev_prices[market] = current
            else:
                st.error("시세 정보 불러오기 실패")

    time.sleep(1)
