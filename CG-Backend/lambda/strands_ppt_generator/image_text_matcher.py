"""Simple TF-IDF based Image↔Text matcher.

Provides a lightweight, dependency-free prototype for matching a requested
image description to a set of candidate images (each with an `alt_text`).

API:
 - choose_best_image(request_text: str, images: List[Dict], top_n: int = 1)
     -> returns list of (index, score) sorted by score desc

Implementation notes:
 - Tokenization is simple and deterministic (lowercase, alnum tokens).
 - IDF uses log(N / (1 + df)) to avoid division by zero.
 - TF is term frequency normalized by document length.
 - Cosine similarity is used on TF-IDF vectors.
"""
from typing import List, Dict, Tuple
import math
import re

# Small stopword set - keep light and local
STOPWORDS = {
    'the', 'and', 'or', 'in', 'on', 'at', 'a', 'an', 'to', 'for', 'of', 'with',
    'by', 'is', 'are', 'was', 'were', 'be', 'been', 'this', 'that', 'these', 'those',
    'it', 'its', 'as', 'from', 'which', 'we', 'you', 'your', 'their', 'they',
}


def tokenize(text: str) -> List[str]:
    if not text:
        return []
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    toks = [t for t in text.split() if t and t not in STOPWORDS and len(t) > 1]
    return toks


def build_term_freq(tokens: List[str]) -> Dict[str, float]:
    freqs: Dict[str, int] = {}
    for t in tokens:
        freqs[t] = freqs.get(t, 0) + 1
    total = sum(freqs.values()) or 1
    return {k: v / total for k, v in freqs.items()}


def compute_idf(docs_tokens: List[List[str]]) -> Dict[str, float]:
    N = len(docs_tokens)
    df: Dict[str, int] = {}
    for tokens in docs_tokens:
        seen = set(tokens)
        for t in seen:
            df[t] = df.get(t, 0) + 1
    idf: Dict[str, float] = {}
    for term, cnt in df.items():
        # smooth idf
        idf[term] = math.log((N) / (1 + cnt)) + 1.0
    return idf


def tfidf_vector(tf: Dict[str, float], idf: Dict[str, float]) -> Dict[str, float]:
    vec: Dict[str, float] = {}
    for t, tv in tf.items():
        vec[t] = tv * idf.get(t, 1.0)
    return vec


def cosine_sim(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    for k, v in a.items():
        dot += v * b.get(k, 0.0)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def choose_best_image(request_text: str, images: List[Dict], top_n: int = 1) -> List[Tuple[int, float]]:
    """Return top_n (index, score) pairs for best matching images.

    images: list of dicts with 'alt_text' (string) key. Missing alt_texts are treated as empty.
    """
    # Build tokens for query and each image alt_text
    docs_tokens: List[List[str]] = []
    query_tokens = tokenize(request_text or '')
    docs_tokens.append(query_tokens)
    for img in images:
        docs_tokens.append(tokenize(img.get('alt_text', '')))

    # compute idf over all docs
    idf = compute_idf(docs_tokens)

    # build tf-idf for query
    q_tf = build_term_freq(query_tokens)
    q_vec = tfidf_vector(q_tf, idf)

    scores: List[Tuple[int, float]] = []
    for idx, img in enumerate(images):
        toks = docs_tokens[idx + 1]
        if not toks:
            scores.append((idx, 0.0))
            continue
        tf = build_term_freq(toks)
        vec = tfidf_vector(tf, idf)
        sc = cosine_sim(q_vec, vec)
        scores.append((idx, float(sc)))

    # sort by score desc
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_n]


if __name__ == '__main__':
    # quick self-test
    imgs = [
        {'alt_text': 'database migration and schema'},
        {'alt_text': 'user interface mockup'},
        {'alt_text': 'load testing and performance tuning'},
    ]
    print(choose_best_image('run migrations and load testing', imgs, top_n=3))
