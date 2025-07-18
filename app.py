import streamlit as st
import requests
from datetime import datetime
import time

st.set_page_config(page_title="비트코인 실시간 시세", page_icon="📈")

st.title("💰 비트코인 실시간 시세 조회")
st.markdown("업비트 API를 통해 실시간 시세를 확인할 수 있습니다.")

# 업비트 API 요청 함수
def get_upbit_price():
    url = "https://api.upbit.com/v1/ticker"
    params = {"markets": "KRW-BTC"}
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
    except Exception as e:
        return None

# 자동 갱신 영역
price_placeholder = st.empty()
time_placeholder = st.empty()

# 스트리밍 루프
while True:
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    price_info = get_upbit_price()

    if price_info:
        # 시간 표시
        time_placeholder.markdown(f"🕒 **현재 시간:** `{now}`")
        
        # 가격 표시
        price_placeholder.metric(
            label="📌 현재가 (KRW-BTC)",
            value=f"{price_info['현재가']:,.0f} 원"
        )
    else:
        price_placeholder.error("시세 정보를 가져올 수 없습니다.")
        time_placeholder.empty()

    time.sleep(1)
