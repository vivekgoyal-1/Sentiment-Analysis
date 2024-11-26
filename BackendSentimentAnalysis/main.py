from flask import Flask, request, jsonify
import os
import pandas as pd
from datetime import datetime
from textblob import TextBlob
import tweepy
import praw
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
TWITTER_BEARER_TOKEN = 'AAAAAAAAAAAAAAAAAAAAAKWnwwEAAAAA8r%2BS8aeU410CNwgkgdlKpkoFbRA%3DKN3qW7qbLfACC8aeWt0WCjpKwOI9nrmLfLQ883aaj2XDFBxA0c'
# Enabling CORS for all domains (could be adjusted for specific origins)
# Reddit API credentials
REDDIT_CLIENT_ID = '4iPff6qqZ05gOPC28-KrXA'
REDDIT_CLIENT_SECRET = '47-2f9lmwv5mncUPMvxhKxZ1Y5pfvA'
REDDIT_USER_AGENT = 'app'

# NewsAPI credentials
NEWS_API_KEY = '7d848ef0eb784979a9bdf526c2b15e8f'


# --- Twitter-related functions are commented out ---
# def twitter_auth():
#     """Authenticate using Twitter API v2 Bearer Token."""
#     return tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

# def fetch_twitter_data(keyword, count=100):
#     """Fetch data from Twitter based on a keyword using API v2."""
#     client = twitter_auth()
#     tweets_data = []
#     try:
#         tweets = client.search_recent_tweets(query=keyword, max_results=count, tweet_fields=['public_metrics'], expansions='author_id')
#         users = {u["id"]: u for u in tweets.includes["users"]}

#         for tweet in tweets.data:
#             user = users.get(tweet.author_id)
#             tweets_data.append({
#                 'platform': 'Twitter',
#                 'heading': user.username if user else "Unknown User",
#                 'description': tweet.text,  # Tweet description is the text of the tweet itself
#                 'image_url': user.profile_image_url if user else None,
#                 'likes': tweet.public_metrics['like_count'],
#                 'dislikes': 0  # Twitter doesn't provide dislikes
#             })
#     except tweepy.TweepyException as e:
#         print(f"Error fetching Twitter data: {e}")
#     return tweets_data


def reddit_auth():
    """Authenticate Reddit API."""
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT
    )


def fetch_reddit_data(keyword, count=1000):
    """Fetch data from Reddit based on a keyword."""
    reddit = reddit_auth()
    reddit_data = []
    try:
        for submission in reddit.subreddit("all").search(keyword, limit=count):
            reddit_data.append({
                'platform': 'Reddit',
                'heading': submission.title,
                'description': submission.selftext if submission.selftext else "No description",  # Reddit post description
                'image_url': submission.url if submission.url.endswith(('jpg', 'png')) else None,
                'likes': submission.score,
                'dislikes': 0  # Reddit doesn't provide dislikes
            })
    except Exception as e:
        print(f"Error fetching Reddit data: {e}")
    return reddit_data


def fetch_news_data(keyword, count=10):
    """Fetch data from NewsAPI based on a keyword."""
    url = f'https://newsapi.org/v2/everything?q={keyword}&apiKey={NEWS_API_KEY}&pageSize={count}'
    news_data = []
    try:
        response = requests.get(url)
        if response.status_code == 200:
            articles = response.json().get('articles', [])
            for article in articles:
                news_data.append({
                    'platform': 'NewsAPI',
                    'heading': article['title'],
                    'description': article['description'] if article['description'] else "No description",  # News article description
                    'image_url': article['urlToImage'],
                    'likes': 0,  # NewsAPI doesn't provide likes or dislikes
                    'dislikes': 0
                })
        else:
            print(f"Error fetching news data: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error with NewsAPI request: {e}")
    return news_data


def load_data_from_folder(folder_path):
    """Load all CSV files from the given folder and return a concatenated DataFrame."""
    all_data = []
    if not os.path.exists(folder_path):
        print(f"Folder '{folder_path}' does not exist.")
        return pd.DataFrame()
    
    for filename in os.listdir(folder_path):
        if filename.endswith(".csv"):
            file_path = os.path.join(folder_path, filename)
            print(f"Loading data from {file_path}")
            df = pd.read_csv(file_path)
            all_data.append(df)
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        return pd.DataFrame()


