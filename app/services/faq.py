"""FAQ matching using bigram Dice similarity (matching n8n workflow logic)."""

from __future__ import annotations


def _bigrams(text: str) -> set[str]:
    """Generate character bigrams from lowercased text."""
    t = text.lower().strip()
    if len(t) < 2:
        return {t}
    return {t[i : i + 2] for i in range(len(t) - 1)}


def dice_similarity(a: str, b: str) -> float:
    """Dice coefficient on bigrams, 0.0-1.0."""
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return 2 * len(ba & bb) / (len(ba) + len(bb))


def match_faq(query: str, faqs: list[dict], threshold: float = 0.45) -> dict | None:
    """Find best FAQ match above threshold. Returns FAQ dict or None."""
    best_score = 0.0
    best_faq = None
    for faq in faqs:
        score = dice_similarity(query, faq["question"])
        if score > best_score:
            best_score = score
            best_faq = faq
    if best_score >= threshold and best_faq:
        return best_faq
    return None
