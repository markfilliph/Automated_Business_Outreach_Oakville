"""
NER-based person name extractor using HuggingFace dslim/bert-base-NER.

Lazy-loads the model on first call (cached for the process lifetime).
CPU-only, synchronous. Looks for PER entities near owner-signal words.
"""

_pipeline = None

OWNER_SIGNALS = [
    "owner", "founder", "co-founder", "president", "ceo",
    "principal", "director", "partner", "proprietor", "managing",
]

# Max char distance between a signal word and a PER entity to count as a hit
SIGNAL_WINDOW = 150


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from transformers import pipeline
        _pipeline = pipeline(
            "ner",
            model="dslim/bert-base-NER",
            aggregation_strategy="simple",
            device=-1,  # CPU
        )
    return _pipeline


def extract_owner_name(text):
    """Extract the most likely owner/founder name from free text.

    Strategy: run NER, find PER entities, score them by proximity to
    owner-signal words. Returns (name, confidence) or ("", "none").

    Confidence levels:
      "medium" — PER entity within SIGNAL_WINDOW chars of a signal word
      "low"    — PER entity found but no nearby signal word
      "none"   — no usable name found
    """
    if not text or len(text.strip()) < 20:
        return "", "none"

    # Truncate — bert-base has a 512-token limit; 3000 chars is safe
    text = text[:3000]
    text_lower = text.lower()

    # Collect signal word positions
    signal_positions = []
    for signal in OWNER_SIGNALS:
        pos = 0
        while True:
            idx = text_lower.find(signal, pos)
            if idx == -1:
                break
            signal_positions.append(idx)
            pos = idx + 1

    try:
        ner = _get_pipeline()
        entities = ner(text)
    except Exception as e:
        return "", "none"

    best_name = ""
    best_dist = float("inf")

    for ent in entities:
        if ent.get("entity_group") != "PER":
            continue
        name = ent.get("word", "").strip()
        # Skip single-token names (likely false positives)
        if len(name.split()) < 2:
            continue
        # Skip names that look like they contain subword artifacts
        if "##" in name or name.startswith("-"):
            continue

        ent_start = ent.get("start", 0)
        if signal_positions:
            dist = min(abs(ent_start - sp) for sp in signal_positions)
        else:
            dist = float("inf")

        if dist < best_dist:
            best_dist = dist
            best_name = name

    if not best_name:
        return "", "none"

    if best_dist <= SIGNAL_WINDOW:
        return best_name, "medium"
    else:
        return best_name, "low"
