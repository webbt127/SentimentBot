from alpaca_trade_api import REST, Stream
from transformers import pipeline, BertTokenizer, BertForSequenceClassification
import alpaca_trade_api as tradeapi
import yfinance as yf
import threading
from concurrent.futures import ThreadPoolExecutor

pool = ThreadPoolExecutor(1)

API_KEY = 'PKY18D0R1JOWO0YN0BWC'
API_SECRET = 'zRtwLDoy1MXgPPmSI5twOxoezBQ5edzisJje0UWy'

model = BertForSequenceClassification.from_pretrained("ahmedrachid/FinancialBERT-Sentiment-Analysis",num_labels=3)
tokenizer = BertTokenizer.from_pretrained("ahmedrachid/FinancialBERT-Sentiment-Analysis")

#classifier = pipeline('sentiment-analysis')
classifier = pipeline('sentiment-analysis', model=model, tokenizer=tokenizer)
stream_client = Stream(API_KEY, API_SECRET)
rest_client = REST(API_KEY, API_SECRET)
endpoint = "https://paper-api.alpaca.markets"
#historical_news = rest_client.get_news("*", "2022-08-29", "2022-09-01")
#print(historical_news)


async def news_data_handler(news):

	summary = news.summary
	headline = news.headline
	tickers = news.symbols

	print("News Event for", tickers)

	relevant_text = summary + headline
	sentiment = classifier(relevant_text)

	print(relevant_text)
	print("Sentiment:", sentiment[0]['label'])
	print("Score:", sentiment[0]['score'])

	api = tradeapi.REST(API_KEY, API_SECRET, endpoint)
	clock = api.get_clock()

	for ticker in tickers:
		stock_info = yf.Ticker(ticker).info
		stock_price = stock_info['regularMarketPrice']
		buy_shares = round(1000/stock_price)
		try:
			position = api.get_position(ticker)
			print("Selling", ticker,"...")
			if sentiment[0]['label'] == 'negative' and sentiment[0]['score'] > 0.95:
				try:
					rest_client.submit_order(symbol=ticker, qty=position.qty, side='sell', type='market', time_in_force='gtc')
					print("Market Sell Order Submitted!")
				except Exception as e:
					print("Market Sell Order Failed!", e)
			else:
				print("Conditions not sufficient to sell.")
		except Exception as e:
			print("Buying", ticker,"...")
			if sentiment[0]['label'] == 'positive' and sentiment[0]['score'] > 0.95:
				try:
					rest_client.submit_order(symbol=ticker, qty=buy_shares, side='buy', type='market', time_in_force='gtc')
					print("Market Buy Order Submitted!")
				except Exception as e:
					print("Market Buy Order Failed!", e)
			else:
				print("Conditions not sufficient to buy.")
				
def client_thread():
	
	stream_client.subscribe_news(news_data_handler, "*")
	print("Stream Client Starting, Waiting For Market News...")
	stream_client.run()
	
while True:
	try:
		pool.submit(client_thread)
	except KeyboardInterrupt:
		print("Closing Stream Client...")
		stream_client.stop()
