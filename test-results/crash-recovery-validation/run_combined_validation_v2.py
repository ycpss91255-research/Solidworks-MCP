"""Validate the combined isolated checkout; unittest only, never native CAD harnesses."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, re, subprocess, sys, time
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
BASE='5266061e1ac739b0ed1149b1e58c36284eb3fcd7'
def git(*args):
    return subprocess.run(['git',*args],cwd=ROOT,capture_output=True,text=True)
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()
def sources():
    names=git('ls-files').stdout.splitlines()
    return {name:digest(ROOT/name) for name in names if (name.endswith('.py') and not name.startswith('test-results/')) or name in ('docs/CLOSE_DOC_TRACE_TDD.md','docs/RECOVERY_STARTUP_FENCE_TDD.md')}
def main():
    report_path=OUT/'combined-green-v2.json';console_path=OUT/'combined-green-v2-console.txt'
    if report_path.exists() or console_path.exists():raise RuntimeError('Fresh result paths required')
    before=sources();status_before=git('status','--porcelain=v1').stdout;head=git('rev-parse','HEAD').stdout.strip();branch=git('branch','--show-current').stdout.strip()
    assert status_before == ' M tests/test_recovery_startup_windows.py\n' and branch=='codex/crash-recovery-validation'
    started=utc();clock=time.perf_counter()
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8')
    run=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-v'],cwd=ROOT,env=env,capture_output=True,encoding='utf8')
    console=run.stdout+run.stderr;console_path.write_text(console,encoding='utf8')
    result=re.search(r'Ran (\d+) tests in ([0-9.]+)s',console)
    diff=git('diff','--check',BASE);status_after=git('status','--porcelain=v1').stdout
    links=[]
    for rel in ('docs/CLOSE_DOC_TRACE_TDD.md','docs/RECOVERY_STARTUP_FENCE_TDD.md'):
        path=ROOT/rel
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf8')):
            if '://' in target or target.startswith('#'):continue
            resolved=(path.parent/target.split('#',1)[0]).resolve()
            links.append({'document':rel,'target':target,'exists':resolved.exists()})
    after=sources()
    first=json.loads((OUT/'combined-green-v1.json').read_text())
    production_unchanged=all(after.get(k)==v for k,v in first['source_sha256_after'].items() if not k.startswith('tests/'))
    report={'started_utc':started,'completed_utc':utc(),'branch':branch,'head':head,'base':BASE,
        'close_doc_commit':'11d63b2fd0f509fb1e08961394a98dc8cd5d13bc','recovery_original_commit':'b64a82b2dad927fd2a98a820dadb37f46261ad14',
        'command':[sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-v'],
        'test_count':int(result.group(1)) if result else None,'test_seconds':float(result.group(2)) if result else None,'wall_seconds':round(time.perf_counter()-clock,3),
        'returncode':run.returncode,'console_sha256':digest(console_path),'source_sha256_before':before,'source_sha256_after':after,'source_unchanged':before==after,'production_unchanged_from_first_mixed_run':production_unchanged,
        'status_before':status_before,'status_after':status_after,'diff_check_returncode':diff.returncode,'diff_check_output':diff.stdout+diff.stderr,
        'only_uncommitted_change':'tests/test_recovery_startup_windows.py', 'preserved_first_mixed_result':'combined-green-v1.json', 'doc_links':links,'actual_cad_calls':0,'native_CAD_harnesses_run':False,'live_or_FIX_modified':False,'deployed':False,'pushed':False}
    report['passed']=run.returncode==0 and result is not None and production_unchanged and before==after and status_after==status_before and diff.returncode==0 and all(row['exists'] for row in links)
    report_path.write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({k:report[k] for k in ('passed','head','test_count','test_seconds','wall_seconds','returncode','source_unchanged','diff_check_returncode','status_after')}))
    print(json.dumps({'report':str(report_path),'source_files':len(before),'doc_links':len(links),'bad_links':[r for r in links if not r['exists']]}))
    return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
