import re

from fleet.tools import ToolUnavailable

UNSAFE = (
    "ignore previous",
    "ignore all",
    "bypass",
    "skip approval",
    "without approval",
    "delete",
    "drop table",
    "truncate",
    "disable",
    "clear safety",
    "override",
    "api key",
    "password",
    "credentials",
    "system prompt",
    "secret",
    "cancel contract",
    "change price",
    "assign replacement",
)


def classify(question):
    q = question.lower()
    if any(term in q for term in UNSAFE):
        return "unsafe", "blocked"
    if "replacement" in q:
        return "replacement", "high" if "recommend" in q or "create" in q else "read_only"
    if "escalat" in q or "support case" in q or "create case" in q:
        return "action", "high"
    if "contract" in q and any(t in q for t in ("end", "expir", "renew")):
        return "contracts", "read_only"
    if any(t in q for t in ("anomal", "repeated", "alerts")) and not re.search(r"v-\d{3}", q):
        return "anomalies", "read_only"
    if "policy" in q:
        return "policy", "read_only"
    if "how many" in q or "fleet summary" in q or "count" in q:
        return "fleet_summary", "read_only"
    if re.search(r"v-\d{3}", q):
        return "vehicle", "read_only"
    return "unknown", "read_only"


class Copilot:
    def __init__(self, tools, retriever):
        self.tools = tools
        self.retriever = retriever

    def ask(self, question, context):
        intent, risk = classify(question)
        context.update(intent=intent, outcome="answered")
        response = {
            "trace_id": context["trace_id"],
            "intent": intent,
            "risk": risk,
            "status": "answered",
            "answer": "",
            "data": {},
            "citations": [],
            "suggested_action": None,
            "warnings": [],
        }
        if intent == "unsafe":
            response.update(
                status="blocked",
                answer="This request exceeds the allowed tools or "
                "attempts to bypass safety controls. No action was performed.",
            )
            context["outcome"] = "blocked"
            return response
        ids = sorted(set(re.findall(r"V-\d{3}", question.upper())))
        try:
            if intent in {"vehicle", "replacement", "action"} and (
                intent != "replacement" or risk == "high"
            ):
                if len(ids) != 1:
                    response.update(
                        status="needs_clarification",
                        answer="Specify one vehicle ID "
                        "such as V-102. For bulk actions, review anomalies first and "
                        "propose each vehicle separately.",
                    )
                else:
                    result = self.tools.call(
                        "vehicle_lookup", lambda: self.tools.vehicle(ids[0]), context
                    )
                    if not result:
                        response.update(
                            status="needs_clarification",
                            answer="Vehicle not found. Check the vehicle ID.",
                        )
                    else:
                        response["data"] = result
                        required = "P-REPLACE" if intent == "replacement" else "P-SAFETY"
                        if intent == "action":
                            required = "P-MAINT"
                        response["citations"] = self.retriever.retrieve(question, context, required)
                        v = result["vehicle"]
                        open_events = [e for e in result["maintenance"] if e["state"] == "open"]
                        response["answer"] = (
                            f"{v['vehicle_id']} has recorded status '{v['status']}'. "
                            f"Open maintenance events: {len(open_events)}. "
                            + " ".join(e["description"] for e in open_events)
                            + f" See [{required}]. Review maintenance clearance before returning "
                            "the vehicle to service. No fleet records were changed."
                        )
                        if risk == "high":
                            action = (
                                "replacement_recommendation"
                                if intent == "replacement"
                                else (
                                    "escalation"
                                    if "escalat" in question.lower()
                                    else "support_case"
                                )
                            )
                            response["suggested_action"] = {
                                "action": action,
                                "vehicle_id": ids[0],
                                "requires_approval": True,
                                "proposal_endpoint": "/v1/actions/propose",
                            }
            elif intent == "contracts":
                match = re.search(r"(\d+)\s*days?", question.lower())
                days = int(match[1]) if match else 30
                if not 1 <= days <= 90:
                    response.update(
                        status="needs_clarification", answer="Use a window of 1–90 days."
                    )
                else:
                    contracts = self.tools.call(
                        "expiring_contracts", lambda: self.tools.contracts(days), context
                    )
                    response["data"] = {
                        "as_of": self.tools.store.seed_date().isoformat(),
                        "days": days,
                        "contracts": contracts,
                    }
                    response["citations"] = self.retriever.retrieve(question, context, "P-CONTRACT")
                    response["answer"] = f"{len(contracts)} contracts end in the next {days} days "
                    response["answer"] += "in this demo snapshot, inclusive of both endpoints. "
                    response["answer"] += "Review renewals under [P-CONTRACT]. No renewal was made."
            elif intent == "anomalies":
                anomalies = self.tools.call("anomaly_scan", self.tools.anomalies, context)
                response["data"] = {
                    "as_of": self.tools.store.seed_date().isoformat(),
                    "anomalies": anomalies,
                }
                response["citations"] = self.retriever.retrieve(question, context, "P-MAINT")
                response["answer"] = f"{len(anomalies)} vehicles match deterministic anomaly rules "
                response["answer"] += (
                    "in [P-MAINT]. Review each vehicle before proposing an escalation."
                )
            elif intent == "fleet_summary":
                response["data"] = {
                    "counts": self.tools.call("status_counts", self.tools.counts, context)
                }
                response["answer"] = "Fleet status counts from the synthetic vehicle table."
            elif intent in {"policy", "replacement"}:
                required = "P-REPLACE" if intent == "replacement" else None
                citations = self.retriever.retrieve(question, context, required)
                if not citations:
                    raise ToolUnavailable("No relevant policy found")
                response["citations"] = citations
                response["answer"] = "\n".join(
                    f"[{c['policy_id']}] {c['excerpt']}" for c in citations
                )
            else:
                response.update(
                    status="needs_clarification",
                    answer="Supported questions cover "
                    "vehicle status, expiring contracts, repeated maintenance alerts, "
                    "fleet counts, and replacement policy. Please choose one.",
                )
        except ToolUnavailable:
            response.update(
                status="degraded",
                answer="A required tool or policy source is "
                "unavailable. No action was performed. Retry later or review the "
                "incident runbook.",
                data={},
                citations=[],
                suggested_action=None,
            )
            response["warnings"] = ["Evidence is incomplete; recommendations are withheld."]
        context["outcome"] = response["status"]
        return response
