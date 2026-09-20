"""Executable, bounded reference treatments for closed-corpus multiple-choice QA.

NOT the general MSAF agent factory. No hidden ground truth in engine input.
Fixture and trusted command transports; no built-in remote model calls.
Role separation is NOT statistical independence of model errors.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from collections import Counter
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parent
ARCHITECTURES = ("B0", "B1", "B2", "B3", "B4", "B5")
FRAMINGS = ("none", "neutral", "quran")
TRANSITIONS = {"INIT": {"PROPOSE","ERROR"}, "PROPOSE": {"DEBATE","VERIFY","AGGREGATE","ERROR"},
               "DEBATE": {"AGGREGATE","ERROR"}, "VERIFY": {"AGGREGATE","ERROR"},
               "AGGREGATE": {"DONE","ERROR"}, "DONE":set(),"ERROR":set()}
STATUS = {"KNOWN","INFERRED","UNCERTAIN","UNKNOWN"}
CITE_KEYS = {"doc_id","start","end"}
RESPONSE_KEYS = {"status","answer","missing_info","evidence","p_answerable","p_correct_if_committed"}

class ProtocolError(ValueError): pass


def canonical(x): return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)
def fingerprint(x): return hashlib.sha256(canonical(x).encode()).hexdigest()


def strict_json(raw):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d: raise ProtocolError("duplicate_json_key")
            d[k]=v
        return d
    def reject(x): raise ProtocolError("nonfinite_json")
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=reject)


def validate_task(task):
    if type(task) is not dict or set(task)!={"id","question","options","documents"}:
        raise ProtocolError("task_fields")
    if any(type(task[k]) is not str or not task[k] or len(task[k])>4096 for k in ("id","question")):
        raise ProtocolError("task_text")
    options=task["options"]
    if type(options) is not list or not 2<=len(options)<=16 or any(type(x) is not str or not x or len(x)>256 for x in options):
        raise ProtocolError("task_options")
    if len(set(options))!=len(options): raise ProtocolError("duplicate_option")
    docs=task["documents"]
    if type(docs) is not list or len(docs)>32: raise ProtocolError("documents")
    ids=set()
    for d in docs:
        if type(d) is not dict or set(d)!={"id","text","origin"}: raise ProtocolError("document_fields")
        if any(type(d[k]) is not str for k in d): raise ProtocolError("document_types")
        if not d["id"] or d["id"] in ids or len(d["id"])>128 or len(d["origin"])>256 or len(d["text"])>8192:
            raise ProtocolError("document_bounds")
        ids.add(d["id"])
    return copy.deepcopy(task)


def citations(value, task):
    if type(value) is not list or len(value)>32: raise ProtocolError("evidence_list")
    docs={d["id"]:d for d in task["documents"]}
    for c in value:
        if type(c) is not dict or set(c)!=CITE_KEYS: raise ProtocolError("citation_fields")
        if type(c["doc_id"]) is not str or c["doc_id"] not in docs: raise ProtocolError("citation_source")
        if type(c["start"]) is not int or type(c["end"]) is not int: raise ProtocolError("citation_offsets")
        if not 0<=c["start"]<c["end"]<=len(docs[c["doc_id"]]["text"]): raise ProtocolError("citation_bounds")
    # These checks resolve text spans; they do NOT establish semantic entailment.


def validate_response(r, task):
    if type(r) is not dict or set(r)!=RESPONSE_KEYS: raise ProtocolError("response_fields")
    if type(r["status"]) is not str or r["status"] not in STATUS: raise ProtocolError("status")
    commit=r["status"] in {"KNOWN","INFERRED"}
    if commit and r["answer"] not in task["options"]: raise ProtocolError("answer")
    if not commit and r["answer"] is not None: raise ProtocolError("abstention_has_answer")
    m=r["missing_info"]
    if type(m) is not list or len(m)>16 or any(type(x) is not str or len(x)>512 for x in m):
        raise ProtocolError("missing_info")
    if not commit and not m: raise ProtocolError("abstention_without_reason")
    for k in ("p_answerable","p_correct_if_committed"):
        p=r[k]
        if p is not None and (type(p) not in (int,float) or not 0<=p<=1): raise ProtocolError("confidence")
    if not commit and r["p_correct_if_committed"] is not None: raise ProtocolError("abstention_confidence")
    citations(r["evidence"],task)
    return copy.deepcopy(r)


def validate_review(r, proposals, task):
    if type(r) is not dict or set(r)!={"verdicts"}: raise ProtocolError("review_fields")
    verdicts=r["verdicts"]
    if type(verdicts) is not list or len(verdicts)!=len(proposals): raise ProtocolError("verdict_count")
    by={}
    for v in verdicts:
        if type(v) is not dict or set(v)!={"proposal_id","support","evidence"}: raise ProtocolError("verdict_fields")
        pid=v["proposal_id"]
        if type(pid) is not str or pid not in proposals or pid in by: raise ProtocolError("verdict_id")
        if v["support"] not in {"ENTAILS","CONTRADICTS","INSUFFICIENT"}: raise ProtocolError("support")
        citations(v["evidence"],task)
        if v["support"]=="ENTAILS" and not v["evidence"]: raise ProtocolError("entails_without_evidence")
        by[pid]=copy.deepcopy(v)
    return by


@dataclass(frozen=True)
class Limits:
    max_calls: int = 6
    max_input_chars: int = 180000
    max_output_chars: int = 30000
    per_call_output_chars: int = 5000
    output_token_cap: int = 800  # passed to adapter, NOT enforceable for arbitrary commands
    call_timeout_seconds: int = 20
    total_seconds: int = 120


class FixtureProvider:
    """Scripted outputs only. It ignores prompts: cannot measure framing effects."""
    name="scripted-fixture";revision="v0.1";is_fixture=True
    def __init__(self, outputs):self.outputs=outputs;self.calls=[]
    def complete(self, job, timeout):
        self.calls.append(copy.deepcopy(job))
        if job["call_id"] not in self.outputs:raise ProtocolError("fixture_missing")
        return {"output":copy.deepcopy(self.outputs[job["call_id"]]),"usage":None}


class CommandProvider:
    """Trusted adapter command: one JSON job on stdin, {output,usage} on stdout.

    No shell. Timeout kills the direct subprocess, NOT arbitrary descendants.
    Temporary output is size-checked after process termination. This is not
    process/network isolation; adapter is TCB. Live adapters need separate review.
    """
    is_fixture=False
    def __init__(self,command,*,name,revision):
        if not command or not name or not revision:raise ValueError("Explicit trusted adapter and revision required")
        self.command=list(command);self.name=name;self.revision=revision
    def complete(self,job,timeout):
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            subprocess.run(self.command,input=canonical(job).encode(),stdout=out,stderr=err,
                           timeout=timeout,check=True,shell=False)
            if out.tell()>20000:raise ProtocolError("adapter_output_size")
            out.seek(0);return strict_json(out.read().decode("utf-8"))


class Engine:
    def __init__(self, provider, architecture="B2", framing="neutral", limits=Limits()):
        if architecture not in ARCHITECTURES or framing not in FRAMINGS:raise ValueError("Unknown treatment")
        self.provider,self.arch,self.framing,self.limits=provider,architecture,framing,limits
        self.prompts=strict_json((ROOT/'prompts.json').read_text())
        self.schema=strict_json((ROOT/'contracts.json').read_text())

    def run(self, raw_task):
        state="INIT"; trace=[]; calls=[]; proposals={};reviews={};inputs=outputs=0;started=time.monotonic()
        def move(new):
            nonlocal state
            if new not in TRANSITIONS[state]:raise ProtocolError("state_transition")
            trace.append({"from":state,"to":new});state=new
        def invoke(call_id,role,payload,kind):
            nonlocal inputs,outputs
            if len(calls)>=self.limits.max_calls:raise ProtocolError("call_budget")
            if time.monotonic()-started>=self.limits.total_seconds:raise ProtocolError("time_budget")
            job={"call_id":call_id,"role":role,"system":self.prompts["base"]+'\n'+self.prompts[role]+'\n'+self.prompts["framing"][self.framing],
                 "payload":copy.deepcopy(payload),"response_schema":self.schema["$defs"][kind],
                 "output_token_cap":self.limits.output_token_cap}
            size=len(canonical(job))
            if inputs+size>self.limits.max_input_chars:raise ProtocolError("input_budget")
            inputs+=size
            rec={"call_id":call_id,"role":role,"input_chars":size,"job_hash":fingerprint(job),"status":"started"};calls.append(rec)
            try:
                envelope=self.provider.complete(job,min(self.limits.call_timeout_seconds,
                                                        self.limits.total_seconds-(time.monotonic()-started)))
                if type(envelope) is not dict or set(envelope)!={"output","usage"}:raise ProtocolError("adapter_envelope")
                count=len(canonical(envelope["output"]))
                if count>self.limits.per_call_output_chars or outputs+count>self.limits.max_output_chars:
                    raise ProtocolError("output_budget")
                outputs+=count;rec.update(output_chars=count,output_hash=fingerprint(envelope["output"]),usage=envelope["usage"])
                if time.monotonic()-started>=self.limits.total_seconds:raise ProtocolError("time_budget")
                value=validate_response(envelope["output"],task) if kind=="response" else validate_review(envelope["output"],payload["proposals"],task)
                rec["status"]="valid";return value
            except Exception:
                rec["status"]="error";raise
        def abstain(reason, conflict=False):
            return {"status":"UNCERTAIN" if conflict else "UNKNOWN","answer":None,
                    "missing_info":[reason],"evidence":[],"p_answerable":None,"p_correct_if_committed":None}
        def committed(answer, evidence):
            # Confidence is not manufactured by averaging model self-reports.
            unique={canonical(c):c for c in evidence}
            return {"status":"INFERRED","answer":answer,"missing_info":[],"evidence":list(unique.values()),
                    "p_answerable":None,"p_correct_if_committed":None}
        result=None;error=None
        try:
            task=validate_task(raw_task)
            move("PROPOSE")
            n={"B0":1,"B1":3,"B2":3,"B3":3,"B4":1,"B5":5}[self.arch]
            for i in range(n):
                pid=f"p{i+1}"
                proposals[pid]=invoke(pid,"proposer",{"task":task},"response")
            if self.arch=="B3":
                move("DEBATE");initial=copy.deepcopy(proposals)
                for pid in initial:
                    proposals[pid]=invoke(pid+'-revision',"debater",{"task":task,"proposals":initial,"self_id":pid},"response")
            if self.arch in {"B2","B4"}:
                move("VERIFY")
                # Validators never see each other's reviews. They still may share model biases.
                roles=["support_checker","challenge_checker"] if self.arch=="B2" else ["support_checker"]
                for role in roles:
                    reviews[role]=invoke(role,role,{"task":task,"proposals":proposals},"review")
            move("AGGREGATE")
            if self.arch=="B0":result=proposals['p1']
            elif self.arch in {"B1","B3","B5"}:
                counts=Counter(p["answer"] for p in proposals.values() if p["status"] in {"KNOWN","INFERRED"})
                winners=[a for a,c in counts.items() if c>n/2]
                result=committed(winners[0],[c for p in proposals.values() if p["answer"]==winners[0] for c in p["evidence"]]) if len(winners)==1 else abstain("no_strict_majority")
            else:
                eligible=[]
                for pid,p in proposals.items():
                    if p["status"] not in {"KNOWN","INFERRED"} or not p["evidence"]:continue
                    if all(v[pid]["support"]=="ENTAILS" for v in reviews.values()):eligible.append(pid)
                answers={proposals[pid]["answer"] for pid in eligible}
                if len(answers)==1:
                    result=committed(next(iter(answers)),[c for pid in eligible for c in proposals[pid]["evidence"]]+
                                     [c for v in reviews.values() for pid in eligible for c in v[pid]["evidence"]])
                else:result=abstain("conflicting_supported_answers" if answers else "no_supported_answer",bool(answers))
            validate_response(result,task);move("DONE")
        except (ProtocolError, ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError) as exc:
            error=type(exc).__name__+":"+str(exc)[:160]
            if state not in {"DONE","ERROR"}:move("ERROR")
            result=None # ERROR is not a successful epistemic abstention.
        return {"protocol":"B2-qa-v0.1","architecture":self.arch,"framing":self.framing,
                "state":state,"result":result,"error":error,"trace":trace,"calls":calls,
                "prompt_hash":fingerprint(self.prompts),"schema_hash":fingerprint(self.schema),
                "task_hash":fingerprint(raw_task),"limits":vars(self.limits),
                "model":{"name":self.provider.name,"revision":self.provider.revision,"fixture":self.provider.is_fixture},
                "cost":{"input_chars":inputs,"output_chars":outputs,"wall_s":time.monotonic()-started},
                "proposals":proposals,"reviews":reviews}
