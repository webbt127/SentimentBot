from alpaca_trade_api import REST, Stream
import alpaca_trade_api as tradeapi
import yfinance as yf
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
		stock_info = yf.Ticker(ticker).info
		stock_price = stock_info['regularMarketPrice']
		stock_price_order = stock_price * 0.98
		rest_client.submit_order(symbol=ticker, qty=position.qty, side='sell', type='limit', limit_price=stock_price_order, time_in_force='gtc')
		print("Market Sell Order Submitted!")
