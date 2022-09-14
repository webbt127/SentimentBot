from alpaca_trade_api import REST, Stream
from transformers import pipeline, BertTokenizer, BertForSequenceClassification
import alpaca_trade_api as tradeapi
import yfinance as yf

API_KEY = 'PKVLATR3V44A75JDC07W'
API_SECRET = 'ngvSepjmymi5Aj0wn13kU6h1ZJyfzfMkQxfDzvmv'
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

	print("News Event for", tickers)

	relevant_text = summary + headline
	sentiment = classifier(relevant_text)

	print(relevant_text)
	print("Sentiment:", sentiment[0]['label'])
	print("Score:", sentiment[0]['score'])

	api = tradeapi.REST(API_KEY, API_SECRET, endpoint)
	clock = api.get_clock()

	if sentiment[0]['label'] != 'neutral' and sentiment[0]['score'] > 0.95 and news.id != previous_id:
		for ticker in tickers:
			try:
				position = api.get_position(ticker)
				print("Selling", ticker,"...")
				if sentiment[0]['label'] == 'negative' and sentiment[0]['score'] > 0.95:
					try:
						stock_info = yf.Ticker(ticker).info
						stock_price = stock_info['regularMarketPrice']
						stock_price_order = stock_price * 0.98
						rest_client.submit_order(symbol=ticker, qty=position.qty, side='sell', type='limit', limit_price=stock_price_order, time_in_force='gtc')
						print("Market Sell Order Submitted!")
					except Exception as e:
						print("Market Sell Order Failed!", e)
				else:
					print("Conditions not sufficient to sell.")
			except Exception as e:
				print("Buying", ticker,"...")
				if sentiment[0]['label'] == 'positive' and sentiment[0]['score'] > 0.95:
					try:
						stock_info = yf.Ticker(ticker).info
						stock_price = stock_info['regularMarketPrice']
						buy_shares = round(1000/stock_price)
						stock_price_order = stock_price *1.05
						rest_client.submit_order(symbol=ticker, qty=buy_shares, side='buy', type='limit', limit_price=stock_price_order, time_in_force='gtc')
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
