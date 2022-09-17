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

	get_clock()

	if news.id != previous_id:
		for ticker in tickers:
			try:
				get_ticker_position(ticker)
				lg.info("%s Position Already Exists!" % ticker)
			except Exception as e:
				lg.info("Buying %s..." % ticker)
				get_price(ticker)
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
	thread1.start()
	thread1.join()
	thread2 = threading.Thread(target=analysis_thread)
	thread2.start()
	thread2.join()
	
def submit_buy_order(ticker, buy_qty):
	try:
		rest_client.submit_order(symbol=ticker, qty=buy_qty, side='buy', type='market', time_in_force='gtc')
		lg.info("Market Buy Order Submitted!")
	except Exception as e:
		lg.info("Market Buy Order Failed! %s" % e)
		
def submit_sell_order(ticker, sell_qty):
	try:
		rest_client.submit_order(symbol=ticker, qty=sell_qty, side='sell', type='market', time_in_force='gtc')
		lg.info("Market Short Order Submitted!")
	except Exception as e:
		lg.info("Market Short Order Failed! %s" % e)
	
def analysis_thread():
	while True:
		while clock.is_open and position_list_size > 0:
			get_clock()
			get_positions()
			for position in positions:
				ticker = position_list[position].__getattr__('symbol')
				exchange = position_list[position].__getattr__('exchange')
				current_qty = get_ticker_position()
				ta = check_ta(ticker, exchange)
				if ta == 'STRONG_BUY':
					submit_sell_order(ticker, current_qty)
				else:
					lg.info("Conditions not sufficient to sell %s." % ticker)
					
			time.sleep(60)
		lg.info("No Open Positions Or Market is Closed, Sleeping 10 minutes...")
		time.sleep(600)
def main():
	initialize_logger()
	
	load_model()

	previous_id = 0 # initialize duplicate ID check storage
	get_clock() # initialize time check
	get_positions() # check existing positions before iterating
	
	begin_threading()
	
if __name__ == '__main__':
	main()

