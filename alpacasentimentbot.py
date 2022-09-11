from alpaca_trade_api import REST, Stream
from transformers import pipeline

API_KEY = 'PKBZFTD9KPUGALJOW7EY'
API_SECRET = '4W8IkPJXCo7WoiEOZPVyURyc1ojnAcW299bSdXwP'

classifier = pipeline('sentiment-analysis')
stream_client = Stream(API_KEY, API_SECRET)
rest_client = REST(API_KEY, API_SECRET)
#historical_news = rest_client.get_news("AAPL", "2022-01-01", "2022-09-01")
#print(historical_news)


async def news_data_handler(news):

	summary = news.summary
	headline = news.headline

	relevant_text = summary + headline
	sentiment = classifier(relevant_text)

	if sentiment['label'] == 'POSITIVE' and sentiment['score'] > 0.95:
		rest_client.submit_order("AAPL", 100)

	elif sentiment['label'] == 'NEGATIVE' and sentiment['score'] > 0.95:
		rest_client.submit_order("AAPL", -100)


stream_client.subscribe_news(news_data_handler, "AAPL")
stream_client.run()
