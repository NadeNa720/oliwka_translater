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
GOOGLE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
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

    # Spanish verb endings often appear in raw input even when users add Polish hints
    if re.search(r"(ar|er|ir)$", text.lower()):
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

    # Premium: DeepSeek API when a key is configured
    if DEEPSEEK_API_KEY:
        try:
            src = source_lang if source_lang != "auto" else detected_any or "auto"
            system_prompt = (
                "You are a precise translation engine. Return only the translated text in Polish."
            )
            user_prompt = (
                "Translate to Polish. If a source language is provided, respect it. "
                f"Source language: {src}. Text: {text}"
            )
            response = requests.post(
                f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 400,
                },
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            translated = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if translated:
                return translated
        except Exception as exc:
            print(f"DeepSeek translation error for '{text}': {exc}")

    # Primary: Official Google Translate API if an API key is present
    if GOOGLE_API_KEY:
        try:
            params = {
                "q": text,
                "target": target_lang,
                "format": "text",
                "key": GOOGLE_API_KEY,
            }
            if source_lang != "auto":
                params["source"] = source_lang
            response = requests.post(
                "https://translation.googleapis.com/language/translate/v2",
                data=params,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            translated = data.get("data", {}).get("translations", [{}])[0].get("translatedText", "")
            if translated:
                return translated
        except Exception as exc:
            print(f"Google API translation error for '{text}': {exc}")

    # Secondary: Google via deep_translator (handles language auto-detect internally)
    try:
        src = source_lang if source_lang != "auto" else detected_any or "auto"
        translated = GoogleTranslator(source=src, target=target_lang).translate(text)
        if translated:
            return translated
    except Exception as exc:
        print(f"Deep-translator Google error for '{text}': {exc}")

    # Next: Lingva (Google-compatible proxy with free public instances)
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

    # Then: LibreTranslate instances
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

    cleaned = re.sub(r"[.,;:!?]$", "", word.lower())

    if lang == "es":
        # Adverbs typically end with -mente
        if cleaned.endswith("mente"):
            return "adverbs"

        # Verb gerunds and participles
        if cleaned.endswith(("ando", "iendo", "ado", "ido")):
            return "verbs"

        # Infinitive verbs (including reflexive forms)
        if cleaned.endswith(("ar", "er", "ir", "arse", "erse", "irse")):
            return "verbs"

        # Adjectival endings
        if cleaned.endswith(("oso", "osa", "ivo", "iva", "able", "ible", "al", "ario", "aria")):
            return "adjectives"

        # Common noun suffixes
        if cleaned.endswith(("ción", "sión", "dad", "tad", "ura", "aje", "ez", "eza")):
            return "nouns"

        # Default for Spanish single words: noun
        return "nouns"

    if lang == "ru":
        # Adverbs
        if cleaned.endswith("о"):
            return "adverbs"

        # Adjectives (full and short forms)
        if cleaned.endswith(("ый", "ий", "ой", "ая", "яя", "ое", "ее", "ие", "ые")):
            return "adjectives"

        # Verbs (infinitives and common present/future endings)
        if cleaned.endswith(("ть", "ти", "чь", "ться", "тись", "ют", "ет", "ут", "ат", "ят", "ешь", "ишь", "им", "ем")):
            return "verbs"

        # Nouns (default for single Russian words)
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
        # Drop in-line glosses like "explicar — rozwinięcie" so detection works
        if "—" in word:
            word = word.split("—", 1)[0].strip()
        elif " - " in word:
            word = word.split(" - ", 1)[0].strip()
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
