"""Selected semantic mutation regression. NOT an exhaustive mutation score.

Each mutation has exact source replacements and is executed in a clean temp
copy. Compile/import errors and timeouts are not counted as killed mutants.
The set was selected AFTER reading the review, not a held-out evaluation.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

MUTANTS = [
 ("M01-no-tool-audit", '        self._events.append(row)', '        pass # mutation: omit event'),
 ("M02-no-lock", 'self._lock = threading.Lock()', 'self._lock = __import__("contextlib").nullcontext()'),
 ("M03-no-workflow-scope", 'if r["workflow"] != s.workflow:', 'if False:'),
 ("M04-no-action-scope", 'if r["action"] not in s.actions:', 'if False:'),
 ("M05-no-execution-charge", '            self._executions += 1', '            pass # no execution charge'),
 ("M06-no-attempt-charge", '            self._attempts += 1', '            pass # no attempt charge'),
 ("M07-self-approval", 'if who == principal:', 'if False:'),
 ("M08-one-approver", 'not 2 <= len(signatures) <= len(self._keys)', 'not 1 <= len(signatures) <= len(self._keys)'),
 ("M09-duplicate-approver", 'if who in seen:', 'if False:'),
 ("M10-nonce-not-consumed", 'self._spent.add(approval["payload"]["nonce"])', 'pass # nonce not consumed'),
 ("M11-no-commit-expiry", 'if self.CATALOG[r["action"]] == 3 and now >= approval["payload"]["expiry_ns"]:', 'if False:'),
 ("M12-no-target-version", '"resource_version": self._versions.get(resource, 0)', '"resource_version": 0'),
 ("M13-ignore-halt", 'if self._halted: return self._finish', 'if False: return self._finish'),
 ("M14-ignore-revoke", 'if p["nonce"] in self._revoked:', 'if False:'),
 ("M15-ignore-principal-revoke", 'if principal in self._revoked_principals:', 'if False:'),
 ("M16-unbounded-audit", 'if len(self._events) >= self._audit_limit:', 'if False:'),
 ("M17-audit-no-time", '"mono_ns": now,', '"mono_ns": 0,'),
 ("M18-audit-no-link", '"prev": self._events[-1]["hash"] if self._events else "0" * 64', '"prev": "0" * 64'),
]

def run(out):
    root=Path(__file__).resolve().parent
    source=(root/'gate.py').read_text()
    out.mkdir(parents=True,exist_ok=True)
    def execute_at(directory):
        env=dict(os.environ,PYTHONPATH=str(directory),PYTHONDONTWRITEBYTECODE='1')
        return subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_gate.py','-v'],
                              cwd=directory,env=env,text=True,capture_output=True,timeout=15)
    baseline=execute_at(root)
    (out/'baseline.log').write_text(baseline.stdout+baseline.stderr)
    if baseline.returncode:raise RuntimeError('Unmutated baseline is failing; refusing mutation result')
    records=[]
    for name,old,new in MUTANTS:
        if source.count(old)!=1:raise ValueError(f'{name}: expected exactly one mutation site')
        changed=source.replace(old,new)
        diff=''.join(difflib.unified_diff(source.splitlines(True),changed.splitlines(True),fromfile='gate.py',tofile=name))
        (out/(name+'.diff')).write_text(diff)
        compile(changed,'gate.py','exec')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);(path/'gate.py').write_text(changed)
            shutil.copytree(root/'tests',path/'tests',ignore=shutil.ignore_patterns('__pycache__'))
            try:
                proc=execute_at(path);log=proc.stdout+proc.stderr
                if 'FAILED (failures=' in log and 'ERROR:' not in log:status='killed_assertion'
                elif proc.returncode==0:status='survived'
                else:status='execution_error_not_kill'
                code=proc.returncode
            except subprocess.TimeoutExpired as exc:
                status,log,code='timeout_not_kill',str(exc),None
        (out/(name+'.log')).write_text(log)
        records.append({'id':name,'status':status,'returncode':code,
                        'mutant_sha256':hashlib.sha256(changed.encode()).hexdigest(),
                        'diff_file':name+'.diff','log_file':name+'.log'})
    report={'suite':'18 selected review-driven semantic mutants, not exhaustive mutation score',
            'python':sys.version,'gate_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'records':records,'killed_assertion':sum(x['status']=='killed_assertion' for x in records)}
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'selected':len(records),'killed_assertion':report['killed_assertion'],
                      'other':[x for x in records if x['status']!='killed_assertion']},indent=2))
    return all(x['status']=='killed_assertion' for x in records)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    raise SystemExit(0 if run(p.parse_args().out) else 1)
