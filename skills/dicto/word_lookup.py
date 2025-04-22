import requests
from base import DictionarySkillBase

class LookupWord(DictionarySkillBase):
    def run(self, input_text):
        input_text = input_text.strip()

        if not input_text:
            return "Please provide a word or phrase to define."

        # Detect if the first word is a supported language code
        tokens = input_text.split()
        potential_lang = tokens[0].lower()

        if potential_lang in self.SUPPORTED_LANGUAGES and len(tokens) > 1:
            lang = potential_lang
            word = " ".join(tokens[1:])
        else:
            lang = self.default_lang
            word = input_text

        word = word.lower()

        # Try fetching from primary API
        data = self.fetch_word_data(word, lang)
        if not data:
            # Try fallback if primary failed
            data = self.fetch_word_data_from_fallback(word, lang)

        if not data:
            return f"Sorry, we couldn't find a definition for \"{word}\" in `{lang}`.\n\nView More on Dictionary: https://www.google.com/search?q=define+{word}"

        output = [f"🔍 Looking up \"{word.capitalize()}\""]

        # Handle cases where `data` is a list
        if isinstance(data, list):
            brief_definition = data[0].get('briefDefinition', None) if data else None
            if brief_definition:
                output.append(f"\n📖 Definition: {brief_definition}")

            seen_defs = set()
            limit = 0
            for entry in data:
                for meaning in entry.get("meanings", []):
                    part_of_speech = meaning.get("partOfSpeech", "Other").capitalize()
                    for definition in meaning.get("definitions", []):
                        if limit >= 6:
                            break  # limit total definitions
                        definition_text = definition.get("definition", "").strip()
                        example = definition.get("example")
                        if definition_text and definition_text not in seen_defs:
                            seen_defs.add(definition_text)
                            line = f"{part_of_speech}: {definition_text}"
                            if example:
                                line += f" (Example: {example})"
                            output.append(line)
                            limit += 1
                    if limit >= 6:
                        break  # Stop after reaching limit
                if limit >= 6:
                    break  # Stop after reaching limit
        else:
            return f"Sorry, the data returned for \"{word}\" in `{lang}` is not in the expected format."

        if not output:
            return f"Sorry, we couldn't find a definition for \"{word}\" in `{lang}`.\n\nView More on Dictionary: https://www.google.com/search?q=define+{word}"

        # Add "View More" link at the end of the output
        output.append(f"\n\nView More on Dictionary: https://www.google.com/search?q=define+{word}")

        return "\n".join(output)

    def fetch_word_data_from_fallback(self, word, lang):
        try:
            # Simulate fallback or use a real API if needed
            fallback_url = f"https://some-other-dictionary-api.com/{lang}/{word}"
            response = requests.get(fallback_url, timeout=5)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            # Hide the fallback error, just return None to silently fail
            pass
        return None
