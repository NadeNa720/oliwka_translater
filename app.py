import json
import os
import re
from typing import Dict, List

import requests
from deep_translator import GoogleTranslator
from flask import Flask, jsonify, render_template, request
from langdetect import detect
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = Flask(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///translations.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class WordEntry(Base):
    __tablename__ = "word_entries"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String, nullable=False)
    language = Column(String, nullable=False)
    part_of_speech = Column(String, nullable=False)
    translations = Column(String, nullable=False)  # Stored as JSON string for portability
    examples = Column(String, nullable=False)  # Stored as JSON string


Base.metadata.create_all(bind=engine)

# LibreTranslate endpoints (primary + fallbacks)
_primary_endpoint = os.getenv("LIBRETRANSLATE_URL")
LINGVA_ENDPOINT = os.getenv("LINGVA_ENDPOINT", "https://lingva.ml")
LIBRETRANSLATE_ENDPOINTS = [
    endpoint
    for endpoint in [
        _primary_endpoint,
        "https://translate.astian.org",
        "https://libretranslate.de",
        "https://translate.argosopentech.com",
    ]
    if endpoint
]
SUPPORTED_LANGS = {"ru", "es"}


# Translation helpers

def detect_language(text: str) -> str:
    """Detect language between Russian and Spanish; default to auto if unclear."""
    # Quick alphabet checks to avoid misclassifying Spanish as Polish
    if re.search("[\u0400-\u04FF]", text):  # Cyrillic block
        return "ru"

    if re.search("[áéíóúñÁÉÍÓÚÑ]", text):
        return "es"

    lowered = text.lower()
    # Common Spanish function words to capture short phrases that langdetect mislabels
    if re.search(r"\b(el|la|los|las|un|una|que|de|y|por|para|con)\b", lowered):
        return "es"

    try:
        lang = detect(text)
        if lang in SUPPORTED_LANGS:
            return lang
    except Exception:
        pass
    return "auto"


def detect_any_language(text: str) -> str:
    """Detect language without restricting to Russian/Spanish."""
    try:
        return detect(text)
    except Exception:
        return "auto"


