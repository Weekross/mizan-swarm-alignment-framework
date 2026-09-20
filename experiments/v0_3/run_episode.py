"""Run one fixed protocol episode with scripted outputs or a trusted adapter.

Example: python run_episode.py --task task.json --fixture outputs.json --out run.json
No provider API credentials are requested or managed by this program.
"""
import argparse
import json
from pathlib import Path
from orchestrator import Engine,FixtureProvider,CommandProvider,ARCHITECTURES,FRAMINGS,strict_json

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--task',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--architecture',choices=ARCHITECTURES,default='B2')
    p.add_argument('--framing',choices=FRAMINGS,default='neutral')
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--fixture',type=Path);group.add_argument('--command-json',type=Path)
    p.add_argument('--provider-name');p.add_argument('--provider-revision')
    a=p.parse_args()
    if a.fixture:provider=FixtureProvider(strict_json(a.fixture.read_text()))
    else:
        if not a.provider_name or not a.provider_revision:p.error('Explicit provider identity/revision required')
        provider=CommandProvider(strict_json(a.command_json.read_text()),name=a.provider_name,revision=a.provider_revision)
    result=Engine(provider,a.architecture,a.framing).run(strict_json(a.task.read_text()))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    raise SystemExit(0 if result['state']=='DONE' else 1)
