from alpaca_trade_api import REST, Stream
from transformers import pipeline, BertTokenizer, BertForSequenceClassification
import yfinance as yf
from datetime import datetime, timezone
from tradingview_ta import TA_Handler, Interval, Exchange
from logger import *
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

def find_exchange(ticker):
	assets = api.list_assets()
	indexes = range(0,32100)
	for index in indexes:
		if ticker == assets[index].symbol:
			return assets[index].exchange
                
def get_price(ticker):
	stock_info = yf.Ticker(ticker).info
	stock_price = stock_info['regularMarketPrice']
	return stock_price
	
def minutes_to_close():
	market_close = (datetime.fromisoformat(clock.next_close.isoformat()))
	now = (datetime.now(timezone.utc))
	minutes_to_close = (((market_close - now).seconds)/60)
	return minutes_to_close
	
def log_news():
	if previous_id != news.id:
		lg.info("News Event for %s" % tickers)
		lg.info(relevant_text)
		lg.info("Sentiment: %s" % sentiment[0]['label'])
		lg.info("Score: %s" % sentiment[0]['score'])
		lg.info("ID: %s" % news.id)
	else:
		lg.info("Duplicate ID, skipping...")
                
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
	position_size = rest_client.get_position(ticker)
	get_qty = int(position_size.qty)
	return get_qty
	
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
