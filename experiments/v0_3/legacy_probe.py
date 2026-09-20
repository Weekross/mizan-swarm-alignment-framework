"""Reproduce SIX selected reported gaps, not Claude's unavailable 24 mutations.
Pass the unchanged original reproduction directory using --legacy.
"""
import argparse
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

class RemoveToolAudit(ast.NodeTransformer):
    def visit_Expr(self,node):
        call=node.value
        if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=='append' and call.args:
            d=call.args[0]
            if isinstance(d,ast.Dict):
                for k,v in zip(d.keys,d.values):
                    if isinstance(k,ast.Constant) and k.value=='type' and isinstance(v,ast.Constant) and v.value=='tool_call':
                        return ast.copy_location(ast.Pass(),node)
        return self.generic_visit(node)

def run(legacy,out):
    source=(legacy/'prototype/runtime_gate.py').read_text()
    tests=(legacy/'tests/test_runtime_gate.py').read_text()
    if hashlib.sha256(source.encode()).hexdigest()!='b8518ba98cced47c7ef17c51640d1e2b9fb32e29dcad9d0e76b08bc3a2cf50fb':
        raise ValueError('Not the frozen original gate')
    out.mkdir(parents=True,exist_ok=True)
    mutations=[('L01-no-tool-audit',ast.unparse(RemoveToolAudit().visit(ast.parse(source)))+'\n')]
    for name,a,b in [
      ('L02-no-lock','self._lock = threading.Lock()','self._lock = __import__("contextlib").nullcontext()'),
      ('L03-no-workflow','and request["workflow"] == s.workflow',''),
      ('L04-no-action-scope','and request["action"] in s.actions',''),
      ('L05-no-execution-budget-charge','self._budget = max(0, self._budget - 1)','pass'),
      ('L06-no-approver-check','p["approver"] != "operator" or ','')]:
        if source.count(a)!=1:raise ValueError(name+' unexpected source')
        mutations.append((name,source.replace(a,b)))
    records=[]
    for name,content in [('baseline',source)]+mutations:
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'runtime_gate.py').write_text(content);(p/'test_runtime_gate.py').write_text(tests)
            r=subprocess.run([sys.executable,'-m','unittest','test_runtime_gate','-v'],cwd=p,
                              capture_output=True,text=True,timeout=15,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        status='passes' if r.returncode==0 else 'fails'
        records.append({'id':name,'status':status,'returncode':r.returncode})
        (out/(name+'.log')).write_text(r.stdout+r.stderr)
        if name!='baseline':
            (out/(name+'.diff')).write_text(''.join(difflib.unified_diff(source.splitlines(True),content.splitlines(True))))
    (out/'results.json').write_text(json.dumps({'scope':'Six selected gap probes, not replication of all 24 Claude mutants',
        'legacy_sha256':hashlib.sha256(source.encode()).hexdigest(),'python':sys.version,'records':records},indent=2)+'\n')
    print(json.dumps(records,indent=2))
    return records[0]['status']=='passes'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();raise SystemExit(0 if run(a.legacy,a.out) else 1)
