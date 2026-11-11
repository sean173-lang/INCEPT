"""Read-only staged/history secret check. Reports paths/counts, never matched values."""
import json,re,subprocess
from pathlib import Path
from dotenv import dotenv_values


def git(*args):return subprocess.check_output(['git',*args])

def audit():
    secrets=[v for k,v in dotenv_values('.env').items() if v and len(v)>=12 and any(x in k.upper() for x in ('KEY','SECRET','TOKEN','PASSWORD'))]
    patterns=[r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'ya29\.[A-Za-z0-9_-]{20,}',r'sk-(?:proj-)?[A-Za-z0-9_-]{32,}',r'GOCSPX-[A-Za-z0-9_-]{20,}']
    def secret(raw):
        s=raw.decode('utf8',errors='replace')
        return any(v in s for v in secrets) or any(re.search(p,s) for p in patterns)
    paths=[p for p in git('diff','--cached','--diff-filter=ACMRT','--name-only','-z').decode().split('\0') if p]
    findings=[]
    for path in paths:
        raw=git('show',':'+path);s=raw.decode('utf8',errors='replace')
        if secret(raw):findings.append((path,'secret match'))
        if path.startswith(('data/','reports/','backups/','private_backups/')) or (Path(path).name.startswith('.env') and path!='.env.example') or Path(path).suffix in ('.db','.sqlite','.sqlite3','.log'):findings.append((path,'private runtime file'))
        if ('/'+'Users/') in s:findings.append((path,'machine-specific personal path'))
        if len(raw)>2_000_000:findings.append((path,'oversized artifact'))
        if path.startswith('workflows/') and path.endswith('.json'):
            w=json.loads(s)
            for n in w['nodes']:
                if n.get('credentials') or n.get('webhookId'):findings.append((path,'unsanitized workflow binding'))
        if re.search(r'[?&](?:X-Amz-Signature|access_token)=',s,re.I):findings.append((path,'signed/token URL'))
    history=[];blobs=0
    for row in git('rev-list','--objects','--all').decode().splitlines():
        oid=row.split()[0]
        if git('cat-file','-t',oid).strip()==b'blob':
            blobs+=1
            if secret(git('cat-file','blob',oid)):history.append(oid)
    result={'staged_files':len(paths),'staged_findings':findings,'history_blobs_checked':blobs,'history_secret_findings':len(history),'limitations':['Pattern/exact-value scan cannot prove absence of every unknown secret.','No signed-URL exceptions are allowlisted.']}
    print(json.dumps(result,indent=2));return not findings and not history

if __name__=='__main__':raise SystemExit(0 if audit() else 1)
