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


def check_ta(asset):
	try:
		ticker_ta = TA_Handler(symbol=asset.symbol, screener="america", exchange=asset.exchange, interval=Interval.INTERVAL_1_HOUR)
		summary = ticker_ta.get_analysis().summary
		recommendation = summary['RECOMMENDATION']
		asset.ta = recommendation
		#lg.info("TradingView Recommendation: %s" % recommendation)
	except Exception as e:
		#lg.info("Unable To Find %s TA!" % asset.symbol)
		asset.ta = ""
	return asset
        
def apewisdom_sentiment(asset):
	apewisdom_url = "https://apewisdom.io/stocks/"
	url = apewisdom_url + asset.symbol
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
		asset.reddit_sentiment = reddit_sentiment
	else:
		lg.info("No Percentage Available for %s" % asset.symbol)
		asset.reddit_sentiment = 0.0
	return asset
        
def get_pcr(asset):
	barchart_url = "https://www.barchart.com/stocks/quotes/"
	url = barchart_url + asset.symbol + "/put-call-ratios"
	req = Request(url=url, headers={'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'})
	try:
		response = urlopen(req)
	except Exception as e:
		asset.pcr = 0.0
	
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
		asset.pcr = barchart_pcr
	else:
		#lg.info("No PCR Available for %s" % asset.symbol)
		asset.pcr = 0.0
	return asset
        
def get_pivots(asset):
	tv_url = "https://www.tradingview.com/symbols/"
	url = tv_url + asset.exchange + "-" + asset.symbol + "/technicals"
	session = HTMLSession()
	try:
		req = session.get(url)
		req.html.render()
	except Exception as e:
		asset.pivot = 0
		lg.info(e)
		return asset
	table = req.html.find('td')
	req.session.close()
	pivots = [None] * 120
	index = 0
	for i in table:
		pivots[index] = i.text
		index = index + 1
	if pivots[80] == '—' or pivots[86] == '—' or pivots[92] == '—' or pivots[98] == '—' or pivots[104] == '—' or pivots[110] == '—' or pivots[116] == '—':
		asset.pivot = 0
		return asset
	if pivots[80] is not None and pivots[86] is not None and pivots[92] is not None and pivots[98] is not None and pivots[104] is not None and pivots[110] is not None and pivots[116] is not None:
		asset.s3 = float(pivots[80])
		asset.s2 = float(pivots[86])
		asset.s1 = float(pivots[92])
		asset.p = float(pivots[98])
		asset.r1 = float(pivots[104])
		asset.r2 = float(pivots[110])
		asset.r3 = float(pivots[116])
	else:
		asset.pivot = 0
		return asset
	if pivots[0] is not None and asset.price is not None:
		if asset.price > asset.s1 and asset.price < asset.p:
			asset.pivot = 1
		elif asset.price > asset.s2 and asset.price < asset.s1:
			asset.pivot = 2
		elif asset.price > asset.s3 and asset.price < asset.s2:
			asset.pivot = 3
		elif asset.price < asset.s3:
			asset.pivot = 4
		elif asset.price < asset.r1 and asset.price > asset.p:
			asset.pivot = -1
		elif asset.price < asset.r2 and asset.price > asset.r1:
			asset.pivot = -2
		elif asset.price < asset.r3 and asset.price > asset.r2:
			asset.pivot = -3
		elif asset.price > asset.r3:
			asset.pivot = -4
		else:
			asset.pivot = 0
	else:
		asset.pivot = 0
	return asset
        
def get_price(asset):
	try:
		stock_info = yf.Ticker(asset.symbol).info
		print(stock_info)
		asset.price = stock_info['regularMarketPrice']
		return asset
	except Exception as e:
		asset.price = None
		lg.info(e)
		return

def get_all_prices(assets):
	asset_list = []
	for asset in assets:
		asset_list.append(asset.symbol)
	try:
		tickers = yf.Tickers(asset_list)
	except Exception as e:
		lg.info(e)
	for asset in assets:
		price = tickers.tickers[asset.symbol].info['regularMarketPrice']
		asset.price = price
	return assets
