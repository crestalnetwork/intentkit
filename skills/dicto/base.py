import requests

class DictionarySkillBase:
    SUPPORTED_LANGUAGES = {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "it": "Italian",
        "ja": "Japanese",
        "ru": "Russian",
        "ko": "Korean",
        "pt-BR": "Portuguese (Brazil)",
        "hi": "Hindi",
        "tr": "Turkish"
    }

    def __init__(self, config=None):
        self.api_url = "https://api.dictionaryapi.dev/api/v2/entries/"
        self.default_lang = (config or {}).get("language", "en")
        if self.default_lang not in self.SUPPORTED_LANGUAGES:
            print(f"⚠️ Unsupported default language: {self.default_lang}. Falling back to English.")
            self.default_lang = "en"

    def fetch_word_data(self, word: str, lang: str = None):
        lang_code = lang or self.default_lang
        if lang_code not in self.SUPPORTED_LANGUAGES:
            return None
        try:
            response = requests.get(f"{self.api_url}{lang_code}/{word}", timeout=5)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            print(f"Request error: {e}")
        return None
