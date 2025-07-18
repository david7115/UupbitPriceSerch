import streamlit as st
import requests

st.title("💰 실시간 비트코인 시세")
url = "https://api.upbit.com/v1/ticker?markets=KRW-BTC"
res = requests.get(url)
if res.status_code == 200:
    price = res.json()[0]['trade_price']
    st.metric("현재가", f"{price:,.0f} 원")
else:
    st.error("시세를 불러올 수 없습니다.")
