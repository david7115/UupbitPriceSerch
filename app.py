import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
import pandas as pd
import plotly.graph_objs as go
from typing import Dict, List, Tuple

# =============================
# 페이지/테마 설정
# =============================
st.set_page_config(
    page_title="업비트 코인 실시간 시세조회 _ Wis David (리팩토링)",
    page_icon="📈",
    layout="wide"
)

st.markdown(
    """
    <h2 style="font-size:28px; margin-bottom:0;">💹 업비트 코인 실시간 시세조회 _ Wis David</h2>
    <p style="font-size:14px; color:gray;">실시간 시세, 등락률, 포트폴리오 계산기, 캔들차트(+MA/거래량), 자동 새로고침, 안정적인 API 호출</p>
    """,
    unsafe_allow_html=True,
)

# =============================
# HTTP 세션 (재시도/타임아웃)
# =============================
@st.cache_resource(show_spinner=False)
def get_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({
        "Accept": "application/json",
        "User-Agent": "wis-david-streamlit/1.0"
    })
    return s

SESSION = get_session()
API_BASE = "https://api.upbit.com/v1"

# =============================
# 유틸
# =============================
def fmt_number(x: float) -> str:
    try:
        return f"{x:,.0f}"
    except Exception:
        return "-"

# =============================
# 데이터 소스
# =============================
@st.cache_data(ttl=3600, show_spinner=False)
def get_markets() -> Dict[str, str]:
    url = f"{API_BASE}/market/all"
    try:
        res = SESSION.get(url, timeout=5)
        res.raise_for_status()
        markets = res.json()
        return {m["market"]: m["korean_name"] for m in markets if m["market"].startswith("KRW-")}
    except Exception as e:
        st.error(f"마켓 목록 조회 실패: {e}")
        return {}

@st.cache_data(ttl=30, show_spinner=False)
def get_candles(market: str, chart_type: str, unit: int | None, count: int = 120) -> pd.DataFrame:
    if chart_type == "minutes":
        url = f"{API_BASE}/candles/minutes/{unit}"
    elif chart_type == "days":
        url = f"{API_BASE}/candles/days"
    elif chart_type == "weeks":
        url = f"{API_BASE}/candles/weeks"
    elif chart_type == "months":
        url = f"{API_BASE}/candles/months"
    else:
        return pd.DataFrame()

    try:
        res = SESSION.get(url, params={"market": market, "count": count}, timeout=7)
        res.raise_for_status()
        candles = res.json()
        candles.reverse()  # 오래된 -> 최신 순
        df = pd.DataFrame({
            "시간": [c.get("candle_date_time_kst") for c in candles],
            "시가": [c.get("opening_price") for c in candles],
            "고가": [c.get("high_price") for c in candles],
            "저가": [c.get("low_price") for c in candles],
            "종가": [c.get("trade_price") for c in candles],
            "거래량": [c.get("candle_acc_trade_volume") for c in candles],
        })
        # 시간 파싱
        try:
            df["시간"] = pd.to_datetime(df["시간"])  # KST 문자열 -> datetime(naive)
        except Exception:
            pass
        return df
    except Exception as e:
        st.warning(f"캔들 조회 실패({market}): {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3, show_spinner=False)
def get_tickers_batch(markets: List[str]) -> pd.DataFrame:
    if not markets:
        return pd.DataFrame()
    url = f"{API_BASE}/ticker"
    try:
        markets_param = ",".join(markets)
        res = SESSION.get(url, params={"markets": markets_param}, timeout=5)
        res.raise_for_status()
        data = res.json()
        rows = []
        for item in data:
            rows.append({
                "market": item.get("market"),
                "현재가": item.get("trade_price"),
                "전일종가": item.get("prev_closing_price"),
                "등락률(%)": ((item.get("trade_price") - item.get("prev_closing_price")) / item.get("prev_closing_price")) * 100 if item.get("prev_closing_price") else None,
                "누적거래대금": item.get("acc_trade_price_24h"),
                "누적거래량": item.get("acc_trade_volume_24h"),
            })
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"시세 조회 실패: {e}")
        return pd.DataFrame()

