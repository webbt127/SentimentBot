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
from requests_html import HTMLSession
from helper_functions import *

		
def check_market_availability():
	clock = get_clock()
	minutes = seconds_to_close(clock)
	if clock.is_open: #minutes < (gvars.minutes_min * 60) or minutes > (gvars.minutes_max * 60):
		return True
	else:
		return False
	
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
	
def submit_buy_order(ticker, buy_qty, ta, pcr):
	try:
		rest_client.submit_order(symbol=ticker, qty=buy_qty, side='buy', type='market', time_in_force='gtc')
		lg.info("Market Buy Order Submitted For %s!" % ticker)
		print("TA: ", ta, " PCR: ", pcr)
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

def run_buy_loop(asset):
	ticker = asset.symbol
	exchange = asset.exchange
	ta = check_ta(ticker, exchange)
	if ta == 'STRONG_BUY':
		current_position = get_ticker_position(ticker)
		if current_position == 0:
			#pcr = get_pcr(ticker)
			#if pcr > 1.5:
			stock_price = get_price(ticker)
			if stock_price is not None:
				new_qty = round(gvars.order_size_usd/(stock_price + .0000000000001))
			else:
				new_qty = 0
			pivots = get_pivots(ticker, exchange, stock_price)
			print(pivots)
			new_qty = new_qty * pivots
			if pivots > 0:
				submit_buy_order(ticker, new_qty, ta, pcr)
		else:
			lg.info("Position Already Exists!")
	else:
		lg.info("TA Not Sufficient For %s!" % ticker)
		
def run_sell_loop(positions):
	for position in positions:
		ticker = position_list[position].__getattr__('symbol')
		exchange = position_list[position].__getattr__('exchange')
		current_qty = get_ticker_position(ticker)
		ta = check_ta(ticker, exchange)
		stock_price = get_price(ticker)
		pivots = get_pivots(ticker, exchange, stock_price)
		#pcr = get_pcr(ticker)
		if ta == 'STRONG_SELL' or ta == 'SELL' or pivots < 0:#pcr < 1.0:
			submit_sell_order(ticker, current_qty)
		else:
			lg.info("Conditions not sufficient to sell %s." % ticker)
	
def main_loop():
	while 1:
		positions, position_list_size, position_list = get_positions()
		market_open = check_market_availability()
		while market_open:
			run_sell_loop(positions)
			with alive_bar(len(assets)) as bar:
				for i in assets:
					run_buy_loop(i)
					bar()
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
active_assets = rest_client.list_assets(status='active')
assets = [a for a in active_assets if a.exchange == 'NASDAQ' or a.exchange == 'NYSE']
cancel_orders() # cancel all open orders before iterating
main_loop()
