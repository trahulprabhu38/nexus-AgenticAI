"""
Hierarchical Fusion Intent Agent
=================================
Implements the Hierarchical Fusion with Entropy Reduction (ΔHk) concept
from the VLA systematic review paper (Ud Din et al., Information Fusion 2026).

The paper shows that hierarchical fusion achieves the greatest entropy reduction
by progressively constraining the action distribution across multiple layers
of abstraction. This agent applies the same principle to intent classification:

  Layer 1 (Contextual Constraint):  Persona-based domain pruning
  Layer 2 (Cross-Modal Alignment):  Query-keyword semantic scoring
  Layer 3 (Uncertainty Assessment):  Entropy thresholding (ΔHk)

Paper reference (Section 4.5, Eq. 5):
  ΔHk = H(A | Z_{k-1}) - H(A | Z_k)
  Cumulative entropy reduction indicates more confident decisions.
"""

import math
import re
from base import BaseAgent, Message

# ---------------------------------------------------------------------------
# Domain definitions
# ---------------------------------------------------------------------------
DOMAINS = ["placements", "results", "projects", "faculty", "syllabus", "accreditation", "data_pruning"]

# ---------------------------------------------------------------------------
# Layer 1: Persona priors (contextual constraint)
# ---------------------------------------------------------------------------
PERSONA_PRIORS = {
    "student": {
        "results":       0.25,
        "syllabus":      0.25,
        "projects":      0.15,
        "placements":    0.15,
        "faculty":       0.10,
        "accreditation": 0.05,
        "data_pruning":  0.05,
    },
    "faculty": {
        "syllabus":      0.20,
        "results":       0.20,
        "projects":      0.20,
        "faculty":       0.15,
        "accreditation": 0.10,
        "placements":    0.10,
        "data_pruning":  0.05,
    },
    "parent": {
        "results":       0.30,
        "placements":    0.25,
        "accreditation": 0.20,
        "faculty":       0.10,
        "syllabus":      0.10,
        "projects":      0.05,
        "data_pruning":  0.00,
    },
    "recruiter": {
        "placements":    0.35,
        "projects":      0.20,
        "accreditation": 0.20,
        "results":       0.10,
        "faculty":       0.10,
        "syllabus":      0.05,
        "data_pruning":  0.00,
    },
    "default": {
        "results":       0.15,
        "syllabus":      0.15,
        "projects":      0.15,
        "placements":    0.15,
        "faculty":       0.15,
        "accreditation": 0.15,
        "data_pruning":  0.10,
    },
}

# ---------------------------------------------------------------------------
# Layer 2: Domain keyword stems and phrases (cross-modal alignment)
# ---------------------------------------------------------------------------
DOMAIN_KEYWORDS = {
    "placements": {
        "stems": [
            "placement", "company", "compan", "package", "recruit", "hire",
            "hiring", "job", "offer", "salary", "intern", "campus", "drive",
            "career", "lpa", "ctc", "onsite", "eligible", "eligib",
            "shortlist", "select", "interview", "employ", "fresher",
            "openings", "resume", "cv",
        ],
        "phrases": ["campus drive", "job offer", "on campus", "off campus"],
    },
    "results": {
        "stems": [
            "result", "grade", "marks", "cgpa", "sgpa", "score", "semester", "sem", "usn",
            "exam", "pass", "fail", "rank", "topper", "gpa", "percent",
            "backlog", "revaluat", "marksheet", "transcript", "scorecard",
            "detained", "supple",
        ],
        "phrases": ["mark sheet", "grade card", "pass percentage"],
    },
    "data_pruning": {
        "stems": ["prune", "column", "dataset", "filter", "feature", "select"],
        "phrases": ["column pruning", "prune columns", "filter data"],
    },
    "projects": {
        "stems": [
            "project", "lab", "research", "thesis", "assign", "workshop",
            "hackathon", "paper", "code", "capstone", "prototype", "demo",
            "github", "repositor", "implement", "develop",
        ],
        "phrases": ["mini project", "final year project", "research paper"],
    },
    "faculty": {
        "stems": [
            "faculty", "teacher", "professor", "prof", "hod", "dean",
            "staff", "mentor", "guide", "cabin", "coordinator", "lecturer",
            "sir", "maam", "ma'am", "doctor", "dr",
        ],
        "phrases": ["office hour", "department head", "class teacher"],
    },
    "syllabus": {
        "stems": [
            "syllabus", "subject", "course", "curriculum", "timetable",
            "schedule", "class", "credit", "elective", "textbook",
            "module", "unit", "portion", "chapter", "topic", "book",
        ],
        "phrases": ["lab manual", "lesson plan", "course outline", "study material"],
    },
    "accreditation": {
        "stems": [
            "accredit", "naac", "nba", "ranking", "tier", "approval",
            "aicte", "ugc", "recogni", "rating", "nirf", "autonomo",
            "affiliat", "certif",
        ],
        "phrases": [],
    },
}

# Confidence thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.75
LOW_CONFIDENCE_THRESHOLD  = 0.40
MULTI_CANDIDATE_THRESHOLD = 0.30


def _shannon_entropy(distribution: dict) -> float:
    """Compute Shannon entropy H = -Sigma p*log2(p) for a probability distribution."""
    return -sum(p * math.log2(p) for p in distribution.values() if p > 0)


def _normalize(scores: dict) -> dict:
    """Normalize a dict of scores to sum to 1."""
    total = sum(scores.values())
    if total == 0:
        n = len(scores)
        return {k: 1.0 / n for k in scores}
    return {k: v / total for k, v in scores.items()}


