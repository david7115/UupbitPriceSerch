import streamlit as st
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="업비트 코인 실시간 시세조회 _ Wis David", page_icon="📈")

# 제목
st.title("💹 업비트 코인 실시간 시세조회 _ Wis David")
st.markdown("업비트 Open API를 활용한 실시간 시세 확인 웹앱입니다.")

# 코인 선택
coin = st.selectbox(
    "📌 조회할 코인을 선택하세요:",
    options=["KRW-BTC", "KRW-ETH", "KRW-ONDO"]
)

# 시세 불러오기 함수
def get_price(market):
    url = "https://api.upbit.com/v1/ticker"
    params = {"markets": market}
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        data = res.json()[0]
        return {
            "현재가": data["trade_price"],
            "고가": data["high_price"],
            "저가": data["low_price"],
            "24시간 거래량": data["acc_trade_volume_24h"]
        }
    except:
        return None

# 표시 영역 만들기
time_box = st.empty()
price_box = st.empty()
diff_box = st.empty()

# 시세 비교를 위한 변수
prev_price = None

# 자동 갱신 루프
while True:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    time_box.markdown(f"🕒 **현재 시간:** `{now}`")

    data = get_price(coin)

    if data:
        current_price = data["현재가"]

        # 현재가 표시
        price_box.metric(
            label=f"💰 현재가 ({coin})",
            value=f"{current_price:,.0f} 원"
        )

        # 전 가격과 비교
        if prev_price is not None:
            diff = current_price - prev_price
            arrow = "🔺" if diff > 0 else ("🔻" if diff < 0 else "⏺️")
            diff_text = f"{arrow} {abs(diff):,.0f} 원"
            diff_box.markdown(f"**가격 변화:** {diff_text}")
        else:
            diff_box.markdown("🔄 가격 변화: 데이터 수집 중...")

        prev_price = current_price

    else:
        price_box.error("시세 정보를 가져올 수 없습니다.")
        diff_box.empty()

    time.sleep(1)
