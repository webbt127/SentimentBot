from alpaca_trade_api import REST, Stream
from transformers import pipeline, BertTokenizer, BertForSequenceClassification
from urllib.request import urlopen, Request
from bs4 import BeautifulSoup
import yfinance as yf
from datetime import datetime, timezone
from tradingview_ta import TA_Handler, Interval, Exchange
from logger import *
import gvars
from joblib import Parallel, delayed, parallel_backend
import time
from alive_progress import alive_bar
from tqdm.auto import tqdm


def check_ta(ticker, exchange):
	try:
		ticker_ta = TA_Handler(symbol=ticker, screener="america", exchange=exchange, interval=Interval.INTERVAL_1_HOUR)
		summary = ticker_ta.get_analysis().summary
		recommendation = summary['RECOMMENDATION']
		#lg.info("TradingView Recommendation: %s" % recommendation)
		return recommendation
	except Exception as e:
		#lg.info("Unable To Find %s TA!" % ticker)
		return ""
		
def apewisdom_sentiment(ticker):
	apewisdom_url = "https://apewisdom.io/stocks/"
	url = apewisdom_url + ticker
	req = Request(url=url, headers={'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'})
	response = urlopen(req)
	
	html = BeautifulSoup(response, features="html.parser")
	strings = html.find_all('div', {'class':'tile-value'})
	index = 0
	percentages = [None] * 5
	for string in strings:
		storage = string.text
		percentages[index] = storage
		index = index + 1
	temp = percentages[3].strip('% ')
	reddit_sentiment = int(temp)
	if reddit_sentiment is not None:
		lg.info("ApeWisdom Sentiment: %s" % reddit_sentiment)
		return reddit_sentiment
	else:
		lg.info("No Percentage Available for %s" % ticker)
		return 0
	
def get_pcr(ticker):
	barchart_url = "https://www.barchart.com/stocks/quotes/"
	url = barchart_url + ticker + "/put-call-ratios"
	req = Request(url=url, headers={'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'})
	try:
		response = urlopen(req)
	except Exception as e:
		return 0
	
	html = BeautifulSoup(response, features="html.parser")
	try:
		strings = html.find_all('div', {'class':'bc-futures-options-quotes-totals__data-row'})
	except Exception as e:
		lg.info("Unable To Find PCR Data %s" % e)
	index = 0
	percentages = [None] * 100
	for string in strings:
		storage = string.text
		percentages[index] = storage
		index = index + 1
	if percentages[5] is not None:
		temp = percentages[5].replace(" Put/Call Open Interest Ratio  ", "")
		temp = temp.replace(" ", "")
		barchart_pcr = float(temp)
	else:
		barchart_pcr = 0.0
	if barchart_pcr is not None:
		#lg.info("BarChart PCR: %s" % barchart_pcr)
		return barchart_pcr
	else:
		#lg.info("No PCR Available for %s" % ticker)
		return 0


def find_exchange(ticker):
	assets = rest_client.list_assets()
	indexes = range(0,32000)
	for index in indexes:
		alive_bar(indexes)
		if ticker == assets[index].symbol:
			return assets[index].exchange
	return ""
		
def check_market_availability():
	return True
	clock = get_clock()
	minutes = seconds_to_close(clock)
	if clock.is_open: #minutes < (gvars.minutes_min * 60) or minutes > (gvars.minutes_max * 60):
		return True
	else:
		return False
		
def get_price(ticker):
	try:
		stock_info = yf.Ticker(ticker).info
		stock_price = stock_info['regularMarketPrice']
		return stock_price
	except Exception as e:
		lg.info(e)
		return
	
def seconds_to_close(clock):
	market_close = (datetime.fromisoformat(clock.next_close.isoformat()))
	now = (datetime.now(timezone.utc))
	seconds = round(((market_close - now).seconds))
	return seconds
        
def seconds_to_open(clock):
	market_open = (datetime.fromisoformat(clock.next_open.isoformat()))
	now = (datetime.now(timezone.utc))
	seconds = round(((market_open - now).seconds))
	return seconds
	
