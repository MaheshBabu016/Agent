from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
import yfinance as yf
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import threading

app = Flask(__name__)
analyzer = SentimentIntensityAnalyzer()

# Your free NewsData.io API key
NEWS_API_KEY = "your_free_newsdata_key"

# Cache dictionary
cache = {"data": [], "last_update": None}
default_tickers = ["AAPL", "TSLA", "MSFT"]

# ---------------------- Core Functions ---------------------- #
def get_stock_data(ticker):
    """Fetch live stock data and 5-day price history."""
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
    """Fetch latest financial news and compute sentiment."""
    try:
        url = f"https://newsdata.io/api/1/news?apikey={NEWS_API_KEY}&q={ticker}&language=en&category=business"
        res = requests.get(url).json()
        news_list = res.get("results", [])[:5]
        sentiments = [analyzer.polarity_scores(n['title'])['compound'] for n in news_list if 'title' in n]
        sentiment_score = round(sum(sentiments) / len(sentiments), 2) if sentiments else 0
        return news_list, sentiment_score
    except:
        return [], 0

def fetch_and_cache():
    """Fetch all data for default tickers and store in cache."""
    print("🔄 Fetching new data...")
    data_list = []
    for t in default_tickers:
        stock_data = get_stock_data(t)
        news, sentiment = get_news_sentiment(t)
        stock_data["sentiment"] = sentiment
        stock_data["news"] = news
        data_list.append(stock_data)
    cache["data"] = data_list
    print("✅ Cache updated successfully!")

# ---------------------- Scheduler Setup ---------------------- #
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_and_cache, "interval", hours=1)
scheduler.start()

# Run first fetch in background thread at startup
threading.Thread(target=fetch_and_cache, daemon=True).start()

# ---------------------- Flask Routes ---------------------- #
@app.route("/", methods=["GET", "POST"])
def index():
    tickers = default_tickers
    if request.method == "POST":
        tickers = [t.strip().upper() for t in request.form["tickers"].split(",")]
    filtered = [d for d in cache["data"] if d["ticker"] in tickers]
    return render_template("index.html", results=filtered)

@app.route("/api/data")
def api_data():
    """Expose cached data via API."""
    return jsonify(cache["data"])

# ---------------------- Main ---------------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