def clean_data(df):
    """Clean the data by removing unnecessary columns and handling missing values."""
    df = df[['platform', 'heading', 'description', 'image_url', 'likes', 'dislikes']]
    df['description'].fillna('No description available', inplace=True)
    df['likes'].fillna(0, inplace=True)
    df['dislikes'].fillna(0, inplace=True)
    df = df.dropna(subset=['heading', 'description'], how='all')
    df.drop_duplicates(inplace=True)
    return df


def sentiment_analysis(text):
    """Analyze sentiment of a given text using TextBlob with polarity and subjectivity."""
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    subjectivity = blob.sentiment.subjectivity
    
    sentiment = 'Neutral'
    description = 'The sentiment is neutral and objective.'

    if polarity > 0:
        sentiment = 'Positive'
        description = 'The sentiment is positive, and the text conveys a favorable opinion.'
    elif polarity < 0:
        sentiment = 'Negative'
        description = 'The sentiment is negative, and the text conveys an unfavorable opinion.'
    
    return {
        'sentiment': sentiment,
        'polarity': polarity,
        'subjectivity': subjectivity,
        'description': description
    }


def apply_sentiment_analysis(df):
    """Apply sentiment analysis to 'heading' and 'description'."""
    df['combined_text'] = df['heading'] + " " + df['description']
    sentiment_data = df['combined_text'].apply(sentiment_analysis)
    df['sentiment'] = sentiment_data.apply(lambda x: x['sentiment'])
    df['polarity'] = sentiment_data.apply(lambda x: x['polarity'])
    df['subjectivity'] = sentiment_data.apply(lambda x: x['subjectivity'])
    df['sentiment_description'] = sentiment_data.apply(lambda x: x['description'])
    return df


def final_verdict(df):
    """Generate final verdict based on sentiment analysis."""
    sentiment_counts = df['sentiment'].value_counts()
    positive_count = sentiment_counts.get('Positive', 0)
    negative_count = sentiment_counts.get('Negative', 0)
    neutral_count = sentiment_counts.get('Neutral', 0)

    # Final verdict logic
    if positive_count > negative_count and positive_count > neutral_count:
        verdict = "Overall Positive"
        detailed_verdict = f"The majority of the statements are positive, with {positive_count} positive sentiments compared to {negative_count} negative and {neutral_count} neutral."
    elif negative_count > positive_count and negative_count > neutral_count:
        verdict = "Overall Negative"
        detailed_verdict = f"The majority of the statements are negative, with {negative_count} negative sentiments compared to {positive_count} positive and {neutral_count} neutral."
    else:
        verdict = "Mixed or Neutral"
        detailed_verdict = f"The sentiments are mixed, with {positive_count} positive, {negative_count} negative, and {neutral_count} neutral sentiments."

    return verdict, detailed_verdict


@app.route('/')
def home():
    return "App is running successfully!", 200


@app.route('/generate_report', methods=['POST'])
def generate_report():
    try:
        print("Function called")
            
        # Get the statement from the request
        statement = request.json.get("statement", "")
        if not statement:
            return jsonify({"error": "No statement provided"}), 400

        # Fetch data from APIs
        reddit_data = fetch_reddit_data(statement)
        news_data = fetch_news_data(statement)

        # Create dataset from the fetched data
        data = reddit_data + news_data

        if data:
            df = pd.DataFrame(data)

            # Clean and analyze the data
            df_cleaned = clean_data(df)
            df_analyzed = apply_sentiment_analysis(df_cleaned)

            # Generate final verdict
            verdict, detailed_verdict = final_verdict(df_analyzed)

            return jsonify({
                "verdict": verdict,
                "detailed_verdict": detailed_verdict,
                "data": df_analyzed.to_dict(orient="records")
            })

        else:
            return jsonify({"error": "No relevant data found"}), 404

    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"error": "An error occurred while generating the report"}), 500


if __name__ == '__main__':
    app.run(debug=True)
