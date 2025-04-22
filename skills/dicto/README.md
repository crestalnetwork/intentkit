# 📚 Dicto - Dictionary Lookup Skill

Dicto is a skill for looking up English word definitions using the free [DictionaryAPI](https://dictionaryapi.dev). It returns detailed definitions, parts of speech, example usages, and a fallback Google link for further lookup.

## 🔍 Features

- Look up definitions of English words
- Part of speech identification (e.g., noun, verb)
- Example usages when available
- Fallback to Google definition search if no definitions are found

---

## 🚀 How It Works

When a user inputs a word (e.g., `run`), Dicto performs a search for said word and provides the user with relevant information relating to searched word

User: run
Dicto: 🔍 Looking up "run"
📖 Definition: To move swiftly on foot.
Verb: To run. Noun: An act or instance of running. (Example: I went for a quick run this morning.) Noun: A trip or errand. (Example: I'm making a run to the store.
View More on Dictionary: https://www.google.com/search?q=define+run

If the word is not found or an error occurs, Dicto informs the user and provides a Google search link as an alternative.

User: htftya
Dicto: Sorry, we couldn't find a definition for "htftya" in `en`.
View More on Dictionary: https://www.google.com/search?q=htftya


---

## 📁 File Structure

dicto/
├── base.py
├── word_lookup.py
├── __init__.py
├── schema.json
├── test_skill.py
├── dicto.png
└── README.md