def translate_text(text: str, source_lang: str = "auto", target_lang: str = "pl") -> str:
    payload = {
        "q": text,
        "source": source_lang,
        "target": target_lang,
        "format": "text",
    }

    detected_any = detect_any_language(text)
    # If source and target are the same (e.g., Polish helper sentences), avoid useless calls
    if (source_lang != "auto" and source_lang == target_lang) or (
        source_lang == "auto" and detected_any == target_lang
    ):
        return text

    # Primary: Google via deep_translator (handles language auto-detect internally)
    try:
        src = source_lang if source_lang != "auto" else detected_any or "auto"
        translated = GoogleTranslator(source=src, target=target_lang).translate(text)
        if translated:
            return translated
    except Exception as exc:
        print(f"Deep-translator Google error for '{text}': {exc}")

    # Secondary: Lingva (Google-compatible proxy with free public instances)
    try:
        src = source_lang if source_lang != "auto" else detected_any or "auto"
        quoted = requests.utils.quote(text)
        url = f"{LINGVA_ENDPOINT}/api/v1/{src}/{target_lang}/{quoted}"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        translated = data.get("translation") if isinstance(data, dict) else ""
        if translated:
            return translated
    except Exception as exc:
        print(f"Lingva translation error for '{text}': {exc}")

    # Tertiary: LibreTranslate instances
    for endpoint in LIBRETRANSLATE_ENDPOINTS:
        try:
            response = requests.post(f"{endpoint}/translate", data=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            translated = data.get("translatedText", "")
            if translated:
                return translated
        except Exception as exc:
            print(f"Translation error for '{text}' via {endpoint}: {exc}")
            continue

    # Fallback: MyMemory (free, public) to avoid full outages
    try:
        # MyMemory needs an explicit pair; it does not accept "auto". Prefer a detected
        # language, fall back to English as a neutral default for better resilience.
        src_guess = source_lang if source_lang != "auto" else detected_any
        src = src_guess if isinstance(src_guess, str) and len(src_guess) == 2 else "en"
        if src == target_lang:
            return text
        params = {"q": text, "langpair": f"{src}|{target_lang}"}
        response = requests.get(
            "https://api.mymemory.translated.net/get", params=params, timeout=15
        )
        response.raise_for_status()
        data = response.json()
        translated = data.get("responseData", {}).get("translatedText", "")
        if translated:
            return translated
    except Exception as exc:
        print(f"MyMemory fallback error for '{text}': {exc}")

    # If all endpoints fail, return empty string so the UI can show a friendly message
    return ""


def classify_part_of_speech(word: str, lang: str, is_phrase: bool) -> str:
    if is_phrase or " " in word:
        return "phrases"

    # Simple heuristics for Spanish
    if lang == "es":
        if word.endswith("mente"):
            return "adverbs"
        if word.endswith("o") or word.endswith("a") or word.endswith("e"):
            # could be noun or adjective; we will mark adjectives if ends with -oso/-osa
            if word.endswith("oso") or word.endswith("osa"):
                return "adjectives"
            return "nouns"
        if word.endswith("ar") or word.endswith("er") or word.endswith("ir"):
            return "verbs"
    # Simple heuristics for Russian
    if lang == "ru":
        if word.endswith("о"):
            return "adverbs"
        if word.endswith("ый") or word.endswith("ая") or word.endswith("ое"):
            return "adjectives"
        if word.endswith("ть") or word.endswith("ться"):
            return "verbs"
        if word.endswith("н") or word.endswith("а") or word.endswith("о") or word.endswith("е"):
            return "nouns"

    return "phrases"


def generate_examples(word: str, lang: str) -> List[Dict[str, str]]:
    """Generate two warm, simple sentences using the word and translate them."""
    sentence_templates = {
        "es": [
            f"Siempre trato de {word} para sentirme en paz.",
            f"Mis amigos y yo hablamos sobre cómo {word} cambia nuestras vidas.",
        ],
        "ru": [
            f"Я часто думаю, как {word} помогает нам в повседневной жизни.",
            f"Друзья напоминают мне, что {word} приносит уют и уверенность.",
        ],
        "auto": [
            f"Zawsze myślę, jak {word} pomaga w codzienności.",
            f"Przyjaciele mówią mi, że {word} dodaje otuchy.",
        ],
    }
    templates = sentence_templates.get(lang, sentence_templates["auto"])
    examples = []
    for sentence in templates:
        translated = translate_text(sentence, source_lang=lang if lang in SUPPORTED_LANGS else "auto")
        examples.append({"source": sentence, "target": translated or ""})
    return examples


def parse_entries(raw: str) -> List[str]:
    # Keep bracketed phrases together, otherwise split on commas or new lines
    tokens = re.findall(r"\([^)]*\)|[^,\n]+", raw)
    entries = []
    for token in tokens:
        word = token.strip()
        if not word:
            continue
        if word.startswith("(") and word.endswith(")"):
            word = word[1:-1].strip()
        entries.append(word)
    return entries


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/api/translate")
def translate_route():
    payload = request.get_json(force=True)
    raw_text: str = payload.get("text", "")
    entries = parse_entries(raw_text)
    grouped: Dict[str, List[Dict[str, str]]] = {
        "nouns": [],
        "verbs": [],
        "adjectives": [],
        "adverbs": [],
        "phrases": [],
    }

    for entry in entries:
        lang = detect_language(entry)
        translations = translate_text(entry, source_lang=lang)
        pos = classify_part_of_speech(entry, lang, is_phrase=" " in entry)
        examples = generate_examples(entry, lang)
        grouped[pos].append(
            {
                "word": entry,
                "language": lang,
                "translations": translations,
                "examples": examples,
                "part_of_speech": pos,
            }
        )

    return jsonify(grouped)


@app.post("/api/save")
def save_word():
    payload = request.get_json(force=True)
    entry = WordEntry(
        word=payload.get("word"),
        language=payload.get("language", "auto"),
        part_of_speech=payload.get("part_of_speech", "phrases"),
        translations=json.dumps(payload.get("translations")),
        examples=json.dumps(payload.get("examples")),
    )
    with SessionLocal() as session:
        session.add(entry)
        session.commit()
    return jsonify({"status": "saved"})


@app.get("/api/saved")
def saved_words():
    with SessionLocal() as session:
        entries = session.query(WordEntry).all()
    saved = [
        {
            "id": e.id,
            "word": e.word,
            "language": e.language,
            "part_of_speech": e.part_of_speech,
            "translations": json.loads(e.translations),
            "examples": json.loads(e.examples),
        }
        for e in entries
    ]
    return jsonify(saved)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
