import json
import os
import re
from typing import Dict, List

import requests
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

# DeepSeek configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
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


def translate_with_examples(text: str, source_lang: str = "auto", target_lang: str = "pl") -> Dict[str, str]:
    """Use DeepSeek to get a translation, examples, and part of speech in one call."""

    detected_any = detect_any_language(text)
    if (source_lang != "auto" and source_lang == target_lang) or (
        source_lang == "auto" and detected_any == target_lang
    ):
        return {
            "translation": text,
            "examples": [],
            "part_of_speech": "phrases",
        }

    if not DEEPSEEK_API_KEY:
        return {
            "translation": "(DeepSeek API key is not configured)",
            "examples": [],
            "part_of_speech": "phrases",
        }

    src = source_lang if source_lang != "auto" else detected_any or "auto"
    system_prompt = (
        "You are a precise, concise translator for Spanish or Russian into Polish. "
        "Respond ONLY with valid JSON."
    )
    user_prompt = (
        "Return a compact JSON object with fields: translation (Polish), part_of_speech "
        "(nouns, verbs, adjectives, adverbs, phrases), and examples (two natural sentences "
        "in the source language that use the word/phrase correctly, each with a Polish "
        "translation). Avoid literal word-by-word Polish; keep it natural. Use warm, everyday "
        "tone. Do not include any text outside JSON. Example structure: {\"translation\": "
        "\"...\", \"part_of_speech\": \"verbs\", \"examples\": [{\"source\": \"...\", \"target\": \"...\"}, {\"source\": \"...\", \"target\": \"...\"}]}. "
        f"Source language: {src}. Target language: {target_lang}. Text: {text}"
    )

    try:
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
                "temperature": 0.15,
                "max_tokens": 500,
            },
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
        content = (
            data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        )
        parsed = json.loads(content)
        translation = parsed.get("translation", "").strip()
        examples = parsed.get("examples", []) or []
        pos = parsed.get("part_of_speech", "phrases").lower()
        return {
            "translation": translation,
            "examples": examples,
            "part_of_speech": pos,
        }
    except Exception as exc:
        print(f"DeepSeek translation error for '{text}': {exc}")
        return {"translation": "", "examples": [], "part_of_speech": "phrases"}


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


def fallback_examples(word: str, lang: str) -> List[Dict[str, str]]:
    """Warm hardcoded examples used only when DeepSeek returns nothing."""
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
    return [{"source": s, "target": ""} for s in templates]


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


@app.get("/api/status")
def status():
    return jsonify({"deepseek_configured": bool(DEEPSEEK_API_KEY)})


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

    allowed_pos = {"nouns", "verbs", "adjectives", "adverbs", "phrases"}

    for entry in entries:
        lang = detect_language(entry)
        ds_response = translate_with_examples(entry, source_lang=lang)
        translations = ds_response.get("translation", "")
        pos_raw = (ds_response.get("part_of_speech") or "phrases").strip().lower()
        pos_aliases = {
            "verb": "verbs",
            "noun": "nouns",
            "adjective": "adjectives",
            "adverb": "adverbs",
            "phrase": "phrases",
            "phrases/other": "phrases",
        }
        pos = pos_aliases.get(pos_raw, pos_raw)
        if pos not in allowed_pos:
            pos = classify_part_of_speech(entry, lang, is_phrase=" " in entry)
        examples = ds_response.get("examples") or fallback_examples(entry, lang)
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
