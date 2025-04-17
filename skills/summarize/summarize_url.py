import requests
from bs4 import BeautifulSoup

def run(url: str, *args, **kwargs):
    """Fetch and return the first few sentences from the webpage at the given URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text() for p in paragraphs if len(p.get_text()) > 40)

        if not text:
            return "Couldn't find readable content on the page."

        sentences = text.split(". ")
        return ". ".join(sentences[:3]) + "."
    except Exception as e:
        return f"Error: {e}"