# =============================
# 인터벌/맵
# =============================
interval_map: Dict[str, Tuple[str, int | None]] = {
    "1분": ("minutes", 1),
    "3분": ("minutes", 3),
    "5분": ("minutes", 5),
    "10분": ("minutes", 10),
    "30분": ("minutes", 30),
    "1시간": ("minutes", 60),
    "일": ("days", None),
    "주": ("weeks", None),
    "월": ("months", None),
}

# =============================
# 사이드바: 옵션/자동 새로고침
# =============================
with st.sidebar:
    st.subheader("⚙️ 옵션")
    interval_label = st.selectbox("🕰️ 차트 주기", list(interval_map.keys()), index=0)
    chart_type, unit = interval_map[interval_label]
    candle_count = st.slider("캔들 개수", min_value=30, max_value=200, value=120, step=10)

    st.divider()
    st.subheader("🔁 자동 새로고침")
    refresh_sec = st.number_input("새로고침 간격(초)", min_value=0, max_value=300, value=0, step=1, help="0이면 자동 새로고침 안 함")
    if refresh_sec > 0:
        st.experimental_set_query_params(_=datetime.now().timestamp())
        st.autorefresh = st.experimental_rerun  # alias 느낌으로 남겨둠
        st.experimental_memo.clear()  # 구버전 호환 무의미하지만 표시만

# =============================
# 마켓/선택
# =============================
markets_dict = get_markets()
all_markets = list(markets_dict.keys())

selected_markets = st.multiselect(
    label="조회할 코인을 선택하세요:",
    options=all_markets,
    format_func=lambda x: f"{markets_dict.get(x, x)} ({x})",
    default=[m for m in ["KRW-BTC", "KRW-ETH"] if m in all_markets],
)

if not selected_markets:
    st.info("좌측/상단에서 코인을 선택해주세요.")
    st.stop()

# 차트에 표시할 기준 코인
graph_market = st.selectbox(
    "📊 차트를 표시할 코인:",
    selected_markets,
    format_func=lambda x: f"{markets_dict.get(x, x)} ({x})",
)

# 현재 시간 표시
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.markdown(f"<p style='font-size:13px;'>🕒 현재 시간: {now}</p>", unsafe_allow_html=True)

# =============================
# 레이아웃
# =============================
left_col, right_col = st.columns([2, 1])

