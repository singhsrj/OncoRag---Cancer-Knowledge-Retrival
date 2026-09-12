"""
Generation-quality metrics that need no ground-truth labels -- only the
retrieved context and the generated answer. Both reuse the exact same
OpenRouter calls already defined in helper.py (generate_answer, embed_text,
cosine_similarity), so no new dependency or provider is introduced.

Faithfulness (0-1):
    1. Ask the LLM to break the answer into atomic factual claims.
    2. Ask the LLM, per claim, whether it's directly supported by the
       retrieved context.
    3. faithfulness = supported_claims / total_claims
    A low score means the model is adding things the context doesn't say
    (hallucination) -- the thing top_k tuning most often trades against.

Answer relevance (0-1, roughly a cosine similarity):
    1. Ask the LLM to generate N questions that the answer would be a good
       response to.
    2. Embed those questions and the original query.
    3. relevance = average cosine similarity(query, generated_question)
    A low score usually means the answer wandered off-topic or is too
    generic to reconstruct the original question.
"""

import json
import re

from helper import generate_answer, embed_text, cosine_similarity


def _parse_json_list(raw: str) -> list[str]:
    """LLMs wrap JSON in prose/code fences sometimes -- pull out the array."""
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
        return [str(x).strip() for x in data if str(x).strip()]
    except json.JSONDecodeError:
        return []


def extract_claims(answer: str) -> list[str]:
    prompt = f"""Break the following answer into a list of short, atomic, independently-
checkable factual statements. Skip hedges like "the context does not say" or
"I don't know" -- only list actual claims. If there are no factual claims at
all, return an empty array.

Return ONLY a JSON array of strings, nothing else.

Answer:
\"\"\"{answer}\"\"\""""
    return _parse_json_list(generate_answer(prompt))


def claim_supported(claim: str, context: str) -> bool:
    prompt = f"""Context:
\"\"\"{context}\"\"\"

Claim: "{claim}"

Is this claim directly supported by the context above? Reply with exactly
one word: YES or NO."""
    raw = generate_answer(prompt).strip().upper()
    return raw.startswith("Y")


def faithfulness_score(answer: str, context_chunks: list[str]) -> float | None:
    """None means the answer had no checkable claims (e.g. a refusal like
    "the context doesn't mention this") -- don't average that in as a 0."""
    claims = extract_claims(answer)
    if not claims:
        return None
    context = "\n\n".join(context_chunks)
    supported = sum(claim_supported(c, context) for c in claims)
    return supported / len(claims)


def generate_questions_from_answer(answer: str, n: int = 3) -> list[str]:
    prompt = f"""Given the following answer, write {n} different questions that this
answer would be a good, complete response to. Vary the phrasing.

Return ONLY a JSON array of {n} strings, nothing else.

Answer:
\"\"\"{answer}\"\"\""""
    return _parse_json_list(generate_answer(prompt))


def answer_relevance_score(query: str, answer: str, n: int = 3) -> float | None:
    questions = generate_questions_from_answer(answer, n=n)
    if not questions:
        return None
    query_emb = embed_text(query)
    sims = [cosine_similarity(query_emb, embed_text(q)) for q in questions]
    return sum(sims) / len(sims)
