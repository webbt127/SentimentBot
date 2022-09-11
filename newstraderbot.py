#Import Required libraries
from urllib.request import urlopen, Request
from bs4 import BeautifulSoup
import pandas as pd

#Import Dependencies for sentiment analysis using our neural network
import tensorflow as tf
import numpy
import pickle
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
import numpy as np
import alpaca_trade_api as tradeapi
import time
import warnings
warnings.filterwarnings("ignore")

finviz_url = "https://finviz.com/quote.ashx?t="
tickers = {"TSLA", "NIO", "AMD", "NVDA", "GME", "AAPL", "SPY", "SHOP", "INTC", "ATVI", "META"}

def preprocessText(text):
    sequences = tokenizer.texts_to_sequences(text)
    padded = pad_sequences(sequences, maxlen=max_length, padding=padding_type, truncating=trunc_type)
    return padded

while True:
    for ticker in tickers:
        url = finviz_url + ticker
        req = Request(url=url, headers={'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'})
        response = urlopen(req)


        news_table = {}
        html = BeautifulSoup(response, features="html.parser")
        news_table = html.find(id='news-table')

        dataRows = news_table.findAll('tr')
        df = pd.DataFrame(columns=['News_Title', 'Time'])
        for i, table_row in enumerate(dataRows):
            if hasattr(table_row.a, 'text'):
                a_text = table_row.a.text
                td_text = table_row.td.text
    
            df = df.append({'News_Title': a_text, 'Time': td_text}, ignore_index=True)

        with open('./tokenizer.pickle', 'rb') as handle:
            tokenizer = pickle.load(handle)
        model = tf.keras.models.load_model('./model1.h5')

        oov_tok = '<OOV>'
        trunc_type = 'post'
        padding_type='post'
        vocab_size = 1000
        max_length = 142

        prep = preprocessText(df.News_Title)
        prep = model.predict(prep)
        df['sent'] = np.argmax(prep, axis=-1)

        api = tradeapi.REST("PKBZFTD9KPUGALJOW7EY", "4W8IkPJXCo7WoiEOZPVyURyc1ojnAcW299bSdXwP", "https://paper-api.alpaca.markets")
        account = api.get_account()

        modeSentiment = df.sent.mode().iloc[0]
        print(ticker, "Most Recent News Title", [df['News_Title'].iloc[0]], "Sentiment:", df['sent'].iloc[0])
        print(ticker, "Positive Sentiment Counts:", df['sent'].value_counts().loc[2])
        print(ticker, "Negative Sentiment Counts:", df['sent'].value_counts().loc[0])
        clock = api.get_clock()
        sentiment_ratio = df['sent'].value_counts().loc[2] / df['sent'].value_counts().loc[0]

        if clock.is_open:
            try:
                position = api.get_position(ticker)
                print(position)
                if sentiment_ratio < 1 or df['sent'].iloc[0] == 0:
                    api.submit_order(
                        symbol=ticker,
                        qty=position.qty,
                        side='sell',
                        type='market',
                        time_in_force='gtc'
                    )
                    print("SELL " + ticker)
            except Exception as e:
                if sentiment_ratio >= 2 and df['sent'].iloc[0] == 2:
                    api.submit_order(
                        symbol=ticker,
                        notional=1000,
                        side='buy',
                        type='market',
                        time_in_force='gtc'
                    )
                    print("BUY " + ticker)
        else:
            print("Market is Closed!")
    if clock.is_open == False:
        print("Market is Closed! Sleeping for 10 minutes...")
        time.sleep(600)
