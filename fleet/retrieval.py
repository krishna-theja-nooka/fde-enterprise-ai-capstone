import re

from fleet.tools import ToolUnavailable

POLICY_FOR_ACTION = {
    "support_case": "P-MAINT",
    "escalation": "P-MAINT",
    "replacement_recommendation": "P-REPLACE",
}


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class Retriever:
    """Lexical matching over a versioned, controlled policy corpus."""

    def __init__(self, store):
        self.store = store

    def retrieve(self, query, context, required_id=None):
        if context.get("fault") == "retrieval_failure":
            raise ToolUnavailable("Policy retrieval unavailable")
        rows = self.store.rows("SELECT * FROM fleet_policies ORDER BY policy_id")
        scored = [(len(tokens(query) & tokens(p["title"] + " " + p["content"])), p) for p in rows]
        chosen = [p for score, p in sorted(scored, key=lambda item: -item[0]) if score > 0][:2]
        if required_id:
            required = next((p for p in rows if p["policy_id"] == required_id), None)
            if required is None:
                raise ToolUnavailable("Required policy missing; fail closed")
            chosen = [required] + [p for p in chosen if p["policy_id"] != required_id][:1]
        context["events"].append(
            {"type": "retrieval", "policy_ids": [p["policy_id"] for p in chosen]}
        )
        return [self.citation(p) for p in chosen]

    @staticmethod
    def citation(policy):
        return {
            "policy_id": policy["policy_id"],
            "title": policy["title"],
            "section": policy["section"],
            "version": policy["version"],
            "excerpt": policy["content"],
            "source": policy["source"],
        }
