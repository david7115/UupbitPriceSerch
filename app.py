"""
Upbit Open API Python client — REST + WebSocket (v1)

✅ 포함 기능(공식 문서 기준)
- 시세(호가/체결/캔들/티커) 조회: /v1/orderbook, /v1/trades/ticks, /v1/candles/*, /v1/ticker, /v1/ticker/all
- 마켓 목록: /v1/market/all
- 자산/계좌: /v1/accounts
- 주문 사전 정보: /v1/orders/chance
- 주문/취소/조회: /v1/orders (POST), /v1/order (DELETE), /v1/orders/open, /v1/orders/closed, /v1/orders/uuids
- 입금/출금: (조회/주소발급/입금확인/출금요청 등 주요 엔드포인트 래핑)
- WebSocket(퍼블릭: ticker/trade/orderbook/candle, 프라이빗: myOrder/myAsset, 구독목록):
  wss://api.upbit.com/websocket/v1

⚠️ 안전장치
- enable_trading=False(기본값) 인 경우, 주문/취소/출금 계열 메서드는 호출 시 예외를 발생시킵니다.
- 실제 키를 환경변수 또는 인자로 주입하세요. (ACCESS_KEY, SECRET_KEY)
- 주문/출금은 법/내부통제/리스크 정책을 반드시 준수하세요.

필요 패키지
    pip install requests PyJWT websocket-client

참고
- 모든 사설(서명) 요청은 JWT(HS256) + query_hash(SHA512) 를 사용합니다.
- POST/DELETE 포함, 파라미터가 존재하는 요청은 query_hash를 포함해야 합니다.
- WebSocket 프라이빗 스트림(myOrder/myAsset)은 동일한 Authorization 헤더를 사용합니다.

작성: 2025-08-20
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union, Callable

import jwt  # PyJWT
import requests
from urllib.parse import urlencode

try:
    import websocket  # websocket-client
except Exception:  # pragma: no cover
    websocket = None  # type: ignore


class UpbitAPIError(RuntimeError):
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self.payload = payload
        message = f"Upbit API Error {status_code}: {payload}"
        super().__init__(message)


@dataclass
class UpbitClientConfig:
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    base_url: str = "https://api.upbit.com"  # 지역에 따라 sg-api.upbit.com 등으로 변경 가능
    enable_trading: bool = False  # 주문/취소/출금 등 위험 동작 보호
    timeout: int = 30
    user_agent: str = (
        "UpbitPythonClient/1.0 (+https://github.com/)"
    )


class UpbitClient:
    """Upbit Open API v1 Python Client (REST + WebSocket)

    공식 문서에 맞춰 주요 엔드포인트를 메서드로 래핑했습니다.
    - 사설 요청: JWT(HS256) + query_hash(SHA512)
    - 퍼블릭 요청: 서명 불필요
    """

    def __init__(self, config: Optional[UpbitClientConfig] = None, **kwargs):
        if config is None:
            config = UpbitClientConfig(**kwargs)
        # 환경변수 fallback
        self.access_key = config.access_key or os.getenv("UPBIT_ACCESS_KEY")
        self.secret_key = config.secret_key or os.getenv("UPBIT_SECRET_KEY")
        self.base_url = config.base_url.rstrip("/")
        self.enable_trading = bool(config.enable_trading)
        self.timeout = int(config.timeout)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.user_agent,
            "Accept": "application/json",
        })

    # =============== 내부 유틸 ===============
    def _jwt_headers(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        if not self.access_key or not self.secret_key:
            raise RuntimeError("사설 요청에는 access_key/secret_key가 필요합니다.")

        payload = {
            "access_key": self.access_key,
            "nonce": str(uuid.uuid4()),
        }
        if params:
            # Upbit는 'query string' 을 SHA512로 해시하여 query_hash로 포함
            # dict -> stable query string (키 정렬 + doseq)
            q = urlencode(sorted(self._flatten(params).items()), doseq=True)
            query_hash = hashlib.sha512(q.encode()).hexdigest()
            payload.update({
                "query_hash": query_hash,
                "query_hash_alg": "SHA512",
            })
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _flatten(d: Dict[str, Any], parent_key: str = "", sep: str = "") -> Dict[str, Any]:
        """중첩 dict 방지용 간단 플래튼 (values가 list인 경우 doseq로 처리)
        Upbit 파라미터는 대부분 1-depth이므로 기본 그대로 반환.
        """
        return d

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        private: bool = False,
        send_json_for_post: bool = True,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers: Dict[str, str] = {}
        if private:
            headers.update(self._jwt_headers(params or {}))

        # 요청 전송
        try:
            if method in ("GET", "DELETE"):
                resp = self.session.request(
                    method, url, params=params, headers=headers, timeout=self.timeout
                )
            else:  # POST/PUT
                if send_json_for_post:
                    headers.setdefault("Content-Type", "application/json")
                    resp = self.session.request(
                        method, url, json=params or {}, headers=headers, timeout=self.timeout
                    )
                else:
                    # 일부 환경에서 application/x-www-form-urlencoded 를 선호할 경우
                    resp = self.session.request(
                        method, url, data=params or {}, headers=headers, timeout=self.timeout
                    )
        except requests.RequestException as e:
            raise RuntimeError(f"HTTP 요청 실패: {e}")

        # 오류 처리
        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except Exception:
                payload = resp.text
            raise UpbitAPIError(resp.status_code, payload)

        # JSON 파싱
        if resp.headers.get("Content-Type", "").startswith("application/json"):
            return resp.json()
        # 텍스트/기타
        return resp.text

    # =============== 퍼블릭(시세) API ===============
    def market_all(self) -> List[Dict[str, Any]]:
        """마켓 목록 조회 (/v1/market/all)"""
        return self._request("GET", "/v1/market/all")

    def ticker(self, markets: Union[str, Iterable[str]]) -> List[Dict[str, Any]]:
        """개별/복수 마켓 현재가 (/v1/ticker)"""
        if not isinstance(markets, str):
            markets = ",".join(markets)
        return self._request("GET", "/v1/ticker", params={"markets": markets})

    def ticker_by_quotes(self, quote_currencies: Union[str, Iterable[str]]) -> List[Dict[str, Any]]:
        """호가통화 기준 전체 티커 스냅샷 (/v1/ticker/all)"""
        if not isinstance(quote_currencies, str):
            quote_currencies = ",".join(quote_currencies)
        return self._request("GET", "/v1/ticker/all", params={"quoteCurrencies": quote_currencies})

    def orderbook(self, markets: Union[str, Iterable[str]], level: Optional[float] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if not isinstance(markets, str):
            markets = ",".join(markets)
        params["markets"] = markets
        if level is not None:
            params["level"] = level
        return self._request("GET", "/v1/orderbook", params=params)

    def supported_orderbook_levels(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/v1/orderbook/supported_levels")

    def trades_ticks(
        self,
        market: str,
        *,
        to: Optional[str] = None,
        count: Optional[int] = None,
        cursor: Optional[str] = None,
        daysAgo: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"market": market}
        if to: params["to"] = to
        if count: params["count"] = count
        if cursor: params["cursor"] = cursor
        if daysAgo: params["daysAgo"] = daysAgo
        return self._request("GET", "/v1/trades/ticks", params=params)

    def candles_minutes(self, unit: int, market: str, *, to: Optional[str] = None, count: Optional[int] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"market": market}
        if to: params["to"] = to
        if count: params["count"] = count
        return self._request("GET", f"/v1/candles/minutes/{unit}", params=params)

    def candles_days(self, market: str, *, to: Optional[str] = None, count: Optional[int] = None, convertingPriceUnit: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"market": market}
        if to: params["to"] = to
        if count: params["count"] = count
        if convertingPriceUnit: params["convertingPriceUnit"] = convertingPriceUnit
        return self._request("GET", "/v1/candles/days", params=params)

    def candles_weeks(self, market: str, *, to: Optional[str] = None, count: Optional[int] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"market": market}
        if to: params["to"] = to
        if count: params["count"] = count
        return self._request("GET", "/v1/candles/weeks", params=params)

    def candles_months(self, market: str, *, to: Optional[str] = None, count: Optional[int] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"market": market}
        if to: params["to"] = to
        if count: params["count"] = count
        return self._request("GET", "/v1/candles/months", params=params)

    def candles_years(self, market: str, *, to: Optional[str] = None, count: Optional[int] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"market": market}
        if to: params["to"] = to
        if count: params["count"] = count
        return self._request("GET", "/v1/candles/years", params=params)

    # =============== 사설(계정/주문/입출금) API ===============
    def accounts(self) -> List[Dict[str, Any]]:
        """보유 자산 조회 (/v1/accounts)"""
        return self._request("GET", "/v1/accounts", private=True)

    def orders_chance(self, market: str) -> Dict[str, Any]:
        return self._request("GET", "/v1/orders/chance", params={"market": market}, private=True)

    # ----- 주문 -----
    def place_order(
        self,
        *,
        market: str,
        side: str,  # 'bid' or 'ask'
        ord_type: str,  # 'limit' | 'price' | 'market' | 'best'
        volume: Optional[Union[str, float]] = None,
        price: Optional[Union[str, float]] = None,
        identifier: Optional[str] = None,
        time_in_force: Optional[str] = None,  # 'ioc' | 'fok' | 'post_only'
        smp_type: Optional[str] = None,       # 'reduce' | 'cancel_maker' | 'cancel_taker'
    ) -> Dict[str, Any]:
        if not self.enable_trading:
            raise PermissionError("enable_trading=True 로 생성해야 주문이 활성화됩니다.")
        params: Dict[str, Any] = {
            "market": market,
            "side": side,
            "ord_type": ord_type,
        }
        if volume is not None:
            params["volume"] = str(volume)
        if price is not None:
            params["price"] = str(price)
        if identifier:
            params["identifier"] = identifier
        if time_in_force:
            params["time_in_force"] = time_in_force
        if smp_type:
            params["smp_type"] = smp_type
        return self._request("POST", "/v1/orders", params=params, private=True)

    def cancel_order(self, *, uuid: Optional[str] = None, identifier: Optional[str] = None) -> Dict[str, Any]:
        if not self.enable_trading:
            raise PermissionError("enable_trading=True 로 생성해야 취소가 활성화됩니다.")
        if not uuid and not identifier:
            raise ValueError("uuid 또는 identifier 중 하나는 필요합니다.")
        params: Dict[str, Any] = {}
        if uuid: params["uuid"] = uuid
        if identifier: params["identifier"] = identifier
        # DELETE 는 쿼리스트링 사용
        return self._request("DELETE", "/v1/order", params=params, private=True)

    def order(self, *, uuid: Optional[str] = None, identifier: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if uuid: params["uuid"] = uuid
        if identifier: params["identifier"] = identifier
        return self._request("GET", "/v1/order", params=params, private=True)

    def orders_open(self, *, market: Optional[str] = None, state: Optional[str] = None, states: Optional[List[str]] = None, page: Optional[int] = None, limit: Optional[int] = None, order_by: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if market: params["market"] = market
        if state: params["state"] = state
        if states: params["states"] = states
        if page: params["page"] = page
        if limit: params["limit"] = limit
        if order_by: params["order_by"] = order_by
        return self._request("GET", "/v1/orders/open", params=params, private=True)

    def orders_closed(self, *, market: Optional[str] = None, state: Optional[str] = None, states: Optional[List[str]] = None, start_time: Optional[str] = None, end_time: Optional[str] = None, limit: Optional[int] = None, order_by: Optional[str] = None, page: Optional[int] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if market: params["market"] = market
        if state: params["state"] = state
        if states: params["states"] = states
        if start_time: params["start_time"] = start_time
        if end_time: params["end_time"] = end_time
        if limit: params["limit"] = limit
        if order_by: params["order_by"] = order_by
        if page: params["page"] = page
        return self._request("GET", "/v1/orders/closed", params=params, private=True)

    def orders_by_ids(self, *, market: Optional[str] = None, uuids: Optional[List[str]] = None, identifiers: Optional[List[str]] = None, order_by: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if market: params["market"] = market
        if uuids: params["uuids"] = uuids
        if identifiers: params["identifiers"] = identifiers
        if order_by: params["order_by"] = order_by
        return self._request("GET", "/v1/orders/uuids", params=params, private=True)

    def cancel_orders_batch(self, *, market: str, count: int, order_by: str = "desc") -> Dict[str, Any]:
        if not self.enable_trading:
            raise PermissionError("enable_trading=True 로 생성해야 취소가 활성화됩니다.")
        params = {"market": market, "count": count, "order_by": order_by}
        return self._request("DELETE", "/v1/orders", params=params, private=True)

    def cancel_orders_list(self, *, market: str, uuids: Optional[List[str]] = None, identifiers: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self.enable_trading:
            raise PermissionError("enable_trading=True 로 생성해야 취소가 활성화됩니다.")
        params: Dict[str, Any] = {"market": market}
        if uuids: params["uuids"] = uuids
        if identifiers: params["identifiers"] = identifiers
        return self._request("DELETE", "/v1/orders/list", params=params, private=True)

    # ----- 출금 / 입금 -----
    def withdraws(self, **kwargs) -> List[Dict[str, Any]]:
        """출금 목록 조회 (/v1/withdraws) — kwargs로 상태/마켓/페이징 등 전달"""
        return self._request("GET", "/v1/withdraws", params=kwargs or None, private=True)

    def withdraw(self, *, currency: str, amount: Union[str, float], address: str, net_type: Optional[str] = None, secondary_address: Optional[str] = None) -> Dict[str, Any]:
        if not self.enable_trading:
            raise PermissionError("enable_trading=True 로 생성해야 출금이 활성화됩니다.")
        params: Dict[str, Any] = {
            "currency": currency,
            "amount": str(amount),
            "address": address,
        }
        if net_type: params["net_type"] = net_type
        if secondary_address: params["secondary_address"] = secondary_address
        return self._request("POST", "/v1/withdraws/coin", params=params, private=True)

    def withdraw_krw(self, *, amount: Union[str, float]) -> Dict[str, Any]:
        if not self.enable_trading:
            raise PermissionError("enable_trading=True 로 생성해야 출금이 활성화됩니다.")
        params = {"amount": str(amount)}
        return self._request("POST", "/v1/withdraws/krw", params=params, private=True)

    def withdraw_allowlisted_addresses(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/v1/withdraws/coin_addresses", private=True)

    def deposits(self, **kwargs) -> List[Dict[str, Any]]:
        return self._request("GET", "/v1/deposits", params=kwargs or None, private=True)

    def deposit(self, *, amount: Union[str, float]) -> Dict[str, Any]:
        """원화(KRW) 입금 요청(일부 계정/등급에서만 지원)."""
        params = {"amount": str(amount)}
        return self._request("POST", "/v1/deposits/krw", params=params, private=True)

    def generate_deposit_address(self, *, currency: str, net_type: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"currency": currency}
        if net_type: params["net_type"] = net_type
        return self._request("POST", "/v1/deposits/generate_coin_address", params=params, private=True)

    def deposit_address(self, *, currency: Optional[str] = None, net_type: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if currency: params["currency"] = currency
        if net_type: params["net_type"] = net_type
        return self._request("GET", "/v1/deposits/coin_addresses", params=params, private=True)

    def deposit_address_by_uuid(self, *, uuid: str) -> Dict[str, Any]:
        return self._request("GET", "/v1/deposits/coin_address", params={"uuid": uuid}, private=True)

    def deposit_verify_by_uuid(self, *, uuid: str) -> Dict[str, Any]:
        return self._request("POST", "/v1/deposits/verify", params={"uuid": uuid}, private=True)

    def deposit_verify_by_txid(self, *, txid: str, currency: str) -> Dict[str, Any]:
        return self._request("POST", "/v1/deposits/verify_txid", params={"txid": txid, "currency": currency}, private=True)

    def deposit_available_info(self, *, currency: str) -> Dict[str, Any]:
        return self._request("GET", "/v1/deposits/coin_availability", params={"currency": currency}, private=True)

    # ----- 기타(지갑/키) -----
    def wallet_status(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/v1/status/wallet")

    def api_keys(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/v1/api_keys", private=True)

    # =============== WebSocket ===============
    class _WS:
        def __init__(self, url: str, headers: Dict[str, str]):
            if websocket is None:
                raise RuntimeError("websocket-client 패키지가 필요합니다: pip install websocket-client")
            self.url = url
            self.headers = [f"{k}: {v}" for k, v in headers.items()]
            self._app = None

        def run(
            self,
            messages: List[Dict[str, Any]],
            on_message: Optional[Callable[[bytes], None]] = None,
            on_open: Optional[Callable[[Any], None]] = None,
            on_error: Optional[Callable[[Any, Exception], None]] = None,
            on_close: Optional[Callable[[Any, int, str], None]] = None,
            ping_interval: int = 15,
        ) -> None:
            def _on_message(ws, msg: bytes):
                if on_message:
                    on_message(msg)
                else:
                    print(msg if isinstance(msg, (bytes, bytearray)) else str(msg))

            def _on_open(ws):
                if on_open:
                    on_open(ws)
                # 구독 요청 전송
                ws.send(json.dumps(messages))

            app = websocket.WebSocketApp(
                self.url,
                header=self.headers,
                on_message=_on_message,
                on_open=_on_open,
                on_error=on_error,
                on_close=on_close,
            )
            self._app = app
            app.run_forever(ping_interval=ping_interval)

    def ws_public(self) -> "UpbitClient._WS":
        headers = {}  # 퍼블릭은 헤더 불필요
        return self._WS("wss://api.upbit.com/websocket/v1", headers)

    def ws_private(self) -> "UpbitClient._WS":
        headers = self._jwt_headers({})
        return self._WS("wss://api.upbit.com/websocket/v1/private", headers)

    # 헬퍼: 구독 메시지 빌더
    @staticmethod
    def ws_build_request(
        *,
        types: List[Dict[str, Any]],  # 예: [{"type": "ticker", "codes": ["KRW-BTC"]}]
        ticket: Optional[str] = None,
        format_: str = "DEFAULT",  # 또는 "SIMPLE"
    ) -> List[Dict[str, Any]]:
        msg: List[Dict[str, Any]] = []
        msg.append({"ticket": ticket or str(uuid.uuid4())})
        msg.extend(types)
        msg.append({"format": format_})
        return msg


# ================= 예시 사용법 =================
if __name__ == "__main__":
    # 환경변수로 키를 넣었다고 가정
    client = UpbitClient(UpbitClientConfig(enable_trading=False))

    # 퍼블릭 예시
    markets = client.market_all()
    print("마켓수:", len(markets))
    print("KRW 마켓 예시:", [m for m in markets if m["market"].startswith("KRW-")][:3])

    # 캔들/호가/체결
    print("분봉 1분 KRW-BTC 5개:", client.candles_minutes(1, "KRW-BTC", count=5)[0])
    print("호가 KRW-BTC:", client.orderbook("KRW-BTC")[0]["market"])
    print("최근 체결 KRW-BTC 3개:", client.trades_ticks("KRW-BTC", count=3)[0])

    # 사설(계좌)
    if client.access_key and client.secret_key:
        print("보유자산 샘플:", client.accounts()[:1])
        print("주문가능정보 샘플:", client.orders_chance("KRW-BTC")["market"]["id"])  # 권한/등급 필요

    # WebSocket 퍼블릭 구독 (실행 예)
    # ws = client.ws_public()
    # sub = client.ws_build_request(types=[{"type": "ticker", "codes": ["KRW-BTC", "KRW-ETH"]}], format_="SIMPLE")
    # ws.run(messages=sub)

    # WebSocket 프라이빗 구독 (myOrder/myAsset)
    # ws_p = client.ws_private()
    # sub_p = client.ws_build_request(types=[{"type": "myOrder"}, {"type": "myAsset"}], format_="DEFAULT")
    # ws_p.run(messages=sub_p)
