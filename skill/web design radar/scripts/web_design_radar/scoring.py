from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from .urls import canonicalize_url


_WEIGHTS = {
    "technology": 0.35,
    "industry": 0.25,
    "popularity": 0.20,
    "novelty": 0.10,
    "analyzability": 0.10,
}


@dataclass(frozen=True)
class Candidate:
    site_url: str
    source_url: str
    title: str
    technology: float
    industry: float
    popularity: float
    novelty: float
    analyzability: float
    tags: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "site_url", canonicalize_url(self.site_url))
        object.__setattr__(self, "tags", tuple(str(tag).strip().lower() for tag in self.tags if str(tag).strip()))
        for field in _WEIGHTS:
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f"{field} must be a number in [0, 1]")

    @property
    def canonical_domain(self) -> str:
        host = urlsplit(self.site_url).hostname
        if host is None:
            raise ValueError("candidate site URL has no host")
        return host

    @property
    def primary_tag(self) -> str | None:
        return self.tags[0] if self.tags else None


def score_candidate(candidate: Candidate) -> float:
    return sum(getattr(candidate, field) * weight for field, weight in _WEIGHTS.items())


def select_candidates(
    candidates: list[Candidate], previous_domains: set[str], quota: int = 2
) -> list[Candidate]:
    if quota < 1:
        return []
    excluded = {domain.lower().removeprefix("www.") for domain in previous_domains}
    unique: dict[str, Candidate] = {}
    for candidate in candidates:
        if candidate.canonical_domain in excluded:
            continue
        current = unique.get(candidate.canonical_domain)
        if current is None or score_candidate(candidate) > score_candidate(current):
            unique[candidate.canonical_domain] = candidate

    ranked = sorted(
        unique.values(),
        key=lambda item: (-score_candidate(item), item.site_url),
    )
    if not ranked:
        return []
    selected = [ranked.pop(0)]
    while ranked and len(selected) < quota:
        baseline = ranked[0]
        diverse = next(
            (
                item
                for item in ranked
                if item.primary_tag != selected[0].primary_tag
                and score_candidate(baseline) - score_candidate(item) <= 0.10
            ),
            None,
        )
        choice = diverse or baseline
        selected.append(choice)
        ranked.remove(choice)
    return selected
