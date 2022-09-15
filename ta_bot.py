from alpaca_trade_api import REST, Stream
import alpaca_trade_api as tradeapi
from tradingview_ta import TA_Handler, Interval, Exchange

API_KEY = 'PKVLATR3V44A75JDC07W'
API_SECRET = 'ngvSepjmymi5Aj0wn13kU6h1ZJyfzfMkQxfDzvmv'
endpoint = "https://paper-api.alpaca.markets"

rest_client = REST(API_KEY, API_SECRET, endpoint)

while True:
 	api = tradeapi.REST(API_KEY, API_SECRET, endpoint)
	clock = api.get_clock()
 	tickers = api.list_positions()
 	print("Open Positions:", tickers)

	for ticker in tickers:
		ticker_ta = TA_Handler(symbol=ticker, screener="america", exchange="nasdaq", interval=Interval.INTERVAL_1_HOUR)
    		print(ticker_ta.get_analysis().summary)
		position = api.get_position(ticker)
		rest_client.submit_order(symbol=ticker, qty=position.qty, side='sell', type='market', time_in_force='gtc')
		print("Market Sell Order Submitted!")
