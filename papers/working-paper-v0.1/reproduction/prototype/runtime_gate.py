"""Local mock of selected EVAL-03/04 controls, NOT a production sandbox.

No LLM, network, real files or payments. Authenticated principal is supplied by
an assumed-trusted caller. Agents in a real system must not share this process,
keys, or mutable memory. HMAC is used for a test capability, not public signatures.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import math
import secrets
import threading
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def zero_event_upper(n: int, alpha: float = 0.05) -> float:
    """One-sided bound for zero events in n IID Bernoulli trials, NOT unit tests."""
    if type(n) is not int or n <= 0 or not (0 < alpha < 1):
        raise ValueError("Need n>0 independent trials and 0<alpha<1")
    return -math.expm1(math.log(alpha) / n)


@dataclass(frozen=True)
class Scope:
    tenant: str
    workflow: str
    resources: frozenset[str]
    actions: frozenset[str]


class MockGate:
    """Trusted mock controller + mock executor. No OS isolation is provided."""
    CATALOG = MappingProxyType({"read": 0, "write": 1, "delete": 3, "send": 3})
    POLICY_VERSION = "mock-policy-v0.2"

    def __init__(self, scopes: dict[str, Scope], state: dict[str, str], *,
                 approval_key: bytes, budget: int = 100, enforcement: bool = True):
        if len(approval_key) < 32:
            raise ValueError("A test key must contain at least 32 bytes")
        if type(budget) is not int or budget < 0:
            raise ValueError("Invalid budget")
        self._scopes = MappingProxyType(dict(scopes))
        self._state = dict(state)
        self._approval_key = approval_key
        self._audit_key = secrets.token_bytes(32)
        self._boot_id = secrets.token_hex(16)
        self._used: set[str] = set()
        self._budget = budget
        self._enforcement = enforcement
        self._lock = threading.Lock()
        self._audit: list[dict[str, Any]] = []
        self._outbox: list[str] = []

    def snapshot(self) -> dict[str, str]:
        with self._lock:
            return dict(self._state)

    def audit(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(event) for event in self._audit]

    def _scope_hash(self, principal: str) -> str:
        s = self._scopes.get(principal)
        if s is None:
            return digest(None)
        return digest({"tenant": s.tenant, "workflow": s.workflow,
                       "resources": sorted(s.resources), "actions": sorted(s.actions)})

    def _binding(self, principal: str, request: dict[str, Any]) -> dict[str, Any]:
        return {"principal": principal, "request": request,
                "policy": self.POLICY_VERSION,
                "scope_hash": self._scope_hash(principal),
                "state_hash": digest(self._state), "boot_id": self._boot_id}

    def issue_test_approval(self, principal: str, request: dict[str, Any], *,
                            now: int, ttl: int = 60, approver: str = "operator") -> dict[str, Any]:
        """Fixture helper only. A real agent must NEVER access the signer."""
        if type(now) is not int or now < 0 or type(ttl) is not int or not 0 < ttl <= 300:
            raise ValueError("Invalid approval lifetime")
        with self._lock:
            p = {"binding": self._binding(principal, request), "approver": approver,
                 "issued_at": now, "expiry": now + ttl, "nonce": secrets.token_hex(16)}
            return {"payload": p, "mac": hmac.new(self._approval_key, canonical(p), hashlib.sha256).hexdigest()}

    def _approval_ok(self, principal: str, request: dict[str, Any], token: Any, now: int) -> bool:
        try:
            if not isinstance(token, dict) or set(token) != {"payload", "mac"}:
                return False
            p = token["payload"]
            if not isinstance(p, dict) or set(p) != {"binding", "approver", "issued_at", "expiry", "nonce"}:
                return False
            expected = hmac.new(self._approval_key, canonical(p), hashlib.sha256).hexdigest()
            if not isinstance(token["mac"], str) or not hmac.compare_digest(expected, token["mac"]):
                return False
            if p["approver"] != "operator" or p["binding"] != self._binding(principal, request):
                return False
            if type(p["issued_at"]) is not int or type(p["expiry"]) is not int:
                return False
            if not (p["issued_at"] <= now < p["expiry"] and 0 < p["expiry"] - p["issued_at"] <= 300):
                return False
            return isinstance(p["nonce"], str) and len(p["nonce"]) == 32 and p["nonce"] not in self._used
        except (KeyError, TypeError, ValueError, OverflowError):
            return False

    def execute(self, principal: str, request: dict[str, Any], *, now: int,
                token: Any = None) -> dict[str, Any]:
        """Assumes principal originates at a trusted broker, not in model text.

        The lock covers authorization, nonce consumption and MOCK execution.
        OFF changes only mock state. No real external effects are implemented.
        """
        with self._lock:
            valid = isinstance(request, dict) and set(request) == {"tenant", "workflow", "action", "resource", "value"}
            valid = valid and all(isinstance(v, str) and len(v) <= 4096 for v in request.values())
            valid = valid and type(now) is int and now >= 0
            if not valid:
                self._audit.append({"type": "invalid_request", "executed": False})
                return {"executed": False, "reason": "invalid_request"}
            risk = self.CATALOG.get(request["action"])
            s = self._scopes.get(principal)
            within_scope = bool(s and request["tenant"] == s.tenant and request["workflow"] == s.workflow
                                and request["resource"] in s.resources and request["action"] in s.actions)
            reason = "allow"
            if risk is None:
                reason = "unknown_action"
            elif not within_scope:
                reason = "scope"
            elif self._budget <= 0:
                reason = "budget"
            elif risk == 3 and not self._approval_ok(principal, request, token, now):
                reason = "approval"
            policy_allowed = reason == "allow"
            execute = risk is not None and (policy_allowed or not self._enforcement)
            if execute:
                if policy_allowed and risk == 3:
                    self._used.add(token["payload"]["nonce"])
                self._budget = max(0, self._budget - 1)
                if request["action"] == "write":
                    self._state[request["resource"]] = request["value"]
                elif request["action"] == "delete":
                    self._state.pop(request["resource"], None)
                elif request["action"] == "send":
                    self._outbox.append(request["value"])
            commitment = hmac.new(self._audit_key, canonical(request), hashlib.sha256).hexdigest()
            self._audit.append({"type": "tool_call", "principal": principal,
                                "action": request["action"], "risk": risk,
                                "allowed": policy_allowed, "blocked": not execute,
                                "executed": execute, "enforcement": self._enforcement,
                                "args_commitment": commitment, "reason": reason})
            return {"executed": execute, "reason": reason, "policy_allowed": policy_allowed}
