from alpaca_trade_api import REST, Stream
from transformers import pipeline, BertTokenizer, BertForSequenceClassification
from urllib.request import urlopen, Request
from bs4 import BeautifulSoup
import yfinance as yf
from datetime import datetime, timezone
from tradingview_ta import TA_Handler, Interval, Exchange
from logger import *
import gvars
import threading
import time
from alive_progress import alive_bar


def check_ta(ticker, exchange):
	try:
		ticker_ta = TA_Handler(symbol=ticker, screener="america", exchange=exchange, interval=Interval.INTERVAL_1_HOUR)
		summary = ticker_ta.get_analysis().summary
		recommendation = summary['RECOMMENDATION']
		lg.info(recommendation)
		return recommendation
	except Exception as e:
		lg.info("Unable To Find %s TA!" % ticker)
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


def find_exchange(ticker):
	assets = rest_client.list_assets()
	indexes = range(0,32000)
	for index in indexes:
		if ticker == assets[index].symbol:
			return assets[index].exchange
	return ""
		
def check_market_availability():

	clock = get_clock()
	minutes = seconds_to_close(clock)
	if minutes < (gvars.minutes_min * 60) or minutes > (gvars.minutes_max * 60):
		return True
	else:
		return False

async def news_data_handler(news):

	summary = news.summary
	headline = news.headline
	tickers = news.symbols
	global previous_id

	relevant_text = summary + headline
	sentiment = classifier(relevant_text)
	
	log_news(news, sentiment, previous_id, tickers, relevant_text)

	market_open = check_market_availability()
	cancel_orders()

	if news.id != previous_id:
		for ticker in tickers:
				current_position = get_ticker_position(ticker)
				if current_position == 0:
					lg.info("Buying %s..." % ticker)
					stock_price = get_price(ticker)
					if stock_price is not None:
						new_qty = round(gvars.order_size_usd/(stock_price + .0000000000001))
					else:
						new_qty = 0
					exchange = find_exchange(ticker)
					ta = check_ta(ticker, exchange)
					try:
						reddit_sentiment = apewisdom_sentiment(ticker)
						if reddit_sentiment > gvars.reddit_buy_threshold and ta == "STRONG_BUY" and market_open: #sentiment[0]['label'] == 'positive' and sentiment[0]['score'] > gvars.min_sentiment_score and
							submit_buy_order(ticker, new_qty)
						else:
							lg.info("Conditions not sufficient to buy %s." % ticker)
					except Exception as e:
						lg.info("Unable To Analyze Reddit Sentiment for %s" % ticker)
				else:
					lg.info("%s Position Already Exists!" % ticker)
		previous_id = news.id
		lg.info("Waiting For Market News...")
		
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
	time.sleep(5)
	thread2.start()
	time.sleep(5)
	thread1.join()
	time.sleep(5)
	thread2.join()
	
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
		lg.info("No Existing Position For %s!" % ticker)
		return 0
	
def load_model():
	lg.info("Loading Machine Learning Model...")
	model = BertForSequenceClassification.from_pretrained("ahmedrachid/FinancialBERT-Sentiment-Analysis",num_labels=3)
	tokenizer = BertTokenizer.from_pretrained("ahmedrachid/FinancialBERT-Sentiment-Analysis")
	classifier = pipeline('sentiment-analysis', model=model, tokenizer=tokenizer)
	lg.info("Machine Learning Model Loaded!")
	return classifier
	
def submit_buy_order(ticker, buy_qty):
	try:
		rest_client.submit_order(symbol=ticker, qty=buy_qty, side='buy', type='market', time_in_force='gtc', extended_hours=True)
		lg.info("Market Buy Order Submitted!")
	except Exception as e:
		lg.info("Market Buy Order Failed! %s" % e)
		
def submit_sell_order(ticker, sell_qty):
	try:
		rest_client.submit_order(symbol=ticker, qty=sell_qty, side='sell', type='market', time_in_force='gtc', extended_hours=True)
		lg.info("Market Sell Order Submitted!")
	except Exception as e:
		lg.info("Market Sell Order Failed! %s" % e)
		
def cancel_orders():
	try:
		rest_client.cancel_all_orders()
	except Exception as e:
		lg.info("Unable To Cancel All Orders")
		
def run_sleep():
	clock = get_clock()
	seconds = seconds_to_close(clock)
	if seconds < 68400 or seconds > 39600:
		sleep_length = seconds - 39600
		if sleep_length < 1:
			sleep_length = 1
		with alive_bar(sleep_length) as bar:
			for _ in range(sleep_length):
				time.sleep(1)
				bar()
	
def analysis_thread():
	while True:
		positions, position_list_size, position_list = get_positions()
		market_open = check_market_availability()
		while market_open:
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
			market_open = check_market_availability()
			positions, position_list_size, position_list = get_positions()
		lg.info("Market is Closed, Sleeping...")
		run_sleep()
	

###################INITIALIZATIONS AND RUN MAIN LOOP###################	
initialize_logger()
	
stream_client = Stream(gvars.API_KEY, gvars.API_SECRET_KEY)
rest_client = REST(gvars.API_KEY, gvars.API_SECRET_KEY, gvars.API_URL)
	
classifier = load_model() # load language processing model

previous_id = 0 # initialize duplicate ID check storage
market_open = check_market_availability() # initial time check
positions = get_positions() # check existing positions before iterating
cancel_orders() # cancel all open orders before iterating
begin_threading()
