import copy
import json
import threading
import unittest
from queue import SimpleQueue
from unittest.mock import patch
from gate import Gate, Scope, TestAuthority, verify_audit

KEYS = {"reviewer-a": b"a"*32, "reviewer-b": b"b"*32, "worker": b"w"*32}
class Clock:
    def __init__(self): self.n = 10**9
    def __call__(self): return self.n
    def advance(self, seconds): self.n += seconds * 10**9

def request(action="read", **changes):
    return {"tenant":"t1", "workflow":"wf1", "action":action, "resource":"doc", "value":"", **changes}

def make(**kwargs):
    scopes = {"worker": Scope("t1", "wf1", frozenset({"doc", "other"}), frozenset(Gate.CATALOG)),
              "reader": Scope("t1", "wf1", frozenset({"doc"}), frozenset({"read"})),
              "t2-worker": Scope("t2", "wf1", frozenset({"doc"}), frozenset(Gate.CATALOG))}
    c = Clock()
    return Gate(scopes, {("t1","doc"):"old", ("t1","other"):"unrelated", ("t2","doc"):"separate"},
                approver_keys=KEYS, clock=c, **kwargs), c

def approve(g, r=None, who="worker", ids=("reviewer-a","reviewer-b"), ttl=60):
    return TestAuthority(KEYS).sign(g.challenge(who, r or request("delete"), ttl_seconds=ttl), ids)

