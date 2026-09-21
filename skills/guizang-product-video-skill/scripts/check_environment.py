#!/usr/bin/env python3
"""Local dependency preflight. Installs nothing; the agent follows onboarding only for reported gaps."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys


def run(args, cwd=None, timeout=30):
    try:
        p=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=timeout)
        return {'ok':p.returncode==0,'stdout':p.stdout.strip(),'stderr':p.stderr.strip(),'output':(p.stdout+p.stderr).strip()}
    except (OSError,subprocess.TimeoutExpired) as e:return {'ok':False,'output':str(e)}


def dotenv_keys(project):
    """Non-empty KEY=value pairs from <project>/.env. Callers must not print values."""
    values={}
    try:lines=(project/'.env').read_text().splitlines()
    except OSError:return values
    for line in lines:
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        name,_,value=line.partition('=')
        values[name.strip()]=value.strip().strip('"').strip("'")
    return values


def hyperframes_failures(payload):
    checks=payload.get('checks')
    if not isinstance(checks,list):return ['Invalid doctor checks'],[]
    optional_names={'whisper-cpp','TTS (Kokoro)','BGM (MusicGen)','Docker','Docker running'}
    required_names={'Node.js','FFmpeg','FFprobe','Chrome'}
    names={row.get('name') for row in checks if isinstance(row,dict)}
    failed=['Missing doctor check: '+name for name in sorted(required_names-names)]
    optional=[]
    for row in checks:
        if not isinstance(row,dict):continue
        if row.get('ok'):continue
        message=str(row.get('name'))+': '+str(row.get('detail',''))
        if row.get('name') in optional_names:optional.append(message)
        else:failed.append(message)
    return failed,optional


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True)
    p.add_argument('--engine',choices=['browser','hyperframes'],default='browser')
    p.add_argument('--force',action='store_true',help='Refresh cached engine checks; browser launch is always verified')
    p.add_argument('--voiceover',choices=['yes','no','undecided'],default='no',help='Narration decision from step 1. "yes" makes EASYROUTER_API_KEY a reported prerequisite; "no" stays silent; "undecided" warns. Never guessed from plan.json: at this point the plan is still the starter sample and its voiceoverRequired is stale.')
    a=p.parse_args();project=a.project.expanduser().resolve();missing=[];versions={};warnings=[]
    if not project.is_dir():p.error('Initialize/select an isolated video project first')
    versions['python']={'path':sys.executable,'version':platform.python_version()}
    if sys.version_info<(3,9):missing.append('python>=3.9')
    paths={}
    for name in ['node','npm','ffmpeg','ffprobe']:
        path=shutil.which(name);paths[name]=path
        if not path:missing.append(name);continue
        v=run([path,'-version' if name.startswith('ff') else '--version'])
        versions[name]={'path':path,'version':v['output'].splitlines()[0] if v['output'] else ''}
        if not v['ok']:missing.append(name+':unusable')
    if paths['node']:
        match=re.search(r'v?(\d+)\.',versions.get('node',{}).get('version',''))
        if not match or int(match.group(1))<22:missing.append('node>=22')
    ff=paths['ffmpeg']
    if ff:
        filters=run([ff,'-hide_banner','-filters'])['output'];enc=run([ff,'-hide_banner','-encoders'])['output']
        for name in ['volume','adelay','amix','loudnorm','afade','aresample','asetnsamples']:
            if not re.search(r'\b'+name+r'\b',filters):missing.append('ffmpeg-filter:'+name)
        for name in ['libx264','aac']:
            if not re.search(r'\b'+name+r'\b',enc):missing.append('ffmpeg-encoder:'+name)
    # Narration is the one prerequisite that depends on a step-1 answer rather than on
    # the machine, so it is reported separately from engine gaps: a missing key must not
    # read as "your toolchain is broken", and it must not skip the browser launch below.
    prereqs=[];voiceover={'requested':a.voiceover=='yes','keyResolved':False,'keySource':None}
    if a.voiceover!='no':
        if os.environ.get('EASYROUTER_API_KEY','').strip():voiceover.update({'keyResolved':True,'keySource':'environment'})
        elif dotenv_keys(project).get('EASYROUTER_API_KEY',''):voiceover.update({'keyResolved':True,'keySource':'.env'})
        if a.voiceover=='yes' and not voiceover['keyResolved']:
            prereqs.append('easyrouter-api-key')
            warnings.append('Narration was chosen but EASYROUTER_API_KEY is not set as an environment variable or in <project>/.env. Ask the user for it now: applying for the key takes them time, and it blocks mixing rather than rendering, so discovering it late wastes a whole build.')
        elif a.voiceover=='undecided':
            warnings.append('Narration is still undecided. If the user later says yes, EASYROUTER_API_KEY becomes a blocking prerequisite for the mixing step, so ask for it at that moment.')
    package_files={}
    for file in ['package.json','package-lock.json','pnpm-lock.yaml','yarn.lock','bun.lock']:
        path=project/file
        if path.is_file():package_files[file]=hashlib.sha256(path.read_bytes()).hexdigest()
    browser=None;modules={};hf=None
    if paths['node']:
        names=['playwright','esbuild','react','react-dom'] if a.engine=='browser' else ['hyperframes']
        js='''const names=JSON.parse(process.argv[1]);const fs=require('fs');const result={};
for(const name of names){try {const file=require.resolve(name+'/package.json');const pkg=JSON.parse(fs.readFileSync(file));result[name]={version:pkg.version,path:file};if(name==='hyperframes'){const path=require('path');const bin=typeof pkg.bin==='string'?pkg.bin:pkg.bin.hyperframes;result[name].cli=path.resolve(path.dirname(file),bin);}}catch(e){result[name]={missing:true,error:e.message};}}
console.log(JSON.stringify(result));'''
        result=run([paths['node'],'-e',js,json.dumps(names)],project)
        if result['ok']:
            modules=json.loads(result['stdout']);hf=modules.get('hyperframes')
            for name in names:
                if name not in modules or modules[name].get('missing'):missing.append('package:'+name)
        else:missing.append('node-package-resolution');warnings.append(result['output'][:800])
    details={'schema':2,'engine':a.engine,'voiceover':voiceover,'platform':platform.platform(),'versions':versions,'packages':modules,'manifests':package_files,'browserEnv':{k:os.environ.get(k) for k in ['PLAYWRIGHT_BROWSERS_PATH','HYPERFRAMES_CHROME_PATH']}}
    fingerprint=hashlib.sha256(json.dumps(details,sort_keys=True).encode()).hexdigest()
    state=project/'evidence/environment.json';old={}
    try:old=json.loads(state.read_text())
    except (OSError,ValueError):pass
    cached=not missing and not prereqs and old.get('ready') and old.get('fingerprint')==fingerprint and not a.force
    # Launch is the availability check: headless-shell can exist without full Chromium.
    # Always recheck browser execution, even when package metadata is cached.
    if not missing and (a.engine=='browser' or not cached):
        if a.engine=='browser':
            result=run([paths['node'],'-e',"const {chromium}=require('playwright');(async()=>{const b=await chromium.launch({headless:true});const p=await b.newPage();await p.setContent('<p>ready</p>');if(await p.textContent('p')!=='ready')throw Error('DOM failed');await b.close();})().catch(e=>{console.error(e.message);process.exit(1)});"],project)
            browser={'launched':result['ok'],'playwrightVersion':modules['playwright']['version']}
            if not result['ok']:
                cached=False
                missing.append('browser-launch');warnings.append(result['output'][:1200])
        else:
            # Invoke the resolved local CLI: no npx package fetching on the ready path.
            result=run([paths['node'],hf['cli'],'doctor','--json'],project,60)
            try:
                payload=json.loads(result.get('stdout',result['output']))
                failed,optional=hyperframes_failures(payload)
                if failed:missing.append('hyperframes-doctor');warnings.extend(failed)
                if optional:warnings.append('Optional capabilities not needed for local rendering: '+', '.join(item.split(':')[0] for item in optional))
            except ValueError:missing.append('hyperframes-doctor');warnings.append(result['output'][:1600])
    ready=not missing and not prereqs
    # Report every gap, not just the first kind: a missing key and a missing package are
    # fixed by different people and neither should hide the other.
    if ready:next_step='Continue; do not load onboarding.'
    else:
        steps=[]
        if missing:steps.append('Read references/onboarding.md for only the reported engine/platform gaps, install them.')
        if prereqs:steps.append('Ask the user for the reported prereqs; a credential cannot be installed by you.')
        next_step=' '.join(steps)+' Then rerun with --force.'
    report={'ready':ready,'cached':bool(cached),'engine':a.engine,'missing':missing,'prereqs':prereqs,'warnings':warnings,'voiceover':voiceover,'fingerprint':fingerprint,'details':details,'browser':browser,
            'next':next_step}
    state.parent.mkdir(exist_ok=True);state.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='details'},ensure_ascii=False,indent=2))
    sys.exit(0 if ready else 1)
if __name__=='__main__':main()
