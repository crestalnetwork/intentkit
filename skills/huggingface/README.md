# HuggingFace Skill Category

This skill category enables natural language understanding tools via HuggingFace Transformers.

## Included Skills

### 🧠 Sentiment Analysis

**Description:**  
Analyzes the sentiment of input text (e.g., "I love this!") and returns a label (`POSITIVE`, `NEGATIVE`, etc.) along with a confidence score.

## Configuration Example

```yaml
skills:
  huggingface:
    states:
      sentiment_analysis: public

