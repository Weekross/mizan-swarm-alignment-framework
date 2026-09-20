"""Bounded in-process reference gate. NOT an OS sandbox or durable service.

A trusted broker supplies principal; a trusted constructor supplies the clock
and approver keys. TestAuthority is ONLY a fixture, not a human approval service.
No real network/files/payments. All methods belong to the trusted side except
execute(), which is exposed through an assumed authenticated broker.
"""
from __future__ import annotations
import copy
import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Callable


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def verify_audit(events, checkpoint):
    """Compare to a separately retained trusted checkpoint, not a supplied tip."""
    try:
        if len(events) != checkpoint["count"]:
            return False
        prev, last = "0" * 64, -1
        for seq, event in enumerate(events, 1):
            row = dict(event); digest = row.pop("hash")
            if row["seq"] != seq or row["prev"] != prev or row["mono_ns"] < last:
                return False
            if row["boot"] != checkpoint["boot"] or sha(row) != digest:
                return False
            last, prev = row["mono_ns"], digest
        return prev == checkpoint["tip"]
    except (KeyError, TypeError, ValueError):
        return False


@dataclass(frozen=True)
class Scope:
    tenant: str
    workflow: str
    resources: frozenset[str]
    actions: frozenset[str]


class TestAuthority:
    """Synthetic signing fixture. Never give this or its keys to an agent."""
    def __init__(self, keys):
        self._keys = dict(keys)

    def sign(self, payload, ids):
        return {"payload": copy.deepcopy(payload), "signatures": [
            {"id": who, "mac": hmac.new(self._keys[who], canonical(payload), hashlib.sha256).hexdigest()}
            for who in ids]}


