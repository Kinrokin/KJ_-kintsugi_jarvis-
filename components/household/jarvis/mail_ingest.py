"""Read-only, account-bound Gmail/Graph metadata ingestion.
No messages are sent, marked read, deleted, accepted or turned into authority.
Scope is explicit. An incomplete cycle never advances a committed cursor.
"""
from __future__ import annotations
import re, urllib.parse
from datetime import timedelta
from .common import *
from .transport import HTTPS, TransportFailure

class CursorExpired(Refused):pass

def ident(value):return urllib.parse.quote(text(value,'provider identifier',1000),safe='')
def clipped(value,n=500):
    if not isinstance(value,str):raise Refused('Provider text type changed')
    return ''.join(c for c in value if c.isprintable() or c=='\t')[:n]

def require(status,body):
    if status!=200:raise TransportFailure('PROVIDER_HTTP_'+str(status))
    if not isinstance(body,dict):raise Refused('Provider shape changed')
    return body

class GmailMetadata:
    provider='gmail_metadata_v1'
    def __init__(self,http,token,account,label,lookback_days=14,max_pages=20):
        self.http=http;self.token=token;self.account=text(account).casefold();self.label=text(label)
        self.days=integer(lookback_days,'lookback',1,365);self.max_pages=integer(max_pages,'pages',1,100)
    def get(self,path):return self.http.request('GET','https://gmail.googleapis.com/gmail/v1/users/me/'+path,token=self.token)
    def identity(self):
        p=require(*self.get('profile'))
        if str(p.get('emailAddress','')).casefold()!=self.account:raise Refused('MAIL_ACCOUNT_MISMATCH')
        return p
    def collect(self,cursor,now):
        profile=self.identity(); floor=iso(now-timedelta(days=self.days)); ids=set();removed=set();page=None;seen=set()
        old=strict_json(cursor) if cursor else None
        if old:
            keys(old,{'history_id','floor'}); floor=old['floor']; instant(floor)
            if not isinstance(old['history_id'],str) or not old['history_id'].isdigit():raise Refused('Invalid saved history cursor')
        anchor=str(profile.get('historyId',''))
        if not anchor.isdigit():raise Refused('History identity missing')
        for _ in range(self.max_pages):
            q={'maxResults':100}
            if page:q['pageToken']=page
            if old:
                q['startHistoryId']=old['history_id'];path='history?'+urllib.parse.urlencode(q)
                status,body=self.get(path)
                if status==404:raise CursorExpired('GMAIL_HISTORY_EXPIRED_FULL_RESYNC_REQUIRED')
                body=require(status,body)
                for h in body.get('history',[]):
                    for group in ('messagesAdded','labelsAdded','labelsRemoved'):
                        for entry in h.get(group,[]):ids.add(text(entry['message']['id']))
                    for entry in h.get('messagesDeleted',[]):removed.add(text(entry['message']['id']))
                last=str(body.get('historyId',''))
                if not last.isdigit():raise Refused('Final history cursor missing')
                if int(last)<int(old['history_id']):raise Refused('History cursor moved backwards')
            else:
                q.update(labelIds=self.label,q='after:'+str(int(instant(floor).timestamp())))
                body=require(*self.get('messages?'+urllib.parse.urlencode(q)))
                for msg in body.get('messages',[]):ids.add(text(msg['id']))
                last=anchor  # captured BEFORE listing; later deltas close the race.
            page=body.get('nextPageToken')
            if not page:break
            if page in seen:raise Refused('PAGINATION_LOOP')
            seen.add(page)
        else:raise Refused('PAGE_LIMIT_INCOMPLETE_SCOPE')
        items=[{'id':x,'removed':True} for x in sorted(removed)]
        for mid in sorted(ids-removed):
            q=urllib.parse.urlencode([('format','metadata'),('metadataHeaders','Subject'),('metadataHeaders','From')])
            status,body=self.get('messages/'+ident(mid)+'?'+q)
            if status==404:items.append({'id':mid,'removed':True});continue
            body=require(status,body)
            if body.get('id')!=mid:raise Refused('MESSAGE_ID_MISMATCH')
            received=datetime.fromtimestamp(int(body['internalDate'])/1000,UTC)
            if self.label not in body.get('labelIds',[]) or received<instant(floor):
                items.append({'id':mid,'removed':True});continue
            headers={h['name'].casefold():h['value'] for h in body.get('payload',{}).get('headers',[])}
            items.append({'id':mid,'subject':clipped(headers.get('subject','(no subject)')),
                          'sender':clipped(headers.get('from','(unknown sender)')),
                          'received_at':iso(received),'body_downloaded':False,'attachments_downloaded':False})
        self.identity()  # Same token and account must still be valid at commit.
        return items,canonical({'history_id':last,'floor':floor})

