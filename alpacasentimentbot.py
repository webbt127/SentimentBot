from alpaca_trade_api import REST, Stream
from transformers import pipeline, BertTokenizer, BertForSequenceClassification
import alpaca_trade_api as tradeapi
import yfinance as yf
from datetime import datetime, timezone
from tradingview_ta import TA_Handler, Interval, Exchange

API_KEY = 'PKGHWK2YIALYGDM0L76G'
API_SECRET = 'afiiLs9sSFnJqyTcwIuRY71IZyyqfyYzup9t3GPh'
endpoint = "https://paper-api.alpaca.markets"

print("Loading Machine Learning Model...")
model = BertForSequenceClassification.from_pretrained("ahmedrachid/FinancialBERT-Sentiment-Analysis",num_labels=3)
tokenizer = BertTokenizer.from_pretrained("ahmedrachid/FinancialBERT-Sentiment-Analysis")
print("Machine Learning Model Loaded!")

print("Loading Classifier...")
#classifier = pipeline('sentiment-analysis')
classifier = pipeline('sentiment-analysis', model=model, tokenizer=tokenizer)
stream_client = Stream(API_KEY, API_SECRET)
rest_client = REST(API_KEY, API_SECRET, endpoint)
print("Classifier Loaded!")
#historical_news = rest_client.get_news("*", "2022-08-29", "2022-09-01")
#print(historical_news)
previous_id = 0


async def news_data_handler(news):

	summary = news.summary
	headline = news.headline
	tickers = news.symbols
	global previous_id

	relevant_text = summary + headline
	sentiment = classifier(relevant_text)
	if previous_id != news.id:
		print("News Event for", tickers)
		print(relevant_text)
		print("Sentiment:", sentiment[0]['label'])
		print("Score:", sentiment[0]['score'])
		print("ID:", news.id)
	else:
		print("Duplicate ID, skipping...")

	api = tradeapi.REST(API_KEY, API_SECRET, endpoint)
	clock = api.get_clock()
	market_close = (datetime.fromisoformat(clock.next_close.isoformat()))
	now = (datetime.now(timezone.utc))
	minutes_to_close = (((market_close - now).seconds)/60)

	if news.id != previous_id:
		for ticker in tickers:
			stock_info = yf.Ticker(ticker).info
			try:
				ticker_ta = TA_Handler(symbol=ticker, screener="america", exchange='nasdaq', interval=Interval.INTERVAL_1_HOUR)
			except Exception as e:
				ticker_ta = TA_Handler(symbol=ticker, screener="america", exchange='nyse', interval=Interval.INTERVAL_1_HOUR)
			summary = ticker_ta.get_analysis().summary
			recommendation = summary['RECOMMENDATION']
			try:
				position = api.get_position(ticker)
				print("Selling", ticker,"...")
				if (((sentiment[0]['label'] == 'negative' and sentiment[0]['score'] > 0.95) or recommendation == 'SELL' or recommendation == 'STRONG_SELL') and clock.is_open):
					try:
						rest_client.submit_order(symbol=ticker, qty=position.qty, side='sell', type='market', time_in_force='gtc')
						print("Market Sell Order Submitted!")
					except Exception as e:
						print("Market Sell Order Failed!", e)
				else:
					print("Conditions not sufficient to sell.")
			except Exception as e:
				print("Buying", ticker,"...")
				if sentiment[0]['label'] == 'positive' and sentiment[0]['score'] > 0.95 and (recommendation == 'BUY' or recommendation == 'STRONG_BUY') and clock.is_open:
					try:
						stock_price = stock_info['regularMarketPrice']
						buy_shares = round(1000/stock_price)
						rest_client.submit_order(symbol=ticker, qty=buy_shares, side='buy', type='market', time_in_force='gtc')
						print("Market Buy Order Submitted!")
					except Exception as e:
						print("Market Buy Order Failed!", e)
				else:
					print("Conditions not sufficient to buy.")
		print("Waiting For Market News...")
	previous_id = news.id


stream_client.subscribe_news(news_data_handler, "*")
print("Stream Client Starting, Waiting For Market News...")
stream_client.run()
