from alpaca_trade_api import REST, Stream
from transformers import pipeline, BertTokenizer, BertForSequenceClassification
import yfinance as yf
from datetime import datetime, timezone
from tradingview_ta import TA_Handler, Interval, Exchange
from logger import *
from helper_functions import *
import gvars
import threading
import time


async def news_data_handler(news):

	summary = news.summary
	headline = news.headline
	tickers = news.symbols
	global previous_id

	relevant_text = summary + headline
	sentiment = classifier(relevant_text)
	
	log_news()

	clock = get_clock()

	if news.id != previous_id:
		for ticker in tickers:
			try:
				get_ticker_position(ticker)
				lg.info("%s Position Already Exists!" % ticker)
			except Exception as e:
				lg.info("Buying %s..." % ticker)
				stock_price = get_price(ticker)
				new_qty = round(1000/stock_price)
				if sentiment[0]['label'] == 'positive' and sentiment[0]['score'] > 0.95 and clock.is_open:
					submit_buy_order(ticker, new_qty)
				else:
					lg.info("Conditions not sufficient to buy %s." % ticker)
		previous_id = news.id
		lg.info("Waiting For Market News...")
				
def news_thread():
	stream_client.subscribe_news(news_data_handler, "*")
	lg.info("Stream Client Starting, Waiting For Market News...")
	stream_client.run()
	
def begin_threading():
	thread1 = threading.Thread(target=news_thread)
	thread2 = threading.Thread(target=analysis_thread)
	thread1.start()
	thread2.start()
	thread1.join()
	thread2.join()
	
def analysis_thread():
	while True:
		positions, position_list_size, position_list = get_positions()
		while position_list_size > 0 and clock.is_open:
			clock = get_clock()
			positions, position_list_size, position_list = get_positions()
			for position in positions:
				ticker = position_list[position].__getattr__('symbol')
				exchange = position_list[position].__getattr__('exchange')
				current_qty = get_ticker_position(ticker)
				ta = check_ta(ticker, exchange)
				if ta == 'STRONG_BUY':
					submit_sell_order(ticker, current_qty)
				else:
					lg.info("Conditions not sufficient to sell %s." % ticker)
					
			time.sleep(60)
		lg.info("No Open Positions Or Market is Closed, Sleeping 10 minutes...")
		time.sleep(600)
	

###################INITIALIZATIONS AND RUN MAIN LOOP###################	
initialize_logger()
	
stream_client = Stream(gvars.API_KEY, gvars.API_SECRET_KEY)
rest_client = REST(gvars.API_KEY, gvars.API_SECRET_KEY, gvars.API_URL)
	
classifier = load_model()

previous_id = 0 # initialize duplicate ID check storage
clock = get_clock() # initialize time check
positions = get_positions() # check existing positions before iterating

begin_threading()
