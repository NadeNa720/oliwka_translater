# Oliwka Translator

A warm single-page translator that focuses on Spanish/Russian → Polish. Paste words or bracketed phrases to get precise Polish translations, two example sentences with translations, and automatic grouping into nouns, verbs, adjectives, adverbs, or phrases. You can save entries to a database (PostgreSQL on Railway recommended; falls back to SQLite locally).

## Features
- Auto-detects Spanish or Russian input and translates to Polish using a reliable chain (official Google API with your key or deep-translator Google first, then Lingva, LibreTranslate, and MyMemory fallbacks).
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

## Configuration
- `DATABASE_URL`: database connection string. Defaults to local SQLite file `translations.db`.
- `LIBRETRANSLATE_URL`: override the primary translation endpoint if you self-host LibreTranslate; the app automatically falls back to public LibreTranslate instances if one endpoint is unreachable.
- `LINGVA_ENDPOINT`: optional Lingva base URL (defaults to `https://lingva.ml`) used as a free proxy before LibreTranslate/MyMemory if Google is unavailable.
- `GOOGLE_TRANSLATE_API_KEY`: optional official Google Translate API key. When set, translations will use the paid API first for the best quality and language detection, then fall back to free providers.
- `PORT`: port for the Flask server (defaults to `5000`).

## Notes
- Part-of-speech grouping uses expanded heuristics for Russian and Spanish endings plus phrase detection to better sort verbs/nouns/adjectives/adverbs. Bracketed items such as `(llegar a un acuerdo)` are kept intact and treated as phrases.
- Translation order now prioritizes the official Google API (if `GOOGLE_TRANSLATE_API_KEY` is set), then the deep-translator Google client, Lingva as a Google-compatible free proxy, public LibreTranslate instances, and finally the free MyMemory API. Override `LIBRETRANSLATE_URL` if you self-host LibreTranslate, and `LINGVA_ENDPOINT` if you run your own Lingva instance.
- SQLAlchemy is pinned to `2.0.38` for Python 3.13 compatibility; reinstall dependencies if you hit import errors on Railway.
