import streamlit as st
import requests
from datetime import datetime
import time
import pandas as pd
import plotly.graph_objs as go

st.set_page_config(
    page_title="업비트 코인 실시간 시세조회 _ Wis David",
    page_icon="📈",
    layout="wide"
)

# 제목
st.markdown("<h2 style='margin-bottom: 0;'>💹 업비트 코인 실시간 시세조회 _ Wis David</h2>", unsafe_allow_html=True)
st.caption("실시간 시세, 등락률, 포트폴리오 계산기와 그래프를 함께 제공합니다.")

# ✅ 마켓 불러오기
@st.cache_data(ttl=3600)
def get_markets():
    url = "https://api.upbit.com/v1/market/all"
    try:
        res = requests.get(url)
        res.raise_for_status()
        return {
            m["market"]: m["korean_name"]
            for m in res.json()
            if m["market"].startswith("KRW-")
        }
    except:
        return {}

markets_dict = get_markets()

# ✅ 선택
selected_markets = st.multiselect(
    label="조회할 코인을 선택하세요:",
    options=list(markets_dict.keys()),
    format_func=lambda x: f"{markets_dict[x]} ({x})",
    default=["KRW-BTC", "KRW-ETH"],
    label_visibility="collapsed"
)

# ✅ 초기화
prev_prices = {m: None for m in selected_markets}
price_logs = {m: [] for m in selected_markets}
holdings = {m: 0 for m in selected_markets}

time_placeholder = st.empty()

# ✅ 가격 조회 함수
def get_price(market):
    url = "https://api.upbit.com/v1/ticker"
    try:
        res = requests.get(url, params={"markets": market})
        res.raise_for_status()
        return res.json()[0]
    except:
        return None

# ✅ 실시간 루프
if selected_markets:
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        time_placeholder.markdown(f"🕒 **현재 시간:** `{now}`")

        for market in selected_markets:
            coin_name = markets_dict[market]
            data = get_price(market)

            if data:
                current_price = data["trade_price"]
                prev_close = data["prev_closing_price"]
                change_rate = ((current_price - prev_close) / prev_close) * 100

                price_logs[market].append({"시간": now, "가격": current_price})
                if len(price_logs[market]) > 30:
                    price_logs[market].pop(0)

                # ✅ 카드형 박스 시작
                st.markdown(
                    f"""
                    <div style="background-color:#f8f9fa; padding:20px; border-radius:10px; margin-bottom:20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                        <h4 style="margin-bottom:10px;">📌 {coin_name} ({market})</h4>
                    """,
                    unsafe_allow_html=True
                )

                # 실시간 가격 및 등락률
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.metric(label="현재가", value=f"{current_price:,.0f} 원", delta=f"{change_rate:+.2f}%")
                with col2:
                    qty = st.number_input(f"{coin_name} 보유 수량", min_value=0.0, value=holdings[market], step=0.01, key=f"{market}_qty")
                    holdings[market] = qty
                    st.write(f"💼 평가금액: `{qty * current_price:,.0f}` 원")

                # ✅ 실시간 그래프
                df = pd.DataFrame(price_logs[market])
                fig = go.Figure(data=go.Scatter(x=df["시간"], y=df["가격"], mode="lines+markers"))
                fig.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig, use_container_width=True)

                # ✅ 카드형 박스 닫기
                st.markdown("</div>", unsafe_allow_html=True)

            else:
                st.error(f"{coin_name} 시세를 불러올 수 없습니다.")

        time.sleep(3)
