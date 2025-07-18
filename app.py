import streamlit as st
import requests

# 페이지 설정
st.set_page_config(page_title="비트코인 시세 조회", page_icon="📈")

# 앱 제목
st.title("💰 비트코인 실시간 시세 조회")
st.markdown("업비트 API를 통해 실시간 시세 정보를 제공합니다.")

# 업비트 Open API 요청
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
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return None

# 시세 가져오기
price_info = get_upbit_price()

# 결과 출력
if price_info:
    st.metric(label="📌 현재가", value=f"{price_info['현재가']:,.0f} 원")
    st.write(f"📈 고가: {price_info['고가']:,.0f} 원")
    st.write(f"📉 저가: {price_info['저가']:,.0f} 원")
    st.write(f"💹 24시간 거래량: {price_info['24시간 거래량']:.3f} BTC")
else:
    st.warning("시세 정보를 가져올 수 없습니다.")