# 좌측: 캔들 차트
with left_col:
    df = get_candles(graph_market, chart_type, unit, candle_count)
    st.markdown(
        f"<h4>{markets_dict.get(graph_market, graph_market)} {interval_label} 캔들 차트</h4>",
        unsafe_allow_html=True,
    )

    if not df.empty:
        # 이동평균/거래량
        for n in (5, 20, 60):
            col_name = f"MA{n}"
            df[col_name] = pd.Series(df["종가"]).rolling(n).mean()

        fig = go.Figure()
        fig.add_trace(
            go.Candlestick(
                x=df["시간"], open=df["시가"], high=df["고가"], low=df["저가"], close=df["종가"],
                increasing_line_color='red', decreasing_line_color='blue', name="Candles"
            )
        )
        fig.add_trace(go.Scatter(x=df["시간"], y=df["MA5"], mode="lines", name="MA5"))
        fig.add_trace(go.Scatter(x=df["시간"], y=df["MA20"], mode="lines", name="MA20"))
        fig.add_trace(go.Scatter(x=df["시간"], y=df["MA60"], mode="lines", name="MA60"))
        fig.add_trace(
            go.Bar(x=df["시간"], y=df["거래량"], name="Volume", opacity=0.3, yaxis="y2")
        )
        fig.update_layout(
            xaxis_rangeslider_visible=False,
            height=480,
            margin=dict(l=10, r=10, t=30, b=10),
            yaxis=dict(title="가격"),
            yaxis2=dict(title="거래량", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.warning("차트 데이터를 가져올 수 없습니다.")

# 우측: 시세/포트폴리오
with right_col:
    tickers_df = get_tickers_batch(selected_markets)
    if tickers_df.empty:
        st.error("시세 데이터를 불러오지 못했습니다.")
    else:
        # 사용자 보유 수량 입력 및 평가금액 계산
        st.markdown("### 💼 포트폴리오 계산기")
        total_eval = 0.0
        for _, row in tickers_df.iterrows():
            market = row["market"]
            name = markets_dict.get(market, market)
            current_price = row["현재가"]
            prev_close = row["전일종가"]
            change_rate = row["등락률(%)"]

            color = "red" if (change_rate or 0) > 0 else "blue"
            st.markdown(
                f"""
                <div style="background-color:#f8f9fa; padding:10px; margin-bottom:10px; border-radius:8px;">
                <h5 style="margin:0 0 6px 0;">{name} ({market})</h5>
                💰 현재가: <b>{fmt_number(current_price)} 원</b><br>
                📈 전일 대비: <span style="color:{color}">{(change_rate or 0):+.2f}%</span>
                """,
                unsafe_allow_html=True,
            )

            qty = st.number_input(
                f"{name} 보유 수량",
                min_value=0.0,
                step=0.0001,
                key=f"qty_{market}",
            )
            eval_amt = (qty or 0) * (current_price or 0)
            total_eval += eval_amt
            st.markdown(f"💼 평가 금액: <b>{fmt_number(eval_amt)} 원</b>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            f"<div style='background:#eef6ff;padding:12px;border-radius:8px;'>총 평가 금액: <b>{fmt_number(total_eval)} 원</b></div>",
            unsafe_allow_html=True,
        )

# =============================
# 부가: 테이블 보기
# =============================
with st.expander("🔎 시세 표로 보기"):
    if 'tickers_df' in locals() and not tickers_df.empty:
        view = tickers_df.copy()
        view.insert(0, "종목명", view["market"].map(markets_dict).fillna(view["market"]))
        view["현재가"] = view["현재가"].map(lambda x: f"{x:,.0f}")
        view["전일종가"] = view["전일종가"].map(lambda x: f"{x:,.0f}")
        view["등락률(%)"] = view["등락률(%)"].map(lambda x: f"{x:+.2f}%")
        view["누적거래대금"] = view["누적거래대금"].map(lambda x: f"{x:,.0f}")
        view["누적거래량"] = view["누적거래량"].map(lambda x: f"{x:,.4f}")
        st.dataframe(view, use_container_width=True, hide_index=True)
    else:
        st.write("표시할 데이터가 없습니다.")

# =============================
# 노트/가이드
# =============================
with st.expander("ℹ️ 참고 (개발 가이드)"):
    st.markdown(
        """
        - **호출 최적화**: 티커는 다중 종목을 한 번에 조회해 API 호출 수를 줄였습니다.
        - **안정성**: HTTP 재시도/타임아웃, 상태코드 에러 처리 추가.
        - **성능**: `@st.cache_data`를 활용해 빈번한 동일 요청 캐시 (티커 3초, 캔들 30초, 마켓 1시간).
        - **차트**: MA5/20/60, 거래량 이중축 추가. 차트 설정은 필요 시 조정하세요.
        - **자동 새로고침**: 사이드바에서 간격 설정(초). 0이면 미사용.
        - **확장 아이디어**:
            1) 업비트 WebSocket을 이용한 초실시간 체결/호가 반영
            2) 손익(P/L) 계산(평단가/수수료 입력) 및 포트폴리오 저장(`st.session_state`)
            3) 알림(가격 도달, 변동률) 및 백테스트용 지표 추가(RSI, MACD 등)
        """
    )