class GateTests(unittest.TestCase):
    def denied(self, g, r, reason, *, who="worker", approval=None):
        before=g.inspect()
        result=g.execute(who, r, approval=approval)
        self.assertEqual(result["reason"],reason)
        self.assertFalse(result["executed"])
        after=g.inspect()
        self.assertEqual(before["state"],after["state"])
        self.assertEqual(before["effects"],after["effects"])
        if result["audited"]:
            self.assertEqual(len(after["audit"]),len(before["audit"])+1)
            self.assertEqual(after["audit"][-1]["reason"],reason)
            self.assertFalse(after["audit"][-1]["executed"])
        return result

    def test_legal_read_is_audited(self):
        g,c=make(); self.assertTrue(g.execute("reader",request())["executed"])
        a=g.inspect(); self.assertEqual(len(a["audit"]),1)
        self.assertEqual(a["audit"][0]["kind"],"tool_call")
        self.assertTrue(a["audit"][0]["executed"])
        self.assertEqual(a["executions"],1)

    def test_workflow_scope_without_approval_masking(self):
        g,_=make();self.denied(g,request(workflow="wf2"),"scope_workflow")
    def test_action_scope_without_approval_masking(self):
        g,_=make();self.denied(g,request("write",value="bad"),"scope_action",who="reader")
    def test_tenant_scope(self):
        g,_=make();self.denied(g,request(tenant="t2"),"scope_tenant")
    def test_resource_scope(self):
        g,_=make();self.denied(g,request(resource="missing"),"scope_resource")
    def test_unknown_action(self):
        g,_=make();self.denied(g,request("shell"),"unknown_action")
    def test_unknown_principal(self):
        g,_=make();self.denied(g,request(),"unknown_principal",who="attacker")
    def test_bad_request_extra_fields(self):
        g,_=make();self.denied(g,request(now=0),"invalid_request")
    def test_caller_cannot_supply_clock_argument(self):
        g,_=make()
        with self.assertRaises(TypeError): g.execute("worker",request(),now=0)
    def test_input_size(self):
        g,_=make();self.denied(g,request(value="a"*4097),"invalid_request")
    def test_internal_default_clock(self):
        with patch("gate.time.monotonic_ns", return_value=123456) as clock:
            g=Gate({"p":Scope("t","wf",frozenset({"x"}),frozenset({"read"}))},{},approver_keys=KEYS)
            self.assertTrue(g.execute("p",request(tenant="t",workflow="wf",resource="x"))["executed"])
            self.assertGreaterEqual(clock.call_count,2)
            self.assertEqual(len(g.inspect()["audit"]),1)
            self.assertEqual(g.inspect()["audit"][-1]["mono_ns"],123456)
    def test_clock_rollback_halts(self):
        g,c=make();g.execute("worker",request());c.n-=1
        self.denied(g,request(),"clock_fault")
    def test_clock_fault_at_commit_is_audited(self):
        g,c=make(); g._before_commit=lambda: setattr(c,"n",0)
        self.denied(g,request("write",value="new"),"clock_fault")
    def test_missing_approval(self):
        g,_=make();self.denied(g,request("delete"),"approval_format")
    def test_two_distinct_approvers_allow(self):
        g,_=make();r=request("delete");t=approve(g,r)
        self.assertTrue(g.execute("worker",r,approval=t)["executed"])
        self.assertNotIn(("t1","doc"),g.inspect()["state"])
        self.assertIn(("t2","doc"),g.inspect()["state"])
    def test_one_approver_insufficient(self):
        g,_=make();t=approve(g,ids=("reviewer-a",))
        self.denied(g,request("delete"),"approval_quorum",approval=t)
    def test_duplicate_approver_insufficient(self):
        g,_=make();t=approve(g,ids=("reviewer-a","reviewer-a"))
        self.denied(g,request("delete"),"approval_duplicate",approval=t)
    def test_self_approver_is_rejected_with_valid_signature(self):
        g,_=make();t=approve(g,ids=("worker","reviewer-a"))
        self.denied(g,request("delete"),"approval_self",approval=t)
    def test_unknown_approver(self):
        g,_=make();t=approve(g);t["signatures"][0]["id"]="stranger"
        self.denied(g,request("delete"),"approval_approver",approval=t)
    def test_bad_signature(self):
        g,_=make();t=approve(g);t["signatures"][0]["mac"]="0"*64
        self.denied(g,request("delete"),"approval_signature",approval=t)
    def test_expiry_uses_internal_clock(self):
        g,c=make();t=approve(g,ttl=2);c.advance(2)
        self.denied(g,request("delete"),"approval_expired",approval=t)
    def test_expiry_during_commit_delay(self):
        g,c=make();t=approve(g,ttl=2);g._before_commit=lambda:c.advance(2)
        self.denied(g,request("delete"),"approval_expired",approval=t)
    def test_argument_binding(self):
        g,_=make();t=approve(g,request("send",value="a"))
        self.denied(g,request("send",value="b"),"approval_binding",approval=t)
    def test_scope_precedes_valid_approval(self):
        g,_=make();t=approve(g,request("send"))
        self.denied(g,request("send"),"scope_action",who="reader",approval=t)
    def test_approval_for_wrong_principal_in_scope(self):
        g,_=make();t=approve(g,request("send"))
        self.denied(g,request("send",tenant="t2"),"approval_binding",who="t2-worker",approval=t)
    def test_replay_same_state(self):
        g,_=make();r=request("send");t=approve(g,r)
        self.assertTrue(g.execute("worker",r,approval=t)["executed"])
        self.denied(g,r,"approval_replayed",approval=t)
    def test_revoke(self):
        g,_=make();t=approve(g);g.revoke(t["payload"]["nonce"])
        self.denied(g,request("delete"),"approval_revoked",approval=t)
    def test_halt(self):
        g,_=make();g.halt();self.denied(g,request("write"),"halted")
    def test_principal_revoked(self):
        g,_=make();g.revoke_principal("worker")
        self.denied(g,request(),"principal_revoked")
    def test_target_changed_invalidates_approval(self):
        g,_=make();t=approve(g);g.execute("worker",request("write",value="changed"))
        self.denied(g,request("delete"),"approval_binding",approval=t)
    def test_aba_target_version(self):
        g,_=make();t=approve(g)
        g.execute("worker",request("write",value="changed"));g.execute("worker",request("write",value="old"))
        self.denied(g,request("delete"),"approval_binding",approval=t)
    def test_unrelated_state_does_not_invalidate(self):
        g,_=make();t=approve(g);g.execute("worker",request("write",resource="other",value="changed"))
        self.assertTrue(g.execute("worker",request("delete"),approval=t)["executed"])
    def test_reboot_invalidates_token(self):
        g,_=make();t=approve(g);other,_=make()
        self.denied(other,request("delete"),"approval_unknown",approval=t)
    def test_execution_budget_spent(self):
        g,_=make(execution_limit=1);g.execute("worker",request())
        self.denied(g,request(),"execution_budget")
    def test_denials_spend_attempt_budget(self):
        g,_=make(attempt_limit=2)
        self.denied(g,request(workflow="bad"),"scope_workflow")
        self.denied(g,request(workflow="bad"),"scope_workflow")
        self.denied(g,request(),"attempt_budget")
        self.assertEqual(g.inspect()["attempts"],2)
    def test_audit_limit_fails_closed_no_unbounded_growth(self):
        g,_=make(audit_limit=2)
        for _ in range(2): self.denied(g,request(workflow="bad"),"scope_workflow")
        for _ in range(100): self.denied(g,request(),"audit_full")
        a=g.inspect();self.assertEqual(len(a["audit"]),2);self.assertEqual(a["suppressed"],100)
    def test_approval_issue_budget(self):
        g,_=make(challenge_limit=1);approve(g)
        with self.assertRaisesRegex(ValueError,"challenge_budget"):approve(g)
    def test_log_presence_and_redaction(self):
        g,_=make();r=request("send",value="CANARY-123");t=approve(g,r)
        g.execute("worker",r,approval=t);a=g.inspect()
        calls=[e for e in a["audit"] if e["kind"]=="tool_call"]
        self.assertEqual(len(calls),1)
        self.assertTrue(calls[0]["executed"])
        text=json.dumps(a["audit"]);self.assertNotIn("CANARY-123",text)
        self.assertNotIn(t["signatures"][0]["mac"],text)
        self.assertEqual(len(calls[0]["args_commitment"]),64)
    def test_audit_seq_time_chain(self):
        g,c=make();g.execute("worker",request());c.advance(1);g.execute("worker",request())
        a=g.inspect();self.assertTrue(verify_audit(a["audit"],a["checkpoint"]))
        self.assertEqual([e["seq"] for e in a["audit"]],[1,2])
        self.assertGreater(a["audit"][1]["mono_ns"],a["audit"][0]["mono_ns"])
        self.assertIn("+00:00",a["audit"][0]["utc"])
    def test_audit_tamper(self):
        g,_=make();g.execute("worker",request());a=g.inspect()
        self.assertEqual(len(a["audit"]),1);a["audit"][0]["reason"]="tampered"
        self.assertFalse(verify_audit(a["audit"],a["checkpoint"]))
    def test_audit_truncation_with_checkpoint(self):
        g,_=make();g.execute("worker",request());a=g.inspect()
        self.assertFalse(verify_audit([],a["checkpoint"]))
    def test_audit_inspect_returns_copy(self):
        g,_=make();g.execute("worker",request());a=g.inspect();a["audit"].clear()
        self.assertEqual(len(g.inspect()["audit"]),1)

    def test_two_threads_replay_atomic_mock_effect(self):
        # Controlled interleaving: first is held immediately before commit;
        # second demonstrably attempts lock acquisition. A no-op lock lets it
        # commit before first is released. Not a general concurrency proof.
        g,_=make();r=request("send");t=approve(g,r)
        entered,release,tried,done2= (threading.Event() for _ in range(4))
        real=g._lock
        class ObservedLock:
            def __enter__(self):
                if threading.current_thread().name=="second":tried.set()
                return real.__enter__()
            def __exit__(self,*args):return real.__exit__(*args)
        g._lock=ObservedLock()
        def seam():
            if threading.current_thread().name=="first":
                entered.set()
                if not release.wait(3):raise RuntimeError("test scheduling timeout")
        g._before_commit=seam
        results=SimpleQueue()
        def run():
            try:results.put(g.execute("worker",r,approval=t))
            except Exception as exc:results.put(exc)
            finally:
                if threading.current_thread().name=="second":done2.set()
        a=threading.Thread(target=run,name="first",daemon=True)
        b=threading.Thread(target=run,name="second",daemon=True)
        a.start()
        try:
            self.assertTrue(entered.wait(3));b.start();self.assertTrue(tried.wait(3))
            early=done2.wait(.15)
        finally:
            release.set();a.join(3)
            if b.ident is not None:b.join(3)
        self.assertFalse(a.is_alive());self.assertFalse(b.is_alive())
        out=[results.get(),results.get()]
        self.assertTrue(all(isinstance(x,dict) for x in out),out)
        self.assertEqual(sum(x["executed"] for x in out),1,out)
        self.assertFalse(early,"Second entered an allegedly atomic section")
        self.assertEqual(sorted(x["reason"] for x in out),["allow","approval_replayed"])
        self.assertEqual(len(g.inspect()["effects"]),1)

if __name__=="__main__":unittest.main()
