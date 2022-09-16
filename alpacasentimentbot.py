from alpaca_trade_api import REST, Stream
from transformers import pipeline, BertTokenizer, BertForSequenceClassification
import alpaca_trade_api as tradeapi
import yfinance as yf
from datetime import datetime, timezone
from tradingview_ta import TA_Handler, Interval, Exchange
from logger import *
import gvars

initialize_logger()

lg.info("Loading Machine Learning Model...")
model = BertForSequenceClassification.from_pretrained("ahmedrachid/FinancialBERT-Sentiment-Analysis",num_labels=3)
tokenizer = BertTokenizer.from_pretrained("ahmedrachid/FinancialBERT-Sentiment-Analysis")
lg.info("Machine Learning Model Loaded!")

lg.info("Loading Classifier...")
classifier = pipeline('sentiment-analysis', model=model, tokenizer=tokenizer)
stream_client = Stream(gvars.API_KEY, gvars.API_SECRET_KEY)
rest_client = REST(gvars.API_KEY, gvars.API_SECRET_KEY, gvars.API_URL)
lg.info("Classifier Loaded!")
previous_id = 0

def check_ta(ticker, exchange):
	try:
		ticker_ta = TA_Handler(symbol=ticker, screener="america", exchange=exchange, interval=Interval.INTERVAL_1_HOUR)
	except Exception as e:
		lg.info("Unable To Find Ticker TA!", e)
	summary = ticker_ta.get_analysis().summary
	recommendation = summary['RECOMMENDATION']
	return recommendation

def get_exchange(ticker):
	assets = api.list_assets()
	print(assets[0].symbol)
	if ticker == assets[0].symbol:
		return assets[0].exchange

async def news_data_handler(news):

	summary = news.summary
	headline = news.headline
	tickers = news.symbols
	global previous_id

	relevant_text = summary + headline
	sentiment = classifier(relevant_text)
	if previous_id != news.id:
		lg.info("News Event for", tickers)
		lg.info(relevant_text)
		lg.info("Sentiment:", sentiment[0]['label'])
		lg.info("Score:", sentiment[0]['score'])
		lg.info("ID:", news.id)
	else:
		lg.info("Duplicate ID, skipping...")

	api = tradeapi.REST(API_KEY, API_SECRET, endpoint)
	clock = api.get_clock()
	market_close = (datetime.fromisoformat(clock.next_close.isoformat()))
	now = (datetime.now(timezone.utc))
	minutes_to_close = (((market_close - now).seconds)/60)

	if news.id != previous_id:
		for ticker in tickers:
			exchange = get_exchange(ticker)
			ta = check_ta(ticker, exchange)
			position = api.get_position(ticker)
			lg.info("Selling", ticker,"...")
				if (((sentiment[0]['label'] == 'negative' and sentiment[0]['score'] > 0.95) or recommendation == 'SELL' or recommendation == 'STRONG_SELL') and clock.is_open):
					try:
						rest_client.submit_order(symbol=ticker, qty=position.qty, side='sell', type='market', time_in_force='gtc')
						lg.info("Market Sell Order Submitted!")
					except Exception as e:
						lg.info("Market Sell Order Failed!", e)
				else:
					lg.info("Conditions not sufficient to sell.")
			except Exception as e:
				lg.info("Buying", ticker,"...")
				if sentiment[0]['label'] == 'positive' and sentiment[0]['score'] > 0.95 and (recommendation == 'BUY' or recommendation == 'STRONG_BUY') and clock.is_open:
					try:
						stock_info = yf.Ticker(ticker).info
						stock_price = stock_info['regularMarketPrice']
						buy_shares = round(1000/stock_price)
						rest_client.submit_order(symbol=ticker, qty=buy_shares, side='buy', type='market', time_in_force='gtc')
						lg.info("Market Buy Order Submitted!")
					except Exception as e:
						lg.info("Market Buy Order Failed!", e)
				else:
					lg.info("Conditions not sufficient to buy.")
		lg.info("Waiting For Market News...")
	previous_id = news.id


stream_client.subscribe_news(news_data_handler, "*")
lg.info("Stream Client Starting, Waiting For Market News...")
stream_client.run()
