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

st.markdown("""
    <h2 style="font-size:28px; margin-bottom:0;">💹 업비트 코인 실시간 시세조회 _ Wis David</h2>
    <p style="font-size:14px; color:gray;">실시간 시세, 등락률, 포트폴리오 계산기, 그래프 포함</p>
""", unsafe_allow_html=True)

# ✅ 업비트 마켓 목록
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

# ✅ 과거 차트 데이터 불러오기 (1분봉 기준)
def load_initial_chart_data(market, count=30):
    url = f"https://api.upbit.com/v1/candles/minutes/1"
    params = {"market": market, "count": count}
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        candles = res.json()
        candles.reverse()  # 시간 오름차순 정렬
        return [{"시간": c["candle_date_time_kst"][11:19], "가격": c["trade_price"]} for c in candles]
    except:
        return []

# ✅ 시세 조회 함수
def get_price(market):
    url = "https://api.upbit.com/v1/ticker"
    try:
        res = requests.get(url, params={"markets": market})
        res.raise_for_status()
        return res.json()[0]
    except:
        return None

# ✅ 사용자 코인 선택
selected_markets = st.multiselect(
    label="조회할 코인을 선택하세요:",
    options=list(markets_dict.keys()),
    format_func=lambda x: f"{markets_dict[x]} ({x})",
    default=["KRW-BTC", "KRW-ETH"],
    label_visibility="collapsed"
)

# ✅ 그래프 표시용 코인 선택
graph_market = st.selectbox(
    "📊 차트를 표시할 코인을 선택하세요:",
    options=selected_markets if selected_markets else [],
    format_func=lambda x: markets_dict.get(x, x)
)

# ✅ 상태 초기화
prev_prices = {m: None for m in selected_markets}
price_logs = {m: [] for m in selected_markets}
holdings = {m: 0.0 for m in selected_markets}

# ✅ 차트 초기화 (1분봉 캔들)
for market in selected_markets:
    price_logs[market] = load_initial_chart_data(market)

# ✅ 실시간 루프
if selected_markets:
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(f"<p style='font-size:13px;'>🕒 현재 시간: {now}</p>", unsafe_allow_html=True)

        # 🧭 2단 레이아웃: 왼쪽 그래프 / 오른쪽 시세
        left_col, right_col = st.columns([2, 1])

        # 📈 왼쪽 - 차트
        with left_col:
            if graph_market:
                graph_data = get_price(graph_market)
                if graph_data:
                    price_logs[graph_market].append({"시간": now[11:], "가격": graph_data["trade_price"]})
                    if len(price_logs[graph_market]) > 30:
                        price_logs[graph_market].pop(0)

                    df = pd.DataFrame(price_logs[graph_market])
                    st.markdown(f"<h4 style='font-size:18px;'>{markets_dict[graph_market]} 가격 차트</h4>", unsafe_allow_html=True)
                    fig = go.Figure(data=go.Scatter(x=df["시간"], y=df["가격"], mode="lines+markers"))
                    fig.update_layout(height=400, margin=dict(l=20, r=20, t=30, b=20))
                    st.plotly_chart(fig, use_container_width=True)

        # 💰 오른쪽 - 시세 카드들
        with right_col:
            for i, market in enumerate(selected_markets):
                coin_name = markets_dict.get(market, market)
                data = get_price(market)

                if data:
                    current = data["trade_price"]
                    prev_close = data["prev_closing_price"]
                    change_rate = ((current - prev_close) / prev_close) * 100
                    prev_prices[market] = current

                    st.markdown(
                        f"""
                        <div style="background-color:#f8f9fa; padding:15px; border-radius:8px; margin-bottom:15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                            <h5 style="margin-bottom:8px;">📌 {coin_name} ({market})</h5>
                            <p style="margin:0;">💰 <b style='font-size:20px;'>{current:,.0f} 원</b></p>
                            <p style="margin:0;">📉 등락률: <span style="color:{'red' if change_rate > 0 else 'blue'};'>{change_rate:+.2f}%</span></p>
                        """,
                        unsafe_allow_html=True
                    )

                    qty = st.number_input(
                        f"{coin_name} 보유 수량",
                        min_value=0.0,
                        value=float(holdings[market]),
                        step=0.01,
                        key=f"{market}_qty_{i}"
                    )
                    holdings[market] = qty
                    total = qty * current

                    st.markdown(
                        f"""💼 평가금액: <b style='font-size:16px;'>{total:,.0f} 원</b>""",
                        unsafe_allow_html=True
                    )
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.error(f"{coin_name} 시세를 가져올 수 없습니다.")

        time.sleep(3)
