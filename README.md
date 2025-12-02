# Oliwka Translator

A warm single-page translator that focuses on Spanish/Russian → Polish. Paste words or bracketed phrases to get precise Polish translations, two example sentences with translations, and automatic grouping into nouns, verbs, adjectives, adverbs, or phrases. You can save entries to a database (PostgreSQL on Railway recommended; falls back to SQLite locally).

## Features
- Auto-detects Spanish or Russian input and translates to Polish using **DeepSeek** (via your API key).
- Handles lists of words and bracketed phrases; phrases stay together and everything else is translated individually.
- Produces two warm example sentences for each entry and translates them to Polish.
- Displays results grouped into five categories (nouns, verbs, adjectives, adverbs, phrases/other).
- Save any entry to the database and view saved words anytime.

## Quickstart
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   flask --app app run --host 0.0.0.0 --port 5000
   ```
   or `python app.py`.
3. Open `http://localhost:5000` and paste your words.

## Railway database
- Provision a PostgreSQL database on Railway and copy the connection string.
- Set the `DATABASE_URL` environment variable to that string (for example, `postgresql+psycopg2://user:pass@host:port/dbname`).
- Deploy the app to Railway; the table `word_entries` will be created automatically.
- The **Saved dictionary** panel reads directly from this database.

### Railway environment variables at a glance
- `DATABASE_URL`: PostgreSQL connection string (falls back to local SQLite when empty).
- `DEEPSEEK_API_KEY`: required to enable translations (DeepSeek is the only translation provider now).
- `DEEPSEEK_MODEL`: optional override of the DeepSeek model (default `deepseek-chat`).
- `DEEPSEEK_BASE_URL`: optional DeepSeek API base URL override (default `https://api.deepseek.com`).

## Configuration
- `DATABASE_URL`: database connection string. Defaults to local SQLite file `translations.db`.
- `DEEPSEEK_API_KEY`: DeepSeek API key. When set, translations will use DeepSeek for the most accurate output.
- `DEEPSEEK_MODEL`: override the DeepSeek model name (defaults to `deepseek-chat`).
- `DEEPSEEK_BASE_URL`: override the DeepSeek API base (defaults to `https://api.deepseek.com`).
- `PORT`: port for the Flask server (defaults to `5000`).

## Notes
- Part-of-speech grouping uses expanded heuristics for Russian and Spanish endings plus phrase detection to better sort verbs/nouns/adjectives/adverbs. Bracketed items such as `(llegar a un acuerdo)` are kept intact and treated as phrases.
- Translation uses DeepSeek exclusively now. Set `DEEPSEEK_API_KEY` so translations can run (the UI banner shows whether the key is detected).
- SQLAlchemy is pinned to `2.0.38` for Python 3.13 compatibility; reinstall dependencies if you hit import errors on Railway.
