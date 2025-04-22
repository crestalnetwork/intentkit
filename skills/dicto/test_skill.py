from word_lookup import LookupWord

def test_skill():
    # Initialize the skill (you can pass the config if needed)
    skill = LookupWord()

    # Test inputs (you can modify this list to test more words)
    test_inputs = [
        "bonjour",  # French word
        "Jack",
        "actor",
        "FAN",
        "JUPITER",
        "run",      # English word
        "comer es bueno",  # Spanish phrase (note: only the first word 'comer' will be considered)
        "geschirrspüler",  # German word
        "ありがとう",  # Japanese word
        "serendipity",  # English word
    ]

    # Test each input
    for input_text in test_inputs:
        print(f"Testing word: {input_text}")
        response = skill.run(input_text)
        print(f"Response: {response}\n")

if __name__ == "__main__":
    test_skill()
