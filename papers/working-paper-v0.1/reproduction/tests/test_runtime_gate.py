"""Deterministic unit tests. These are NOT LLM episodes or validation of MSAF."""
import copy
import json
import unittest
from runtime_gate import MockGate, Scope, zero_event_upper

KEY = b"synthetic-only-test-key-32-bytes!!"

def make_gate(**kwargs):
    return MockGate({"worker": Scope("tenant-A", "wf-1", frozenset({"doc-1"}),
                                     frozenset({"read", "write", "delete", "send"})),
                     "other": Scope("tenant-A", "wf-1", frozenset({"doc-1"}), frozenset({"delete"}))},
                    {"doc-1": "synthetic data"}, approval_key=KEY, **kwargs)

def req(action="delete", **changes):
    r = {"tenant": "tenant-A", "workflow": "wf-1", "action": action, "resource": "doc-1", "value": ""}
    r.update(changes)
    return r

class GateTests(unittest.TestCase):
    def test_legal_read(self):
        self.assertTrue(make_gate().execute("worker", req("read"), now=1)["executed"])
    def test_unknown_principal(self):
        self.assertFalse(make_gate().execute("fake", req("read"), now=1)["executed"])
    def test_other_tenant(self):
        self.assertFalse(make_gate().execute("worker", req("read", tenant="tenant-B"), now=1)["executed"])
    def test_other_resource(self):
        self.assertFalse(make_gate().execute("worker", req("read", resource="doc-2"), now=1)["executed"])
    def test_unknown_action(self):
        self.assertFalse(make_gate().execute("worker", req("expand_scope"), now=1)["executed"])
    def test_agent_supplied_risk_rejected(self):
        self.assertFalse(make_gate().execute("worker", req(risk=0), now=1)["executed"])
    def test_agent_supplied_identity_rejected(self):
        self.assertFalse(make_gate().execute("worker", req("read", agent_id="operator"), now=1)["executed"])
    def test_missing_approval_preserves_state(self):
        g=make_gate();before=g.snapshot()
        self.assertFalse(g.execute("worker",req(),now=1)["executed"])
        self.assertEqual(before,g.snapshot())
    def test_valid_approval_has_effect(self):
        g=make_gate();r=req();t=g.issue_test_approval("worker",r,now=1)
        self.assertTrue(g.execute("worker",r,now=2,token=t)["executed"])
        self.assertNotIn("doc-1",g.snapshot())
    def test_forged_mac(self):
        g=make_gate();r=req();t=g.issue_test_approval("worker",r,now=1);t["mac"]="0"*64
        self.assertFalse(g.execute("worker",r,now=2,token=t)["executed"])
    def test_expired(self):
        g=make_gate();r=req();t=g.issue_test_approval("worker",r,now=1,ttl=2)
        self.assertFalse(g.execute("worker",r,now=3,token=t)["executed"])
    def test_replay(self):
        g=make_gate();r=req("send");t=g.issue_test_approval("worker",r,now=1)
        self.assertTrue(g.execute("worker",r,now=2,token=t)["executed"])
        self.assertFalse(g.execute("worker",r,now=2,token=t)["executed"])
    def test_other_arguments(self):
        g=make_gate();t=g.issue_test_approval("worker",req("send",value="a"),now=1)
        self.assertFalse(g.execute("worker",req("send",value="b"),now=2,token=t)["executed"])
    def test_other_workflow(self):
        g=make_gate();t=g.issue_test_approval("worker",req(),now=1)
        self.assertFalse(g.execute("worker",req(workflow="wf-2"),now=2,token=t)["executed"])
    def test_other_principal_with_permission(self):
        g=make_gate();t=g.issue_test_approval("worker",req(),now=1)
        self.assertFalse(g.execute("other",req(),now=2,token=t)["executed"])
    def test_approval_cannot_create_scope(self):
        g=make_gate();r=req(resource="doc-2");t=g.issue_test_approval("worker",r,now=1)
        self.assertEqual(g.execute("worker",r,now=2,token=t)["reason"],"scope")
    def test_state_changed_since_approval(self):
        g=make_gate();t=g.issue_test_approval("worker",req(),now=1)
        g.execute("worker",req("write",value="changed"),now=1)
        self.assertFalse(g.execute("worker",req(),now=2,token=t)["executed"])
    def test_budget(self):
        self.assertFalse(make_gate(budget=0).execute("worker",req("read"),now=1)["executed"])
    def test_old_token_after_restart(self):
        g=make_gate();t=g.issue_test_approval("worker",req(),now=1)
        self.assertFalse(make_gate().execute("worker",req(),now=2,token=t)["executed"])
    def test_log_does_not_store_raw_value_or_token(self):
        g=make_gate();r=req("send",value="SYNTHETIC-CANARY-742")
        t=g.issue_test_approval("worker",r,now=1);g.execute("worker",r,now=2,token=t)
        a=json.dumps(g.audit());self.assertNotIn(r["value"],a);self.assertNotIn(t["mac"],a)
    def test_off_mode_is_unsafe_mock_control(self):
        g=make_gate(enforcement=False)
        out=g.execute("worker",req(),now=1)
        self.assertTrue(out["executed"]);self.assertFalse(out["policy_allowed"])
        self.assertNotIn("doc-1",g.snapshot())
    def test_malformed_token(self):
        self.assertFalse(make_gate().execute("worker",req(),now=1,token={"payload":[]})["executed"])
    def test_zero_event_bound(self):
        self.assertAlmostEqual(zero_event_upper(500),0.0059735515,places=9)
    def test_zero_denominator_raises(self):
        with self.assertRaises(ValueError):zero_event_upper(0)

if __name__ == "__main__":
    unittest.main()
