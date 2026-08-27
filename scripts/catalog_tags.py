"""Canonical two-tag schema for Paper Collection records."""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Iterable


SOURCE_TAGS = (
    "arXiv",
    "OpenReview",
    "Journal",
    "Conference",
    "Research page",
    "Scholar search",
    "Local PDF",
)

NON_TOPIC_TAGS = {
    "Browser bookmark",
    "Contextual Reference",
    "Flow Matching RG",
    "Meaningful Chat",
    "Recommended",
}

TOPIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Nonreciprocal Systems", ("nonreciprocal", "non-reciprocal", "odd viscosity")),
    ("Active Matter", ("active matter", "active particle", "active brownian", "flock", "vicsek", "quincke", "motility-induced", "self-propelled")),
    ("Flow Matching", ("flow matching", "rectified flow")),
    ("Diffusion Models", ("diffusion model", "score-based", "score matching")),
    ("Renormalization Group", ("renormalization", "renormalisation", r"\brg flow\b")),
    ("Neural Operators", ("neural operator", "deeponet", "fourier neural operator")),
    ("Transformer Theory", ("transformer", "self-attention", "attention")),
    ("World Models", ("world model", "world-action")),
    ("Robotics", ("robot", "embodied", "manipulation", "vision-language-action", r"\bvla\b")),
    ("Fluid Dynamics", ("fluid", "hydrodynamic", "turbulence", "stokesian", "faraday wave")),
    ("Soft Matter", ("soft matter", "colloid", "polymer", "granular", "amorphous solid")),
    ("Biophysics", ("biological", "cell", "tissue", "protein", "bacteria")),
    ("Scaling Laws", ("scaling law", "neural scaling", "power law")),
    ("Information Theory", ("information theory", "information-theoretic", "mutual information", "fisher information")),
    ("Field Theory", ("field theory", "path integral", "effective action")),
    ("Training Dynamics", ("training dynamics", "learning dynamics", "gradient descent")),
    ("AI for Science", ("scientific discovery", "physical law", "symbolic regression", "ai for science")),
    ("Video Generation", ("video generation", "video diffusion")),
    ("Generative Models", ("generative model", "generative modeling")),
    ("Statistical Physics", ("statistical physics", "statistical mechanics", "phase transition", "critical phenomena", "universality")),
    ("Machine Learning", ("machine learning", "deep learning", "neural network", "artificial intelligence", r"\bai\b")),
)

TOPIC_PRIORITY = (
    "Nonreciprocal Systems",
    "Active Matter",
    "Flow Matching",
    "Diffusion Models",
    "Renormalization Group",
    "Neural Operators",
    "Transformer Theory",
    "World Models",
    "Robotics",
    "Fluid Dynamics",
    "Soft Matter",
    "Biophysics",
    "Scaling Laws",
    "Information Theory",
    "Field Theory",
    "Training Dynamics",
    "AI for Science",
    "Video Generation",
    "Few-step Generation",
    "Path Integrals",
    "Scientific ML",
    "Symmetry",
    "Benchmarking",
    "Generative Models",
    "Statistical Physics",
    "Machine Learning",
)


def source_for(url: str | None, existing_tags: Iterable[str] = ()) -> str:
    """Return one source label, preferring an identifiable public host."""
    host = urllib.parse.urlsplit(url or "").netloc.casefold().removeprefix("www.")
    if host.endswith("arxiv.org"):
        return "arXiv"
    if host.endswith("openreview.net"):
        return "OpenReview"
    for tag in existing_tags:
        if tag in SOURCE_TAGS:
            return tag
    if host == "scholar.google.com":
        return "Scholar search"
    if host:
        return "Journal"
    return "Local PDF"


def _matches(title: str, terms: tuple[str, ...]) -> bool:
    lowered = title.casefold()
    return any(re.search(term, lowered) if "\\b" in term else term in lowered for term in terms)


def topic_for(title: str, existing_tags: Iterable[str] = ()) -> str:
    """Return one topic label from title evidence and any existing topic labels."""
    candidates = {
        tag
        for tag in existing_tags
        if tag not in SOURCE_TAGS
        and tag not in NON_TOPIC_TAGS
        and not re.fullmatch(r"(?:19|20)\d{2}(?:-\d{2})?", tag)
    }
    for topic, terms in TOPIC_RULES:
        if _matches(title, terms) and (not candidates or topic in candidates):
            return topic
    for topic in TOPIC_PRIORITY:
        if topic in candidates:
            return topic
    return sorted(candidates)[0] if candidates else "Other"


def paper_tags(source: str, title: str, topic_candidates: Iterable[str] = ()) -> list[str]:
    """Build the canonical ``[source, topic]`` tag pair."""
    return [source, topic_for(title, topic_candidates)]


def validate_tag_pair(tags: object) -> bool:
    return (
        isinstance(tags, list)
        and len(tags) == 2
        and tags[0] in SOURCE_TAGS
        and isinstance(tags[1], str)
        and bool(tags[1])
        and tags[1] not in SOURCE_TAGS
        and tags[1] not in NON_TOPIC_TAGS
    )
