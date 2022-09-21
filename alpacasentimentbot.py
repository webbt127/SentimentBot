from alpaca_trade_api import REST, Stream
from transformers import pipeline, BertTokenizer, BertForSequenceClassification
from urllib.request import urlopen, Request
from bs4 import BeautifulSoup
import yfinance as yf
from datetime import datetime, timezone
from tradingview_ta import TA_Handler, Interval, Exchange
from logger import *
from helper_functions import *
import gvars
import threading
import time


def check_ta(ticker, exchange):
	try:
		ticker_ta = TA_Handler(symbol=ticker, screener="america", exchange=exchange, interval=Interval.INTERVAL_1_HOUR)
		summary = ticker_ta.get_analysis().summary
		recommendation = summary['RECOMMENDATION']
		return recommendation
	except Exception as e:
		lg.info("Unable To Find %s TA!" % ticker)
		
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
	try:
		reddit_sentiment = int(percentages[3].strip('% '))
		return reddit_sentiment
	except Exception as e:
		lg.info("No Percentage Available for %s" % ticker)


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
	
	log_news(news, sentiment, previous_id, tickers, relevant_text)

	clock = get_clock()

	if news.id != previous_id:
		for ticker in tickers:
			try:
				get_ticker_position(ticker)
				lg.info("%s Position Already Exists!" % ticker)
			except Exception as e:
				lg.info(e)
				lg.info("Buying %s..." % ticker)
				stock_price = get_price(ticker)
				new_qty = round(gvars.order_size_usd/stock_price)
				exchange = find_exchange(ticker)
				ta = check_ta(ticker, exchange)
				try:
					reddit_sentiment = apewisdom_sentiment(ticker)
					if sentiment[0]['label'] == 'positive' and sentiment[0]['score'] > gvars.min_sentiment_score and reddit_sentiment > gvars.reddit_buy_threshold and ta == "STRONG_BUY": # and clock.is_open:
						submit_buy_order(ticker, new_qty)
					else:
						lg.info("Conditions not sufficient to buy %s." % ticker)
				except Exception as e:
					lg.info("Unable To Analyze Reddit Sentiment for %s" % ticker)
		previous_id = news.id
		lg.info("Waiting For Market News...")
		
def get_price(ticker):
	stock_info = yf.Ticker(ticker).info
	stock_price = stock_info['regularMarketPrice']
	return stock_price
	
def minutes_to_close(clock):
	market_close = (datetime.fromisoformat(clock.next_close.isoformat()))
	now = (datetime.now(timezone.utc))
	minutes_to_close = (((market_close - now).seconds)/60)
	return minutes_to_close
	
def log_news(news, sentiment, previous_id, tickers, relevant_text):
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
	thread2 = threading.Thread(target=analysis_thread)
	thread1.start()
	thread2.start()
	thread1.join()
	thread2.join()
	
def get_positions():
	try:
		position_list = rest_client.list_positions()
		position_list_size = len(position_list)
		positions = range(0, position_list_size - 1)
		return positions, position_list_size, position_list
	except Exception as e:
		lg.info("No Positions to Analyze! %s" % e)
		
def get_clock():
	return rest_client.get_clock()
	
def get_ticker_position(ticker):
	try:
		position_size = rest_client.get_position(ticker)
		get_qty = int(position_size.qty)
		return get_qty
	except Exception as e:
		lg.info("No Existing Position for %s" % ticker)
	
def load_model():
	lg.info("Loading Machine Learning Model...")
	model = BertForSequenceClassification.from_pretrained("ahmedrachid/FinancialBERT-Sentiment-Analysis",num_labels=3)
	tokenizer = BertTokenizer.from_pretrained("ahmedrachid/FinancialBERT-Sentiment-Analysis")
	classifier = pipeline('sentiment-analysis', model=model, tokenizer=tokenizer)
	lg.info("Machine Learning Model Loaded!")
	return classifier
	
def submit_buy_order(ticker, buy_qty):
	try:
		rest_client.submit_order(symbol=ticker, qty=buy_qty, side='buy', type='market', time_in_force='gtc')
		lg.info("Market Buy Order Submitted!")
	except Exception as e:
		lg.info("Market Buy Order Failed! %s" % e)
		
def submit_sell_order(ticker, sell_qty):
	try:
		rest_client.submit_order(symbol=ticker, qty=sell_qty, side='sell', type='market', time_in_force='gtc')
		lg.info("Market Sell Order Submitted!")
	except Exception as e:
		lg.info("Market Sell Order Failed! %s" % e)
	
def analysis_thread():
	while True:
		positions, position_list_size, position_list = get_positions()
		clock = get_clock()
		while position_list_size > 0 and clock.is_open:
			for position in positions:
				ticker = position_list[position].__getattr__('symbol')
				exchange = position_list[position].__getattr__('exchange')
				current_qty = get_ticker_position(ticker)
				ta = check_ta(ticker, exchange)
				reddit_sentiment = apewisdom_sentiment(ticker)
				if ta == 'STRONG_SELL' or reddit_sentiment < gvars.reddit_sell_threshold:
					submit_sell_order(ticker, current_qty)
				else:
					lg.info("Conditions not sufficient to sell %s." % ticker)
					
			time.sleep(gvars.loop_sleep_time)
			clock = get_clock()
			positions, position_list_size, position_list = get_positions()
		lg.info("No Open Positions Or Market is Closed, Sleeping 10 minutes...")
		time.sleep(gvars.market_sleep_time)
	

###################INITIALIZATIONS AND RUN MAIN LOOP###################	
initialize_logger()
	
stream_client = Stream(gvars.API_KEY, gvars.API_SECRET_KEY)
rest_client = REST(gvars.API_KEY, gvars.API_SECRET_KEY, gvars.API_URL)
	
classifier = load_model()

previous_id = 0 # initialize duplicate ID check storage
clock = get_clock() # initialize time check
positions = get_positions() # check existing positions before iterating
begin_threading()
