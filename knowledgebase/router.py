"""
Before we retrieve anything, ask the LLM which topic file the query belongs
to. This keeps retrieval scoped to one document instead of searching every
cancer topic's embeddings for every question.
"""

from helper import generate_answer


def classify_topic(query: str, topics: list[str]) -> str:
    """
    topics: e.g. ["lung_cancer", "breast_cancer", "skin_cancer"]
    Returns exactly one of the given topic strings.
    """
    topic_list = "\n".join(f"- {t}" for t in topics)

    prompt = f"""You are a router that decides which knowledge base to search to answer a question.

Available topics:
{topic_list}

Question: {query}

Respond with ONLY the exact topic name from the list above that is most relevant.
Do not explain your choice. Do not add punctuation. Just the topic name, exactly as written above."""

    raw_response = generate_answer(prompt).strip()

    # The LLM should return an exact match, but don't trust that blindly --
    # do a case-insensitive fallback match in case it adds stray formatting.
    for topic in topics:
        if raw_response.lower() == topic.lower():
            return topic

    for topic in topics:
        if topic.lower() in raw_response.lower():
            return topic

    raise ValueError(
        f"Router returned '{raw_response}', which doesn't match any known topic: {topics}"
    )
