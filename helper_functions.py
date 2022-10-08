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
        
def get_pivots(ticker, exchange, price):
	tv_url = "https://www.tradingview.com/symbols/"
	url = tv_url + exchange + "-" + ticker + "/technicals"
	session = HTMLSession()
	try:
		req = session.get(url)
	except Exception as e:
		lg.info(e)
	req.html.render()
	table = req.html.find('td')
	req.session.close()
	pivots = [None] * 120
	index = 0
	for i in table:
		pivots[index] = i.text
		index = index + 1
	if fib_s3 == '-' or fib_s2 == '-' or fib_s1 == '-' or fib_p == '-' or fib_r1 == '-' or fib_r2 == '-' or fib_r3 == '-':
		return 0
	fib_s3 = float(pivots[80])
	fib_s2 = float(pivots[86])
	fib_s1 = float(pivots[92])
	fib_p = float(pivots[98])
	fib_r1 = float(pivots[104])
	fib_r2 = float(pivots[110])
	fib_r3 = float(pivots[116])
	if pivots[0] is not None:
		if price > fib_s1 and price < fib_p:
			return 1
		elif price > fib_s2 and price < fib_s1:
			return 2
		elif price > fib_s3 and price < fib_s2:
			return 3
		elif price < fib_s3:
			return 4
		elif price < fib_r1 and price > fib_p:
			return -1
		elif price < fib_r2 and price > fib_r1:
			return -2
		elif price < fib_r3 and price > fib_r2:
			return -3
		elif price > fib_r3:
			return -4
		else:
			return 0
	else:
		return 0
        
def get_price(ticker):
	try:
		stock_info = yf.Ticker(ticker).info
		stock_price = stock_info['regularMarketPrice']
		return stock_price
	except Exception as e:
		lg.info(e)
		return
