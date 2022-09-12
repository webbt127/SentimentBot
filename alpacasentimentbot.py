from alpaca_trade_api import REST, Stream
from transformers import pipeline, BertTokenizer, BertForSequenceClassification
import alpaca_trade_api as tradeapi

API_KEY = 'PKBZFTD9KPUGALJOW7EY'
API_SECRET = '4W8IkPJXCo7WoiEOZPVyURyc1ojnAcW299bSdXwP'

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

	print("News Event for", tickers, "!")

	relevant_text = summary + headline
	sentiment = classifier(relevant_text)

	print(relevant_text)
	print("Sentiment:", sentiment['label'])
	print("Score:", sentiment['score'])

	api = tradeapi.REST(API_KEY, API_SECRET, endpoint)
	clock = api.get_clock()

	for ticker in tickers:
		try:
			position = api.get_position(ticker)
			if sentiment['label'] == 'NEGATIVE' and sentiment['score'] > 0.95:
				try:
					rest_client.submit_order(symbol=ticker, qty=position.qty, side='sell', type='market', time_in_force='gtc')
					print(ticker, "Market Sell Order Submitted!")
				except Exception as e:
					print(ticker, "Market Sell Order Failed!", e)
			else:
				print(ticker, "Positive Sentiment Found But Position Already Exists!")
		except Exception as e:
			if sentiment['label'] == 'POSITIVE' and sentiment['score'] > 0.95:
				try:
					rest_client.submit_order(symbol=ticker, notional=1000, side='buy', type='market', time_in_force='gtc')
					print(ticker, "Market Buy Order Submitted!")
				except Exception as e:
					print(ticker, "Market Buy Order Failed!", e)
			else:
				print(ticker, "Negative Sentiment Found But No Existing Position!")


stream_client.subscribe_news(news_data_handler, "*")
print("Stream Client Starting, Waiting For Market News...")
stream_client.run()