class Gate:
    CATALOG = MappingProxyType({"read": 0, "write": 1, "delete": 3, "send": 3})
    POLICY = "gate-v0.3-two-approvers"

    def __init__(self, scopes: dict[str, Scope], state: dict[tuple[str, str], str], *,
                 approver_keys: dict[str, bytes], clock: Callable[[], int] | None = None,
                 attempt_limit=100, execution_limit=100, audit_limit=512, challenge_limit=64):
        if len(approver_keys) < 2 or len(set(approver_keys.values())) != len(approver_keys):
            raise ValueError("Need distinct fixture identities AND keys")
        if any(type(k) is not bytes or len(k) < 32 for k in approver_keys.values()):
            raise ValueError("Need >=32-byte keys")
        if any(type(n) is not int or n < 1 for n in (attempt_limit, execution_limit, audit_limit, challenge_limit)):
            raise ValueError("Positive bounded capacities required")
        self._scopes = MappingProxyType({p: Scope(s.tenant, s.workflow, frozenset(s.resources),
                                                 frozenset(s.actions)) for p, s in scopes.items()})
        self._state = dict(state)
        self._versions = {k: 0 for k in state}
        self._keys = MappingProxyType(dict(approver_keys))
        self._clock = clock or time.monotonic_ns
        self._last = -1
        self._boot = secrets.token_hex(16)
        self._commit_key = secrets.token_bytes(32)
        self._lock = threading.Lock()
        self._attempts, self._executions = 0, 0
        self._attempt_limit, self._execution_limit = attempt_limit, execution_limit
        self._audit_limit, self._challenge_limit = audit_limit, challenge_limit
        self._issued = 0
        self._pending, self._spent, self._revoked = {}, set(), set()
        self._revoked_principals = set()
        self._events, self._effects = [], []
        self._halted, self._suppressed = False, 0

    def _now(self):
        value = self._clock()
        if type(value) is not int or value < 0 or value < self._last:
            self._halted = True
            raise ValueError("clock_fault")
        self._last = value
        return value

    def _room(self):
        if len(self._events) >= self._audit_limit:
            self._suppressed = min(self._suppressed + 1, 2**63 - 1)
            return False
        return True

    def _record(self, kind, principal, reason, executed, now, commitment=None):
        row = {"seq": len(self._events) + 1, "boot": self._boot,
               "mono_ns": now, "utc": datetime.now(timezone.utc).isoformat(),
               "kind": kind, "principal": principal if principal in self._scopes else "unknown",
               "reason": reason, "executed": executed, "args_commitment": commitment,
               "attempts": self._attempts, "executions": self._executions,
               "prev": self._events[-1]["hash"] if self._events else "0" * 64}
        row["hash"] = sha(row)
        self._events.append(row)

    def _finish(self, principal, reason, executed, now, commitment=None):
        self._record("tool_call", principal, reason, executed, now, commitment)
        return {"executed": executed, "reason": reason, "audited": True}

    @staticmethod
    def _request(raw):
        # Real transport must enforce a byte limit before JSON decoding.
        if type(raw) is not dict or set(raw) != {"tenant", "workflow", "action", "resource", "value"}:
            raise ValueError("invalid_request")
        if any(type(v) is not str or len(v) > 4096 for v in raw.values()):
            raise ValueError("invalid_request")
        return dict(raw)

    def _scope_reason(self, principal, r):
        s = self._scopes.get(principal)
        if s is None: return "unknown_principal"
        if principal in self._revoked_principals: return "principal_revoked"
        if r["tenant"] != s.tenant: return "scope_tenant"
        if r["workflow"] != s.workflow: return "scope_workflow"
        if r["resource"] not in s.resources: return "scope_resource"
        if r["action"] not in self.CATALOG: return "unknown_action"
        if r["action"] not in s.actions: return "scope_action"
        return None

    def _binding(self, principal, r):
        s = self._scopes[principal]
        resource = (r["tenant"], r["resource"])
        return {"principal": principal, "request": r, "policy": self.POLICY, "boot": self._boot,
                "scope": sha([s.tenant, s.workflow, sorted(s.resources), sorted(s.actions)]),
                "resource_version": self._versions.get(resource, 0)}

    def challenge(self, principal, raw, *, ttl_seconds=60):
        """Trusted broker API. Signing happens separately in the test authority."""
        with self._lock:
            if not self._room(): raise ValueError("audit_full")
            now = self._now(); r = self._request(raw)
            reason = self._scope_reason(principal, r)
            if reason or self._halted: raise ValueError(reason or "halted")
            if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 300:
                raise ValueError("invalid_ttl")
            if self._issued >= self._challenge_limit: raise ValueError("challenge_budget")
            nonce = secrets.token_hex(16)
            p = {"binding": self._binding(principal, r), "issued_ns": now,
                 "expiry_ns": now + ttl_seconds * 10**9, "nonce": nonce}
            self._pending[nonce] = sha(p); self._issued += 1
            self._record("challenge", principal, "issued", False, now)
            return copy.deepcopy(p)

    def _approval_reason(self, principal, r, token, now):
        try:
            if type(token) is not dict or set(token) != {"payload", "signatures"}: return "approval_format"
            p, signatures = token["payload"], token["signatures"]
            if type(p) is not dict or set(p) != {"binding", "issued_ns", "expiry_ns", "nonce"}:
                return "approval_format"
            if type(p["nonce"]) is not str: return "approval_format"
            if p["nonce"] in self._spent: return "approval_replayed"
            if p["nonce"] in self._revoked: return "approval_revoked"
            if self._pending.get(p["nonce"]) != sha(p): return "approval_unknown"
            if p["binding"] != self._binding(principal, r): return "approval_binding"
            if not p["issued_ns"] <= now < p["expiry_ns"]: return "approval_expired"
            if type(signatures) is not list or not 2 <= len(signatures) <= len(self._keys):
                return "approval_quorum"
            seen = set()
            for sig in signatures:
                if type(sig) is not dict or set(sig) != {"id", "mac"}: return "approval_format"
                who = sig["id"]
                if type(who) is not str or who not in self._keys: return "approval_approver"
                if who == principal: return "approval_self"
                if who in seen: return "approval_duplicate"
                expected = hmac.new(self._keys[who], canonical(p), hashlib.sha256).hexdigest()
                if type(sig["mac"]) is not str or not hmac.compare_digest(expected, sig["mac"]):
                    return "approval_signature"
                seen.add(who)
            return None
        except (TypeError, KeyError, ValueError):
            return "approval_format"

    def _before_commit(self):
        """No-op scheduling seam used by tests; not an exposed callback API."""
        pass

    def execute(self, principal, raw, *, approval=None):
        """No caller-controlled timestamp. Only in-memory effects are atomic."""
        with self._lock:
            if not self._room(): return {"executed": False, "reason": "audit_full", "audited": False}
            try: now = self._now()
            except ValueError:
                return self._finish(principal, "clock_fault", False, max(self._last, 0))
            if self._attempts >= self._attempt_limit:
                return self._finish(principal, "attempt_budget", False, now)
            self._attempts += 1
            if self._halted: return self._finish(principal, "halted", False, now)
            try: r = self._request(raw)
            except ValueError: return self._finish(principal, "invalid_request", False, now)
            commitment = hmac.new(self._commit_key, canonical(r), hashlib.sha256).hexdigest()
            reason = self._scope_reason(principal, r)
            if reason: return self._finish(principal, reason, False, now, commitment)
            if self._executions >= self._execution_limit:
                return self._finish(principal, "execution_budget", False, now, commitment)
            if self.CATALOG[r["action"]] == 3:
                reason = self._approval_reason(principal, r, approval, now)
                if reason: return self._finish(principal, reason, False, now, commitment)
            self._before_commit()
            # Re-read time after potential scheduler delay; nonce/authorization stay
            # under the same lock. Do not use this mock around an external RPC.
            try: now = self._now()
            except ValueError:
                return self._finish(principal, "clock_fault", False, max(self._last, 0), commitment)
            if self.CATALOG[r["action"]] == 3 and now >= approval["payload"]["expiry_ns"]:
                return self._finish(principal, "approval_expired", False, now, commitment)
            if self.CATALOG[r["action"]] == 3:
                self._spent.add(approval["payload"]["nonce"])
            self._executions += 1
            key = (r["tenant"], r["resource"])
            if r["action"] == "write": self._state[key] = r["value"]
            if r["action"] == "delete": self._state.pop(key, None)
            if r["action"] in {"write", "delete"}:
                self._versions[key] = self._versions.get(key, 0) + 1
            self._effects.append({"action": r["action"], "tenant": r["tenant"], "resource": r["resource"]})
            return self._finish(principal, "allow", True, now, commitment)

    def halt(self):
        with self._lock:
            self._halted = True
            if self._room(): self._record("halt", "admin", "halted", False, max(self._last, 0))

    def revoke(self, nonce):
        with self._lock:
            if nonce not in self._pending: raise ValueError("unknown_nonce")
            self._revoked.add(nonce)
            if self._room(): self._record("revoke", "admin", "approval_revoked", False, max(self._last, 0))

    def revoke_principal(self, principal):
        with self._lock:
            if principal not in self._scopes: raise ValueError("unknown_principal")
            self._revoked_principals.add(principal)
            if self._room(): self._record("revoke_principal", principal, "principal_revoked", False, max(self._last, 0))

    def inspect(self):
        """Trusted test/admin observation, not an agent tool."""
        with self._lock:
            return copy.deepcopy({"state": self._state, "effects": self._effects,
                "audit": self._events, "attempts": self._attempts, "executions": self._executions,
                "suppressed": self._suppressed, "checkpoint": {
                    "boot": self._boot, "count": len(self._events),
                    "tip": self._events[-1]["hash"] if self._events else "0" * 64}})