class OutlookMetadata:
    provider='graph_metadata_v1'
    def __init__(self,http,token,account,folder='inbox',max_pages=20):
        self.http=http;self.token=token;self.account=text(account);self.folder=text(folder);self.selector=self.folder
        self.max_pages=integer(max_pages,'pages',1,100)
        self.base='https://graph.microsoft.com/v1.0/me/mailFolders/'+ident(folder)+'/messages/delta'
    def identity(self):
        b=require(*self.http.request('GET','https://graph.microsoft.com/v1.0/me?$select=id',token=self.token))
        if b.get('id')!=self.account:raise Refused('MAIL_ACCOUNT_MISMATCH')
    def resolve_folder(self):
        # A provider may canonicalize the 'inbox' alias to an opaque, case-sensitive ID.
        status,b=self.http.request('GET','https://graph.microsoft.com/v1.0/me/mailFolders/'+ident(self.selector)+'?$select=id',token=self.token,headers={'Prefer':'IdType="ImmutableId"'})
        b=require(status,b);self.folder=text(b.get('id'),'verified folder id')
        self.base='https://graph.microsoft.com/v1.0/me/mailFolders/'+ident(self.folder)+'/messages/delta'
    def safe_link(self,url):
        u=urllib.parse.urlsplit(url)
        if u.scheme!='https' or u.hostname!='graph.microsoft.com' or u.port not in (None,443) or u.username or u.password or u.fragment:
            raise Refused('DELTA_DESTINATION_REFUSED')
        path=urllib.parse.unquote(u.path)
        # Graph documents both slash and OData-parenthesized folder identifiers.
        allowed={'/v1.0/me/mailfolders/'+self.folder+'/messages/delta',
                 "/v1.0/me/mailfolders('"+self.folder+"')/messages/delta"}
        # Structural spelling is normalized, but opaque provider IDs are case-sensitive.
        if path.replace('/mailFolders','/mailfolders') not in allowed:raise Refused('DELTA_SCOPE_REFUSED')
        return url
    def collect(self,cursor,now):
        self.identity();self.resolve_folder();items=[];seen=set()
        url=self.safe_link(cursor) if cursor else self.base+'?'+urllib.parse.urlencode({'$select':'id,subject,from,receivedDateTime,isRead','$top':100})
        for _ in range(self.max_pages):
            if url in seen:raise Refused('PAGINATION_LOOP')
            seen.add(url)
            status,b=self.http.request('GET',self.safe_link(url),token=self.token,headers={'Prefer':'IdType="ImmutableId"'})
            if status in (404,410):raise CursorExpired('GRAPH_CURSOR_EXPIRED_FULL_RESYNC_REQUIRED')
            b=require(status,b)
            if not isinstance(b.get('value'),list):raise Refused('Delta shape changed')
            for m in b['value']:
                mid=text(m['id'],'message id')
                if '@removed' in m:items.append({'id':mid,'removed':True});continue
                instant(m['receivedDateTime'])
                items.append({'id':mid,'subject':clipped(m.get('subject','(no subject)')),
                              'sender':clipped(m.get('from',{}).get('emailAddress',{}).get('address','(unknown sender)')),
                              'received_at':m['receivedDateTime'],'body_downloaded':False,'attachments_downloaded':False})
            nextlink=b.get('@odata.nextLink');delta=b.get('@odata.deltaLink')
            if nextlink and delta:raise Refused('Ambiguous delta progression')
            if nextlink:url=self.safe_link(nextlink);continue
            if not delta:raise Refused('Final delta link missing')
            self.identity();return items,self.safe_link(delta)
        raise Refused('PAGE_LIMIT_INCOMPLETE_SCOPE')

def poll_source(store,cfg,token,http=None,now=None):
    now=now or now_utc();name=cfg['id']
    binding={'provider':cfg['provider'],'account':cfg['account'],'credential_ref':cfg['credential_ref']}
    scope={'selector':cfg['selector'],'lookback_days':cfg.get('lookback_days',14) if cfg['provider']=='gmail' else None,
           'metadata_only':True,'interpretation':'No assurance all household obligations are represented'}
    store.begin_source(name,binding,scope,now);old=store.source(name)
    http=http or HTTPS({'gmail.googleapis.com','graph.microsoft.com'})
    try:
        if cfg['provider']=='gmail':adapter=GmailMetadata(http,token,cfg['account'],cfg['selector'],cfg.get('lookback_days',14),cfg.get('max_pages',20))
        elif cfg['provider']=='outlook':adapter=OutlookMetadata(http,token,cfg['account'],cfg['selector'],cfg.get('max_pages',20))
        else:raise Refused('Provider not supported')
        items,cursor=adapter.collect(old['cursor'],now)
        store.commit_source(name,items,cursor,now,full=old['cursor'] is None)
        return {'id':name,'status':'COMPLETE','item_count':len(items),'scope':scope}
    except Exception as e:
        code=e.code if isinstance(e,TransportFailure) else 'RESYNC_REQUIRED' if isinstance(e,CursorExpired) else 'SYNC_FAILED'
        store.fail_source(name,code,now)
        return {'id':name,'status':'DEGRADED','error_code':code,'cursor_advanced':False}
