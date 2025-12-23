from abstracts.skill import IntentKitSkill
from .models import DictoInput, DictoOutput
import requests

class DictoSkill(IntentKitSkill):
    name: str = "dicto"
    description: str = "Looks up dictionary definitions for a given word."
    args_schema = DictoInput

    def _run(self, word: str, lang: str = "en") -> DictoOutput:
        word = word.strip().lower()
        if not word:
            return DictoOutput(result="Please provide a word to define.")

        try:
            response = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/{lang}/{word}")
            if response.status_code != 200:
                raise ValueError("Word not found.")
            data = response.json()
            definitions = data[0]['meanings'][0]['definitions'][0]['definition']
            result = f"🔍 Looking up \"{word}\"\n📖 Definition: {definitions}\n\nView More on Dictionary: https://www.google.com/search?q=define+{word}"
            return DictoOutput(result=result)
        except Exception as e:
            return DictoOutput(result=f"Sorry, we couldn't find a definition for \"{word}\" in `{lang}`.\n\nView More on Dictionary: https://www.google.com/search?q=define+{word}")
