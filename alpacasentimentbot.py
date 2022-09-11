from alpaca_trade_api import REST, Stream
from transformers import pipeline

API_KEY = 'PKBZFTD9KPUGALJOW7EY'
API_SECRET = '4W8IkPJXCo7WoiEOZPVyURyc1ojnAcW299bSdXwP'

classifier = pipeline('sentiment-analysis')


async def news_data_handler(news):

	summary = news.summary
	headline = news.headline

	relevant_text = summary + headline
	sentiment = classifier(relevant_text)

	if sentiment['label'] == 'POSITIVE' and sentiment['score'] > 0.95:
		rest_client.submit_order("AAVEUSD", 100)

	elif sentiment['label'] == 'NEGATIVE' and sentiment['score'] > 0.95:
		rest_client.submit_order("AAVEUSD", -100)


	stream_client.subscribe_news(news_data_handler, "AAVEUSD")

	stream_client.run()
