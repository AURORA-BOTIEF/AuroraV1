"""Text Analyzer utilities for PPT generator.

Provides simple, deterministic heuristics to estimate text complexity,
shorten bullets, and split slide content into multiple slides when too long.
"""
from typing import Dict, List
import math
import re

# Small stopword set to improve key-term extraction (keeps dependencies minimal)
STOPWORDS = {
    'the', 'and', 'or', 'in', 'on', 'at', 'a', 'an', 'to', 'for', 'of', 'with',
    'by', 'is', 'are', 'was', 'were', 'be', 'been', 'this', 'that', 'these', 'those',
    'it', 'its', 'as', 'from', 'which', 'we', 'you', 'your', 'their', 'they'
}


def estimate_text_complexity(slide_data: Dict) -> Dict:
    """Return metrics about the slide's text content.

    Returns a dict with keys: word_count, sentence_count, avg_sentence_length
    """
    title = slide_data.get('title', '') or ''
    caption = slide_data.get('caption', '') or ''
    bullets = slide_data.get('bullets') or []

    all_text = ' '.join([title, caption] + [str(b) for b in bullets])
    words = [w for w in all_text.split() if w.strip()]
    word_count = len(words)

    # Very lightweight sentence split by punctuation
    sentences = [s.strip() for s in re.split(r'[\.!?]+', all_text) if s.strip()]
    sentence_count = max(1, len(sentences))
    avg_sentence_length = word_count / sentence_count if sentence_count else word_count

    return {
        'word_count': word_count,
        'sentence_count': sentence_count,
        'avg_sentence_length': avg_sentence_length
    }


def shorten_bullets(bullets: List[str], max_bullets: int = 5) -> List[str]:
    """Return a shortened list of bullets, keeping lead information.

    Strategy: keep the first `max_bullets-1` bullets and merge the remainder into a final summary bullet.
    """
    if not bullets:
        return []
    if len(bullets) <= max_bullets:
        return bullets

    head = bullets[: max_bullets - 1]
    rest = bullets[max_bullets - 1 :]

    # Create a concise summary using key terms from the remaining bullets.
    combined = ' '.join([str(s).strip() for s in rest])

    def extract_key_terms(text: str, top_n: int = 4) -> List[str]:
        text = re.sub(r"[^a-zA-Z0-9\s]", ' ', text or '')
        toks = [t.lower() for t in text.split() if t.strip()]
        freqs = {}
        for t in toks:
            if t in STOPWORDS or len(t) <= 2:
                continue
            freqs[t] = freqs.get(t, 0) + 1
        # sort by frequency then by length (prefer longer tokens for clarity)
        items = sorted(freqs.items(), key=lambda x: (-x[1], -len(x[0]), x[0]))
        return [it[0] for it in items[:top_n]]

    key_terms = extract_key_terms(combined, top_n=4)
    if key_terms:
        summary = 'Also covers: ' + ', '.join(key_terms) + '.'
    else:
        # fallback to joining trimmed rest if no good key terms
        summary = combined
        if len(summary) > 180:
            summary = summary[:177].rsplit(' ', 1)[0] + '...'

    head.append(summary)
    return head


def split_slide_content(slide_data: Dict, max_words_per_slide: int = 90) -> List[Dict]:
    """Split a slide_data into multiple slides if it contains more than max_words_per_slide words.

    Rules:
    - If bullets exist, split bullets into groups that keep <= max_words_per_slide words.
    - If no bullets (long paragraph), split paragraph by sentence boundaries.
    """
    metrics = estimate_text_complexity(slide_data)
    if metrics['word_count'] <= max_words_per_slide:
        return [slide_data]

    # If bullets present, chunk bullets
    bullets = slide_data.get('bullets') or []
    if bullets:
        chunks: List[List[str]] = []
        current: List[str] = []
        current_words = 0
        for b in bullets:
            b_words = len(str(b).split())
            if current_words + b_words > max_words_per_slide and current:
                chunks.append(current)
                current = [b]
                current_words = b_words
            else:
                current.append(b)
                current_words += b_words
        if current:
            chunks.append(current)

        slides = []
        total = len(chunks)
        base_title = slide_data.get('title') or ''
        for idx, chunk in enumerate(chunks):
            new_slide = dict(slide_data)
            # Only keep image on the first split to avoid repeating large visuals
            if 'image_url' in new_slide and idx > 0:
                new_slide.pop('image_url', None)
            # If a chunk contains a single very long bullet, split that bullet into sentences
            if len(chunk) == 1 and len(str(chunk[0]).split()) > max_words_per_slide:
                # split by sentence-like boundaries
                sents = [s.strip() for s in re.split(r'(?<=[\.\!?])\s+', str(chunk[0])) if s.strip()]
                # Turn each sentence into its own bullet group if needed
                # For simplicity, keep the first part as the chunk here (others will be new slides)
                new_slide['bullets'] = [sents[0]] if sents else [chunk[0]]
                # if there are remaining sentences, insert them as additional chunks after current index
                if len(sents) > 1:
                    for extra in sents[1:]:
                        chunks.insert(idx + 1, [extra])
            else:
                new_slide['bullets'] = chunk
            # for split slides, add a clearer postfix to title: ' — Part X/N'
            if total > 1:
                new_slide['title'] = f"{base_title} — Part {idx+1}/{total}"
            slides.append(new_slide)
        return slides

    # No bullets: attempt to split by sentence boundaries
    text = ' '.join([str(slide_data.get('title') or ''), str(slide_data.get('caption') or '')]).strip()
    # if there's little text in title/caption, try to split a 'content' field if present
    if not text and 'content' in slide_data:
        text = slide_data.get('content', '')

    sentences = [s.strip() for s in re.split(r'(?<=[\.!?])\s+', text) if s.strip()]
    slides = []
    current = ''
    current_words = 0
    for s in sentences:
        s_words = len(s.split())
        if current_words + s_words > max_words_per_slide and current:
            new_slide = dict(slide_data)
            new_slide['caption'] = current.strip()
            new_slide['bullets'] = []
            slides.append(new_slide)
            current = s
            current_words = s_words
        else:
            current = (current + ' ' + s).strip()
            current_words += s_words

    if current:
        new_slide = dict(slide_data)
        new_slide['caption'] = current.strip()
        new_slide['bullets'] = []
        slides.append(new_slide)

    # Post-process: if multiple slides were produced, add clearer titles and only keep image on first
    if len(slides) > 1:
        total = len(slides)
        base_title = slide_data.get('title') or ''
        for i, s in enumerate(slides):
            s['title'] = f"{base_title} — Part {i+1}/{total}"
            if i > 0 and 'image_url' in s:
                s.pop('image_url', None)

    return slides
