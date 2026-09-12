import requests
import json
from dotenv import load_dotenv
import numpy as np
import os
load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')


def chunk_text(text, chunk_size=500, overlap=50):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def cosine_similarity(a, b):
    '''It returns a number between -1 and 1.
    Closer to 1 means "these two vectors point in a very similar direction" — i.e., similar meaning.
    Closer to 0 means unrelated.'''
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def euclidean_distance(a, b):
    '''Return actual distance between 2 points'''
    return np.linalg.norm(a - b)


def retrieve(query_embedding, chunks, embeddings, top_k=3):
    scores = []
    for emb in embeddings:
        score = cosine_similarity(query_embedding, emb)
        scores.append(score)
    # return sorted indices of scores, reverse them, extract top 3
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [chunks[i] for i in top_indices]


def retrieve_with_ids(query_embedding, chunks, embeddings, top_k=3):
    scores = [cosine_similarity(query_embedding, emb) for emb in embeddings]
    top_indices = np.argsort(scores)[::-1][:top_k]
    return list(top_indices)  # just the ids, as a plain list


def embed_text(text):
    response = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        json={"model": "openai/text-embedding-3-small", "input": [text]}
    )
    return response.json()["data"][0]["embedding"]


def generate_answer(prompt, model="upstage/solar-pro4"):
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        data=json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}]
        })
    )
    result = response.json()
    if "choices" not in result:
        raise Exception(f"Generation API error: {result}")
    return result["choices"][0]["message"]["content"]


def build_prompt(query, retrieved_chunks):
    context = "\n\n".join(retrieved_chunks)
    return f"""Answer the question using only the context below. If the answer isn't in the context, say so.

Context:
{context}

Question: {query}
Answer:"""
