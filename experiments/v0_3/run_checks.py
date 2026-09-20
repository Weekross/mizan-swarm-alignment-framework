"""Reproducible local/CI checks; all data and providers here are synthetic."""
import argparse
from datetime import datetime,timezone
import hashlib
from io import StringIO
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest
import os
import mutations
from orchestrator import Engine, FixtureProvider, ARCHITECTURES, FRAMINGS

ROOT=Path(__file__).resolve().parent
class Recorded(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.records=[];self.start={}
    def startTest(self,test):self.start[test.id()]=time.monotonic();super().startTest(test)
    def addSuccess(self,test):
        super().addSuccess(test);self.records.append({'id':test.id(),'status':'passed','seconds':time.monotonic()-self.start[test.id()]})
    def addFailure(self,test,err):
        super().addFailure(test,err);self.records.append({'id':test.id(),'status':'failed','detail':self._exc_info_to_string(err,test)})
    def addError(self,test,err):
        super().addError(test,err);self.records.append({'id':test.id(),'status':'error','detail':self._exc_info_to_string(err,test)})
    def addSubTest(self,test,subtest,err):
        super().addSubTest(test,subtest,err)
        if err:self.records.append({'id':str(subtest),'status':'subtest_failure','detail':self._exc_info_to_string(err,test)})

def main(out,legacy):
    out.mkdir(parents=True,exist_ok=True)
    stream=StringIO();suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Recorded).run(suite)
    (out/'unit-tests.log').write_text(stream.getvalue());print(stream.getvalue(),end='')
    try:revision=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:revision=None
    report={'utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),
            'revision':revision,'tests':r.testsRun,'successful':r.wasSuccessful() and r.testsRun>0,'per_test':r.records,
            'llm_calls':0,'human_review_completed':False,
            'code_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(ROOT.rglob('*')) if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in str(p)},
            'scope':'Synthetic unit/protocol checks only; not independent security trials or completed evals'}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['successful']:return False
    # Exercise the 18 treatments. Scripted providers ignore prompts: no N/Q effect measured.
    sys.path.insert(0,str(ROOT/'tests'))
    from test_orchestrator import TASK, fixture
    n={'B0':1,'B1':3,'B2':3,'B3':3,'B4':1,'B5':5}
    transcripts=[]
    for a in ARCHITECTURES:
        for framing in FRAMINGS:
            transcripts.append(Engine(FixtureProvider(fixture(('Y',)*n[a])),a,framing).run(TASK))
    (out/'scripted-18-cells.json').write_text(json.dumps(transcripts,indent=2)+'\n')
    if any(x['state']!='DONE' for x in transcripts):return False
    # Repeat one explicitly scheduled concurrency case. Repeats are not IID trials.
    repeated=[]
    for i in range(10):
        t=unittest.defaultTestLoader.loadTestsFromName('test_gate.GateTests.test_two_threads_replay_atomic_mock_effect')
        s=StringIO();result=unittest.TextTestRunner(stream=s,verbosity=2).run(t)
        repeated.append({'repeat':i,'success':result.wasSuccessful(),'log':s.getvalue()})
    (out/'concurrency-repeats.json').write_text(json.dumps(repeated,indent=2)+'\n')
    mutation_ok=mutations.run(out/'mutations')
    if legacy:
        from legacy_probe import run
        if not run(legacy,out/'legacy-probes'):return False
    return mutation_ok and all(x['success'] for x in repeated)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--legacy',type=Path)
    a=p.parse_args();raise SystemExit(0 if main(a.out,a.legacy) else 1)