def get_positions():
	try:
		position_list = rest_client.list_positions()
		position_list_size = len(position_list)
		positions = range(0, position_list_size - 1)
		return positions, position_list_size, position_list
	except Exception as e:
		lg.info("No Positions to Analyze! %s" % e)
		return range(0, 0), 0, []
		
def get_clock():
	return rest_client.get_clock()
	
def get_ticker_position(ticker):
	try:
		position_size = rest_client.get_position(ticker)
		get_qty = int(position_size.qty)
		return get_qty
	except Exception as e:
		#lg.info("No Existing Position For %s!" % ticker)
		return 0
	
def submit_buy_order(ticker, buy_qty):
	try:
		rest_client.submit_order(symbol=ticker, qty=buy_qty, side='buy', type='market', time_in_force='gtc')
		lg.info("Market Buy Order Submitted For %s!" % ticker)
	except Exception as e:
		lg.info("Market Buy Order Failed! %s" % e)
		
def submit_sell_order(ticker, sell_qty):
	try:
		rest_client.submit_order(symbol=ticker, qty=sell_qty, side='sell', type='market', time_in_force='gtc')
		lg.info("Market Sell Order Submitted For %s!" % ticker)
	except Exception as e:
		lg.info("Market Sell Order Failed! %s" % e)
		
def cancel_orders():
	try:
		rest_client.cancel_all_orders()
	except Exception as e:
		lg.info("Unable To Cancel All Orders")
		
def run_sleep():
	clock = get_clock()
	seconds = seconds_to_open(clock)
	if seconds < 63000:
		sleep_length = seconds
		if sleep_length < 1:
			sleep_length = 1
		with alive_bar(sleep_length) as bar:
			for _ in range(sleep_length):
				time.sleep(1)
				bar()
				
def no_operation():
	return

def run_buy_loop(index):
	ticker = assets[index].symbol
	exchange = assets[index].exchange
	if exchange == 'NASDAQ' or exchange == 'NYSE':
		ta = check_ta(ticker, exchange)
		if ta == 'STRONG_BUY':
			current_position = get_ticker_position(ticker)
			if current_position == 0:
				pcr = get_pcr(ticker)
				if pcr > 0.8:
					stock_price = get_price(ticker)
					if stock_price is not None:
						new_qty = round(gvars.order_size_usd/(stock_price + .0000000000001))
					else:
						new_qty = 0
					submit_buy_order(ticker, new_qty)
				else:
					no_operation()
					#lg.info("PCR not sufficient to buy %s." % ticker)
			else:
				no_operation()
				#lg.info("Position Already Exists!")
		else:
			no_operation()
			#lg.info("TA Not Sufficient For %s!" % ticker)
	
def analysis_thread():
	while 1:
		positions, position_list_size, position_list = get_positions()
		market_open = check_market_availability()
		while market_open:
			for position in positions:
				ticker = position_list[position].__getattr__('symbol')
				exchange = position_list[position].__getattr__('exchange')
				current_qty = get_ticker_position(ticker)
				ta = check_ta(ticker, exchange)
				pcr = get_pcr(ticker)
				if ta == 'STRONG_SELL' or ta == 'SELL' or pcr < 0.65:
					submit_sell_order(ticker, current_qty)
				else:
					lg.info("Conditions not sufficient to sell %s." % ticker)
                                        
			indexes = range(0,31600)
			Parallel(n_jobs=8, prefer="threads")(delayed(run_buy_loop)(i) for i in tqdm(indexes, desc="Scanning Progress", leave=False, ncols=100, bar_format='{l_bar}{bar}|'))
			market_open = check_market_availability()
			positions, position_list_size, position_list = get_positions()
		lg.info("Market is Closed, Sleeping...")
		cancel_orders()
		run_sleep()
	

###################INITIALIZATIONS AND RUN MAIN LOOP###################	
initialize_logger()
	
rest_client = REST(gvars.API_KEY, gvars.API_SECRET_KEY, gvars.API_URL)

market_open = check_market_availability() # initial time check
positions = get_positions() # check existing positions before iterating
assets = rest_client.list_assets()
cancel_orders() # cancel all open orders before iterating
analysis_thread()
