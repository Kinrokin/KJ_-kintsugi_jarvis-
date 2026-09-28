"""Small deterministic helpers; no background execution or provider access."""
from __future__ import annotations
import json, statistics, uuid
from datetime import timedelta
from pathlib import Path
from .common import *

class SyncCoverage:
    def __init__(self):self.committed={};self.staging={};self.status={}
    def begin(self,source):self.staging[source]=[];self.status[source]='SYNCING'
    def page(self,source,items,*,next_page=None,next_cursor=None):
        if source not in self.staging:raise Refused('Start a synchronization first')
        if not isinstance(items,list):raise Refused('Invalid page')
        self.staging[source].extend(items)
        if next_page is not None:
            if next_cursor is not None:raise Refused('Cursor cannot be committed before the last page')
            return
        if next_cursor is None:raise Refused('Final page needs cursor')
        self.committed[source]={'cursor':next_cursor,'items':self.staging.pop(source)};self.status[source]='COMPLETE'
    def fail(self,source):self.staging.pop(source,None);self.status[source]='DEGRADED'

def coverage_report(required,records,now=None,max_age_seconds=3600):
    now=now or now_utc();result={}
    for name in required:
        r=records.get(name,{})
        try:age=(now-instant(r['as_of'])).total_seconds()
        except (KeyError,ValueError,TypeError):age=None
        valid=r.get('status')=='COMPLETE' and r.get('policy_verified') is True and age is not None and 0<=age<=max_age_seconds
        result[name]={'covered':valid,'status':r.get('status','UNKNOWN'),'age_seconds':age}
    complete=bool(required) and all(v['covered'] for v in result.values())
    return {'coverage':'COMPLETE' if complete else 'DEGRADED','all_clear_eligible':complete,'sources':result,
            'note':'Coverage alone does not establish absence of obligations. Self-monitored unless an independent observer is deployed.'}

def read_policy_fixture(path,expected_sha256):
    p=Path(path)
    if p.is_symlink() or not p.is_file():raise Refused('Policy source unavailable')
    blob=p.read_bytes()
    if len(blob)>100000:raise Refused('Policy fixture too large')
    h=hashlib.sha256(blob).hexdigest()
    if h!=expected_sha256:raise Refused('Policy version/digest mismatch')
    d=strict_json(blob.decode());keys(d,{'version','challenge','minimum_policy'})
    return {'status':'READ_FROM_BYTES','version':d['version'],'challenge':d['challenge'],'sha256':h}

def dependency_risks(obligations,arrangements):
    out=[]
    for o in obligations:
        for need in o.get('requires',[]):
            r=arrangements.get((o['id'],need))
            if not r or r.get('status')!='accepted':
                out.append({'obligation_id':o['id'],'observed':'No accepted '+need+' record in supplied sources',
                            'inferred_risk':'This dependency may be unresolved','unknown':'It may be arranged outside available records'})
    return out

def plan_flexible(tasks,now,until,mode='normal'):
    """Greedy bounded preview; immutable fixed commitments. Not a provider rescheduler."""
    if mode not in {'normal','minimum'}:raise Refused('Invalid day mode')
    fixed=sorted([t for t in tasks if t['fixed']],key=lambda t:instant(t['start']))
    result={'fixed':fixed,'proposed':[],'unplaced':[]};cursor=now
    for t in [t for t in tasks if not t['fixed']]:
        mins=t.get('minimum_minutes',t['minutes']) if mode=='minimum' else t['minutes'];integer(mins,'duration',1,1440)
        if t.get('clinical'):result['unplaced'].append({'id':t['id'],'reason':'Clinical instructions are outside this planner'});continue
        end=cursor+timedelta(minutes=mins)
        for f in fixed:
            a,b=instant(f['start']),instant(f['end'])
            if cursor<b and end>a:cursor=b;end=cursor+timedelta(minutes=mins)
        deadline=instant(t['deadline']) if t.get('deadline') else until
        if end>min(until,deadline):result['unplaced'].append({'id':t['id'],'reason':'No slot without changing a fixed commitment'})
        else:result['proposed'].append({'id':t['id'],'start':iso(cursor),'end':iso(end)});cursor=end
    return result

def opportunity_screen(facts):
    checks=['identity_verified','official_program_verified','eligibility_evidence','no_upfront_fee','purpose_limited_data','worth_review']
    missing=[k for k in checks if facts.get(k) is not True]
    return {'status':'REVIEW_CANDIDATE' if not missing else 'HOLD_UNVERIFIED','missing':missing,'apply_automatically':False}

def value_report(rows):
    totals={};reviews=[];maintenance=[]
    for r in rows:
        integer(r['value'],'value',0);totals[r['kind']]=totals.get(r['kind'],0)+r['value']
        if r['kind']=='review_seconds':reviews.append(r['value'])
        if r['kind']=='maintenance_seconds':maintenance.append(r['value'])
    return {'totals':totals,'review_sample_median_seconds':statistics.median(reviews) if reviews else None,
            'maintenance_total_seconds':sum(maintenance),'net_recorded_savings_cents':totals.get('verified_savings_cents',0)-totals.get('operating_cost_cents',0),
            'basis':'User-recorded samples, not verified ROI or a measured full-week outcome'}

class Budget:
    """Per-run deterministic allowance. No paid integration is enabled by this class."""
    def __init__(self,max_calls=0,max_cents=0):self.max_calls=integer(max_calls,minimum=0);self.max_cents=integer(max_cents,minimum=0);self.calls=0;self.cents=0
    def reserve(self,cents):
        integer(cents,minimum=0)
        if self.calls+1>self.max_calls or self.cents+cents>self.max_cents:raise Refused('Run budget exceeded')
        self.calls+=1;self.cents+=cents
