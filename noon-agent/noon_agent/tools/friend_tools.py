"""Friend resolution and fuzzy matching tools."""

from difflib import SequenceMatcher
from typing import Any, Dict, List


def fuzzy_match_score(a: str, b: str) -> float:
    """
    Calculate similarity score between two strings.

    Args:
        a: First string
        b: Second string

    Returns:
        Similarity score between 0 and 1
    """
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def search_friend(
    query: str, friends: List[Dict[str, str]], threshold: float = 0.6
) -> Dict[str, Any]:
    """
    Search for friends using fuzzy matching.

    Args:
        query: Name to search for
        friends: List of friend dicts with 'name', 'email', 'calendar_id'
        threshold: Minimum similarity score (0-1)

    Returns:
        {
            "matches": [...],
            "exact_match": bool,
            "top_match": {...} or None
        }
    """
    matches = []
    exact_match = False

    for friend in friends:
        score = fuzzy_match_score(query, friend["name"])

        if score >= threshold:
            matches.append(
                {
                    "name": friend["name"],
                    "email": friend["email"],
                    "calendar_id": friend["calendar_id"],
                    "confidence": round(score, 2),
                }
            )

            if score == 1.0:
                exact_match = True

    # Sort by confidence
    matches.sort(key=lambda x: x["confidence"], reverse=True)

    top_match = matches[0] if matches else None

    return {"matches": matches, "exact_match": exact_match, "top_match": top_match}


def resolve_attendees(
    attendee_names: List[str], friends: List[Dict[str, str]], threshold: float = 0.7
) -> Dict[str, Any]:
    """
    Resolve a list of attendee names to email addresses and calendar IDs.

    Args:
        attendee_names: List of names to resolve
        friends: List of friend dicts
        threshold: Minimum confidence for matching

    Returns:
        {
            "resolved": [...],  # Successfully resolved attendees
            "unresolved": [...],  # Names that couldn't be matched
            "ambiguous": [...]  # Names with multiple possible matches
        }
    """
    resolved = []
    unresolved = []
    ambiguous = []

    for name in attendee_names:
        result = search_friend(query=name, friends=friends, threshold=threshold)

        if not result["matches"]:
            unresolved.append({"name": name, "reason": "no_match"})
        elif len(result["matches"]) == 1 or result["exact_match"]:
            # Single match or exact match - resolve it
            match = result["matches"][0]
            resolved.append(
                {
                    "input_name": name,
                    "resolved_name": match["name"],
                    "email": match["email"],
                    "calendar_id": match["calendar_id"],
                    "confidence": match["confidence"],
                }
            )
        else:
            # Multiple matches - ambiguous
            ambiguous.append({"name": name, "possible_matches": result["matches"]})

    return {"resolved": resolved, "unresolved": unresolved, "ambiguous": ambiguous}
