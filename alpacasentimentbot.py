from alpaca_trade_api import REST, Stream
from transformers import pipeline, BertTokenizer, BertForSequenceClassification
import yfinance as yf
from datetime import datetime, timezone
from tradingview_ta import TA_Handler, Interval, Exchange
from logger import *
import gvars
import threading
import time

initialize_logger()
	
stream_client = Stream(gvars.API_KEY, gvars.API_SECRET_KEY)
rest_client = REST(gvars.API_KEY, gvars.API_SECRET_KEY, gvars.API_URL)
	
load_model()

previous_id = 0 # initialize duplicate ID check storage
clock = get_clock(rest_client) # initialize time check
get_positions() # check existing positions before iterating

def check_ta(ticker, exchange):
	try:
		ticker_ta = TA_Handler(symbol=ticker, screener="america", exchange=exchange, interval=Interval.INTERVAL_1_HOUR)
		summary = ticker_ta.get_analysis().summary
		recommendation = summary['RECOMMENDATION']
		return recommendation
	except Exception as e:
		lg.info("Unable To Find %s TA!" % ticker)

def find_exchange(ticker):
	assets = api.list_assets()
	indexes = range(0,32100)
	for index in indexes:
		if ticker == assets[index].symbol:
			return assets[index].exchange

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
		
def get_price(ticker):
	stock_info = yf.Ticker(ticker).info
	stock_price = stock_info['regularMarketPrice']
	
def minutes_to_close():
	market_close = (datetime.fromisoformat(clock.next_close.isoformat()))
	now = (datetime.now(timezone.utc))
	minutes_to_close = (((market_close - now).seconds)/60)
	
def log_news():
	if previous_id != news.id:
		lg.info("News Event for %s" % tickers)
		lg.info(relevant_text)
		lg.info("Sentiment: %s" % sentiment[0]['label'])
		lg.info("Score: %s" % sentiment[0]['score'])
		lg.info("ID: %s" % news.id)
	else:
		lg.info("Duplicate ID, skipping...")
		
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
	
def get_positions():
	try:
		position_list = rest_client.list_positions()
		position_list_size = len(position_list)
		positions = range(0, position_list_size - 1)
	except Exception as e:
		lg.info("No Positions to Analyze! %s" % e)
		
def get_clock(rest_client):
	clock = rest_client.get_clock()
	
def get_ticker_position(ticker):
	position_size = rest_client.get_position(ticker)
	get_qty = int(position_size.qty)
	return get_qty
	
def load_model():
	lg.info("Loading Machine Learning Model...")
	model = BertForSequenceClassification.from_pretrained("ahmedrachid/FinancialBERT-Sentiment-Analysis",num_labels=3)
	tokenizer = BertTokenizer.from_pretrained("ahmedrachid/FinancialBERT-Sentiment-Analysis")
	classifier = pipeline('sentiment-analysis', model=model, tokenizer=tokenizer)
	lg.info("Machine Learning Model Loaded!")
	
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
	
	begin_threading()
	
if __name__ == '__main__':
	main()