def _tokenize(text: str) -> list:
    """Split text into lowercase word tokens."""
    return re.findall(r"[a-z']+", text.lower())


def _compute_keyword_scores(query: str) -> dict:
    """
    Score each domain using stem matching + phrase matching.

    Stem matching: each query word is checked against keyword stems.
    A stem matches if the query word starts with the stem or the stem
    starts with the query word (handles both directions).

    Phrase matching: multi-word phrases are checked as substrings
    of the full query (worth 2 points each — stronger signal).
    """
    query_lower = query.lower()
    words = _tokenize(query_lower)
    scores = {}

    for domain, kw_data in DOMAIN_KEYWORDS.items():
        score = 0.0

        # Stem matching: check each query word against each stem
        # word.startswith(stem) → "recruitment" matches stem "recruit"
        # stem.startswith(word) → only allowed for longer words (>=5 chars)
        #                         to avoid "the" matching "thesis" etc.
        for word in words:
            if len(word) < 3:
                continue
            for stem in kw_data["stems"]:
                if word.startswith(stem):
                    score += 1.0
                    break
                if len(word) >= 5 and stem.startswith(word):
                    score += 1.0
                    break

        # Phrase matching: substring check (worth 2x)
        for phrase in kw_data["phrases"]:
            if phrase in query_lower:
                score += 2.0

        scores[domain] = score

    return scores


class HierarchicalIntentAgent(BaseAgent):
    """
    Three-layer hierarchical fusion intent classifier.

    The classification pipeline mirrors the paper's hierarchical fusion paradigm:
    each layer progressively reduces the entropy of the domain distribution,
    producing more confident and reliable intent tags.
    """

    def __init__(self):
        super().__init__("intent_agent")

    async def handle_message(self, message: Message) -> Message:
        query = message.text
        persona = message.metadata.get("persona", "default")

        result = self.classify(query, persona)

        return Message(
            sender="intent_agent",
            text=result["intent"],
            metadata=result,
        )

    def classify(self, query: str, persona: str = "default") -> dict:
        """
        Run the 3-layer hierarchical fusion pipeline.

        Returns a dict with:
          intent            - domain tag(s) or CLARIFICATION_REQUIRED
          confidence        - top domain confidence [0-1]
          entropy_reduction - normalized delta-Hk [0-1] (higher = more certain)
          reasoning         - human-readable explanation
          action            - instruction for the downstream Table Agent
          scores            - full domain probability distribution
        """

        # === LAYER 1: Contextual Constraint (Persona Prior) ===
        prior = PERSONA_PRIORS.get(persona, PERSONA_PRIORS["default"]).copy()
        h_prior = _shannon_entropy(prior)  # H(A | Z0)

        # === LAYER 2: Cross-Modal Alignment (Keyword Evidence) ===
        keyword_scores = _compute_keyword_scores(query)
        total_score = sum(keyword_scores.values())

        # Bayesian-style fusion: multiply prior by evidence likelihood
        # then renormalize. This produces sharper posteriors than linear blending.
        posterior = {}
        if total_score > 0:
            evidence = _normalize(keyword_scores)
            for domain in DOMAINS:
                # Bayesian update: P(domain | query) ~ P(query | domain) * P(domain)
                # Add smoothing so zero-evidence domains aren't completely killed
                smoothed_evidence = evidence.get(domain, 0) + 0.01
                posterior[domain] = prior[domain] * smoothed_evidence
        else:
            posterior = prior.copy()

        posterior = _normalize(posterior)
        h_posterior = _shannon_entropy(posterior)  # H(A | Z_K)

        # === LAYER 3: Uncertainty Assessment (delta-Hk) ===
        max_entropy = math.log2(len(DOMAINS))
        delta_h = h_prior - h_posterior
        entropy_reduction = 1.0 - (h_posterior / max_entropy) if max_entropy > 0 else 0.0

        # Rank domains by posterior probability
        ranked = sorted(posterior.items(), key=lambda x: x[1], reverse=True)
        top_tag, top_conf = ranked[0]
        second_tag, second_conf = ranked[1]

        # Decision logic
        if top_conf >= HIGH_CONFIDENCE_THRESHOLD:
            intent = top_tag
            action = f"Search the '{top_tag}' domain tables for: {query}"
        elif top_conf >= LOW_CONFIDENCE_THRESHOLD:
            if second_conf >= MULTI_CANDIDATE_THRESHOLD:
                intent = f"{top_tag},{second_tag}"
                action = f"Search both '{top_tag}' and '{second_tag}' domains for: {query}"
            else:
                intent = top_tag
                action = f"Search the '{top_tag}' domain tables for: {query}"
        else:
            intent = "CLARIFICATION_REQUIRED"
            action = "Ask the user to clarify their query with more specific terms."

        # Build reasoning
        if total_score > 0:
            matched_domains = [d for d, s in keyword_scores.items() if s > 0]
            reasoning = (
                f"Persona '{persona}' set initial priors (H0={h_prior:.2f} bits). "
                f"Query keywords aligned with [{', '.join(matched_domains)}]. "
                f"After fusion: delta-Hk={delta_h:.2f} bits, entropy reduced to {h_posterior:.2f} bits."
            )
        else:
            reasoning = (
                f"Persona '{persona}' set initial priors (H0={h_prior:.2f} bits). "
                f"No domain keywords detected in query. "
                f"Classification relies on persona prior alone."
            )

        return {
            "intent": intent,
            "confidence": round(top_conf, 3),
            "entropy_reduction": round(entropy_reduction, 3),
            "delta_h": round(delta_h, 3),
            "reasoning": reasoning,
            "action": action,
            "scores": {d: round(s, 3) for d, s in ranked},
        }
