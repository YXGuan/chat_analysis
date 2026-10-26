"""A transparent lexical baseline; replace assignments with Kura cluster labels later.

Only user messages are scored. One category wins per conversation so stacks
always sum to the chat count. Ties follow taxonomy order; no match stays Other.
"""

import re
from typing import Any

TAXONOMY = [
    {
        "id": "code",
        "name": "Software & code",
        "color": "#5578be",
        "terms": "python javascript typescript java programming code function script html css react sql database api algorithm error debug linux docker github array pandas c++ c# matlab regex".split(),
    },
    {
        "id": "creative",
        "name": "Stories & imagination",
        "color": "#ae7da0",
        "terms": "story stories fictional fiction character characters roleplay roleplaying scene scenes novel fantasy dialogue poem poetry screenplay fanfiction dragon magical".split(),
    },
    {
        "id": "language",
        "name": "Writing & language",
        "color": "#d49a4e",
        "terms": "translate translation grammar rewrite rephrase paraphrase essay paragraph proofreading vocabulary sentence sentences english spanish french german summarize summary letter email".split(),
    },
    {
        "id": "study",
        "name": "Science & learning",
        "color": "#6a9e8b",
        "terms": "physics chemistry biology science research scientific equation equations mathematics math calculate calculus theorem quantum probability statistics statistical experiment theory molecule cells university exam homework".split(),
    },
    {
        "id": "work",
        "name": "Business & work",
        "color": "#ca7465",
        "terms": "business marketing company companies customer customers product products sales revenue investment financial finance stock market startup resume career interview management strategy project presentation".split(),
    },
    {
        "id": "culture",
        "name": "Culture & entertainment",
        "color": "#8b91b6",
        "terms": "game games gaming movie movies music song songs film anime manga history historical politics political philosophy religion book books artist art sports football pokemon minecraft".split(),
    },
    {
        "id": "life",
        "name": "Everyday life",
        "color": "#9a9e52",
        "terms": "recipe recipes cook cooking food diet fitness exercise workout travel trip hotel health sleep relationship relationships friend friends family birthday vacation meal meals garden pet dog cat".split(),
    },
    {"id": "other", "name": "Other / unclassified", "color": "#b6b9ba", "terms": []},
]


def assign_categories(conversations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return auditable labels and matching terms using capped distinct-term scores."""
    results = {}
    for chat in conversations:
        text = "\n".join(
            m["content"] for m in chat["messages"] if m["role"] == "user"
        ).lower()
        tokens = set(re.findall(r"[a-z]+(?:\+\+|#)?", text))
        matches = [
            (category, sorted(tokens.intersection(category["terms"])))
            for category in TAXONOMY[:-1]
        ]
        category, terms = max(matches, key=lambda pair: len(pair[1]))
        results[chat["chat_id"]] = {
            "category": category["id"] if terms else "other",
            "matched_terms": terms,
            "method": "distinct-keywords-v1",
        }
    return results
