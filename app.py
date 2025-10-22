from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import yfinance as yf
import requests
import threading
import pandas as pd

app = Flask(__name__)
analyzer = SentimentIntensityAnalyzer()

# ---------------------- Config ---------------------- #
NEWS_API_KEY = "your_free_newsdata_key"   # Replace with your actual key
cache = {"data": [], "last_update": None}
DEFAULT_TICKERS = ["AAPL", "TSLA", "MSFT"]

# ---------------------- Load All Tickers ---------------------- #
def load_all_tickers():
    """Load all NASDAQ + NYSE tickers from Nasdaq Trader."""
    try:
        nasdaq = pd.read_csv("https://ftp.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", sep="|")
        nyse = pd.read_csv("https://ftp.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", sep="|")
        tickers = sorted(list(set(nasdaq['Symbol'].tolist() + nyse['Symbol'].tolist())))
        return tickers
    except Exception as e:
        print("⚠️ Could not load tickers:", e)
        return DEFAULT_TICKERS

ALL_TICKERS = load_all_tickers()

# ---------------------- Core Functions ---------------------- #
def get_stock_data(ticker):
    """Fetch live stock data and 5-day history."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        info = stock.info
        prices = hist['Close'].round(2).tolist()
        dates = hist.index.strftime('%Y-%m-%d').tolist()
        return {
            "ticker": ticker,
            "price": round(info.get("currentPrice", 0), 2),
            "volume": info.get("volume"),
            "marketCap": info.get("marketCap"),
            "previousClose": info.get("previousClose"),
            "open": info.get("open"),
            "prices": prices,
            "dates": dates,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

def get_news_sentiment(ticker):
    """Fetch latest news and compute sentiment."""
    try:
        url = f"https://newsdata.io/api/1/news?apikey={NEWS_API_KEY}&q={ticker}&language=en&category=business"
        res = requests.get(url).json()
        news_list = res.get("results", [])[:5]
        sentiments = [analyzer.polarity_scores(n['title'])['compound'] for n in news_list if 'title' in n]
        sentiment_score = round(sum(sentiments) / len(sentiments), 2) if sentiments else 0
        return news_list, sentiment_score
    except Exception:
        return [], 0

def fetch_and_cache(tickers=None):
    """Fetch stock + sentiment data for selected tickers."""
    tickers = tickers or DEFAULT_TICKERS
    print(f"🔄 Fetching data for: {', '.join(tickers[:5])}...")
    data_list = []
    for t in tickers:
        stock_data = get_stock_data(t)
        news, sentiment = get_news_sentiment(t)
        stock_data["sentiment"] = sentiment
        stock_data["news"] = news
        data_list.append(stock_data)
    cache["data"] = data_list
    print("✅ Cache updated successfully!")

# ---------------------- Scheduler ---------------------- #
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_and_cache, "interval", hours=1)
scheduler.start()
threading.Thread(target=fetch_and_cache, daemon=True).start()

# ---------------------- Routes ---------------------- #
@app.route("/", methods=["GET", "POST"])
def index():
    tickers = DEFAULT_TICKERS
    if request.method == "POST":
        tickers_input = request.form.get("tickers", "")
        if tickers_input.strip():
            tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip().upper() in ALL_TICKERS]
            fetch_and_cache(tickers)  # Fetch only for requested
    filtered = [d for d in cache["data"] if d["ticker"] in tickers]
    return render_template("index.html", results=filtered, tickers=ALL_TICKERS)

@app.route("/api/data")
def api_data():
    """Expose cached data."""
    return jsonify(cache["data"])

# ---------------------- Run ---------------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
