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
	return True
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
		return position_list
	except Exception as e:
		lg.info("No Positions to Analyze! %s" % e)
		return []
		
def get_clock():
	return rest_client.get_clock()
	
def get_ticker_position(asset):
	try:
		position_size = rest_client.get_position(asset.symbol)
		asset.qty = int(position_size.qty)
	except Exception as e:
		#lg.info("No Existing Position For %s!" % asset.symbol)
		asset.qty = 0
	return asset
	
def submit_buy_order(asset):
	try:
		rest_client.submit_order(symbol=asset.symbol, qty=asset.new_qty, side='buy', type='market', time_in_force='gtc')
		lg.info("Market Buy Order Submitted For %s!" % asset.symbol)
	except Exception as e:
		lg.info("Market Buy Order Failed! %s" % e)
		
def submit_sell_order(asset):
	try:
		rest_client.submit_order(symbol=asset.symbol, qty=asset.qty, side='sell', type='market', time_in_force='gtc')
		lg.info("Market Sell Order Submitted For %s!" % asset.symbol)
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
	sleep_length = seconds
	if seconds < 63000 or seconds > 64000:
		if sleep_length < 1:
			sleep_length = 1
		with alive_bar(sleep_length, title='Market Closed, Sleeping...') as bar:
			for _ in range(sleep_length):
				time.sleep(1)
				bar()
				
def no_operation():
	return

def calc_qty(asset):
	if asset.price is not None:
		asset.new_qty = round(gvars.order_size_usd/(asset.price + .0000000000001))
		get_pivots(asset)
	else:
		asset.new_qty = 0
		asset.pivot = 0
	asset.new_qty = asset.new_qty * asset.pivot
	return asset

def run_buy_loop(asset):
	get_ticker_position(asset)
	if asset.qty == 0 and asset.price is not None:
		get_pivots(asset)
		if asset.pivot > 0:
			calc_qty(asset)
			submit_buy_order(asset)
	else:
		lg.info("Unable To Buy Asset!")
		
def run_sell_loop(positions):
	for position in positions:
		get_ticker_position(position)
		check_ta(position)
		get_price(position)
		get_pivots(position)
		#pcr = get_pcr(position.symbol)
		if position.ta == 'STRONG_SELL' or position.ta == 'SELL' or position.pivot < 0:#pcr < 1.0:
			submit_sell_order(position)
		else:
			lg.info("Conditions not sufficient to sell %s." % position.symbol)
	
def main_loop(assets):
	while 1:
		positions = get_positions()
		market_open = check_market_availability()
		while market_open:
			#run_sell_loop(positions)
			with alive_bar(0, title='Checking Technicals...') as bar:
				Parallel(n_jobs=8, prefer="threads")(delayed(check_ta)(asset) for asset in assets)
				bar()
			lg.info("Asset List TA Checked!")
			assets_filtered_ta = [a for a in assets if a.ta == 'STRONG_BUY']
			with alive_bar(0, title='Getting Prices...') as bar:
				Parallel(n_jobs=8, prefer="threads")(delayed(get_price)(asset) for asset in assets_filtered_ta)
				bar()
			lg.info("Prices Retrieved!")
			with alive_bar(len(assets_filtered_ta), title='Checking Filtered Assets To Buy...') as bar:
				for asset in assets_filtered_ta:
					run_buy_loop(asset)
					bar()
			market_open = check_market_availability()
			positions = get_positions()
		cancel_orders()
		run_sleep()
	

###################INITIALIZATIONS AND RUN MAIN LOOP###################	
initialize_logger()
	
rest_client = REST(gvars.API_KEY, gvars.API_SECRET_KEY, gvars.API_URL)

market_open = check_market_availability() # initial time check
positions = get_positions() # check existing positions before iterating
active_assets = rest_client.list_assets(status='active')
assets = [a for a in active_assets if (a.exchange == 'NASDAQ' or a.exchange == 'NYSE') and a.tradable == True]
cancel_orders() # cancel all open orders before iterating
main_loop(assets)
