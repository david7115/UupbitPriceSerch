import streamlit as st
import requests
from datetime import datetime
import pandas as pd
import plotly.graph_objs as go

# 페이지 설정
st.set_page_config(
    page_title="업비트 코인 실시간 시세조회 _ Wis David",
    page_icon="📈",
    layout="wide"
)

# 타이틀
st.markdown("""
    <h2 style="font-size:28px; margin-bottom:0;">💹 업비트 코인 실시간 시세조회 _ Wis David</h2>
    <p style="font-size:14px; color:gray;">실시간 시세, 등락률, 포트폴리오 계산기, 캔들차트를 제공합니다.</p>
""", unsafe_allow_html=True)

# 마켓 목록
@st.cache_data(ttl=3600)
def get_markets():
    url = "https://api.upbit.com/v1/market/all"
    res = requests.get(url)
    markets = res.json()
    return {
        m["market"]: m["korean_name"]
        for m in markets if m["market"].startswith("KRW-")
    }

markets_dict = get_markets()

# 캔들 주기 매핑
interval_map = {
    "1분": ("minutes", 1),
    "3분": ("minutes", 3),
    "5분": ("minutes", 5),
    "10분": ("minutes", 10),
    "30분": ("minutes", 30),
    "1시간": ("minutes", 60),
    "일": ("days", None),
    "주": ("weeks", None),
    "월": ("months", None)
}

# 차트 주기 선택
interval = st.selectbox("🕰️ 차트 주기", list(interval_map.keys()), index=0)

# 캔들 데이터 불러오기
def get_candle_data(market, chart_type, unit=None, count=50):
    if chart_type == "minutes":
        url = f"https://api.upbit.com/v1/candles/minutes/{unit}"
    elif chart_type == "days":
        url = "https://api.upbit.com/v1/candles/days"
    elif chart_type == "weeks":
        url = "https://api.upbit.com/v1/candles/weeks"
    elif chart_type == "months":
        url = "https://api.upbit.com/v1/candles/months"
    else:
        return pd.DataFrame()

    params = {"market": market, "count": count}
    res = requests.get(url, params=params)
    candles = res.json()
    candles.reverse()

    df = pd.DataFrame({
        "시간": [c["candle_date_time_kst"] for c in candles],
        "시가": [c["opening_price"] for c in candles],
        "고가": [c["high_price"] for c in candles],
        "저가": [c["low_price"] for c in candles],
        "종가": [c["trade_price"] for c in candles],
        "거래량": [c["candle_acc_trade_volume"] for c in candles]
    })
    return df

# 현재가 조회
def get_price(market):
    url = "https://api.upbit.com/v1/ticker"
    res = requests.get(url, params={"markets": market})
    return res.json()[0]

# 사용자 선택
selected_markets = st.multiselect(
    label="조회할 코인을 선택하세요:",
    options=list(markets_dict.keys()),
    format_func=lambda x: f"{markets_dict[x]} ({x})",
    default=["KRW-BTC", "KRW-ETH"]
)

graph_market = st.selectbox("📊 차트를 표시할 코인:", selected_markets)

prev_prices = {}
holdings = {}

# 시간 표시
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.markdown(f"<p style='font-size:13px;'>🕒 현재 시간: {now}</p>", unsafe_allow_html=True)

# 레이아웃 구성
left_col, right_col = st.columns([2, 1])

# 좌측: 캔들 차트
with left_col:
    if graph_market:
        chart_type, unit = interval_map.get(interval, ("minutes", 1))
        df = get_candle_data(graph_market, chart_type, unit)

        st.markdown(f"<h4>{markets_dict[graph_market]} {interval} 캔들 차트</h4>", unsafe_allow_html=True)

        fig = go.Figure(data=[
            go.Candlestick(
                x=df["시간"],
                open=df["시가"],
                high=df["고가"],
                low=df["저가"],
                close=df["종가"],
                increasing_line_color='red',
                decreasing_line_color='blue'
            )
        ])
        fig.update_layout(xaxis_rangeslider_visible=False, height=400)
        st.plotly_chart(fig, use_container_width=True)

# 우측: 실시간 시세 및 포트폴리오 계산기
with right_col:
    for i, market in enumerate(selected_markets):
        coin_name = markets_dict[market]
        price_info = get_price(market)
        current_price = price_info["trade_price"]
        prev_price = price_info["prev_closing_price"]
        change_rate = ((current_price - prev_price) / prev_price) * 100

        st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:10px; margin-bottom:10px; border-radius:8px;">
            <h5>{coin_name} ({market})</h5>
            💰 현재가: <b>{current_price:,.0f} 원</b><br>
            📈 전일 대비: <span style="color:{'red' if change_rate > 0 else 'blue'}">{change_rate:+.2f}%</span>
        """, unsafe_allow_html=True)

        qty = st.number_input(
            f"{coin_name} 보유 수량",
            min_value=0.0,
            step=0.01,
            key=f"{market}_qty_{i}"
        )
        total = qty * current_price

        st.markdown(f"💼 평가 금액: <b>{total:,.0f} 원</b>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
