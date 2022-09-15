from alpaca_trade_api import REST, Stream
import alpaca_trade_api as tradeapi
import time
from tradingview_ta import TA_Handler, Interval, Exchange

API_KEY = 'PKASJ5Y3N7H004MOL0QN'
API_SECRET = 'PuTN34kuictvukT5yTVIevgRsWoK9o60Dzzsz9Co'
endpoint = "https://paper-api.alpaca.markets"

rest_client = REST(API_KEY, API_SECRET, endpoint)
api = tradeapi.REST(API_KEY, API_SECRET, endpoint)
clock = api.get_clock()
position_list = api.list_positions()
position_list_size = len(position_list)
positions = range(0, position_list_size - 1)
while True:
  while position_list_size > 0 and clock.is_open:
    for position in positions:
      ticker = position_list[position].__getattr__('symbol')
      exchange = position_list[position].__getattr__('exchange')
      position_size = api.get_position(ticker)
      position_t = api.get_position(ticker)
      print(position_t.exchange)
      print("Open Positions:", ticker)
      try:
        ticker_ta = TA_Handler(symbol=ticker, screener="america", exchange=exchange, interval=Interval.INTERVAL_1_HOUR)
        summary = ticker_ta.get_analysis().summary
      except Exception as e:
        print("No TA Data Available for", ticker)
      recommendation = summary['RECOMMENDATION']
      print(recommendation)
      if recommendation == 'SELL' or recommendation == 'STRONG_SELL':
        try:
          rest_client.submit_order(symbol=ticker, qty=position_size.qty, side='sell', type='market', time_in_force='gtc')
          print("Market Sell Order Submitted!")
        except Exception as e:
          print("Market Sell Order Failed!", e)
  print("No Open Positions Or Market is Closed, Sleeping 10 minutes...")
  if clock.is_open == 0:
    api.cancel_all_orders()
    print("All Open Orders Cancelled!")
  time.sleep(600)
