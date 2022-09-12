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

	relevant_text = summary + headline
	sentiment = classifier(relevant_text)

	api = tradeapi.REST(API_KEY, API_SECRET, endpoint)
	clock = api.get_clock()

	for ticker in tickers:
		try:
			position = api.get_position(ticker)
			print(position)
			if sentiment['label'] == 'NEGATIVE' and sentiment['score'] > 0.95:
				rest_client.submit_order(ticker, position.qty)
		except Exception as e:
			if sentiment['label'] == 'POSITIVE' and sentiment['score'] > 0.95:
				rest_client.submit_order(ticker, 1)


stream_client.subscribe_news(news_data_handler, "*")
stream_client.run()
