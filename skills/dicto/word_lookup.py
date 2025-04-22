import requests
from base import DictionarySkillBase

class LookupWord(DictionarySkillBase):
    def run(self, input_text):
        input_text = input_text.strip()

        if not input_text:
            return "Please provide a word or phrase to define."

        tokens = input_text.split()
        potential_lang = tokens[0].lower()

        if potential_lang in self.SUPPORTED_LANGUAGES and len(tokens) > 1:
            lang = potential_lang
            word = " ".join(tokens[1:])
        else:
            lang = self.default_lang
            word = input_text

        word = word.lower()
        data = self.fetch_word_data(word, lang)

        if not data:
            data = self.fetch_word_data_from_fallback(word, lang)

        if not data:
            return f"Sorry, we couldn't find a definition for \"{word}\" in `{lang}`.\n\nView More on Dictionary: https://www.google.com/search?q=define+{word}"

        output = [f"🔍 Looking up \"{word}\""]
        seen_defs = set()
        all_defs = []
        first_definition = None
        limit = 0

        for entry in data:
            for meaning in entry.get("meanings", []):
                part_of_speech = meaning.get("partOfSpeech", "Other").capitalize()
                for definition in meaning.get("definitions", []):
                    if limit >= 6:
                        break
                    def_text = definition.get("definition", "").strip()
                    example = definition.get("example", "").strip()
                    if def_text and def_text not in seen_defs:
                        seen_defs.add(def_text)
                        if not first_definition:
                            first_definition = def_text
                        line = f"{part_of_speech}: {def_text}"
                        if example:
                            line += f" (Example: {example})"
                        all_defs.append(line)
                        limit += 1
                if limit >= 6:
                    break
            if limit >= 6:
                break

        if first_definition:
            output.append(f"📖 Definition: {first_definition}")

        output.extend(all_defs[1:] if len(all_defs) > 1 else [])
        output.append(f"\nView More on Dictionary: https://www.google.com/search?q=define+{word}")
        return "\n".join(output)

    def fetch_word_data_from_fallback(self, word, lang):
        try:
            fallback_url = f"https://some-other-dictionary-api.com/{lang}/{word}"
            response = requests.get(fallback_url, timeout=5)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass
        return None
