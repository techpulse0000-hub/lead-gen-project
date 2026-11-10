"""Persisted, bounded research runs; one background worker per local dashboard."""
import json
import threading
from pathlib import Path

from .crawler import Crawler, add_source, canonical
from .profile import load_profile
from .store import Store, now
from . import discovery
from . import llm_classifier
from . import apify_enrichment, contractor_verification, contact_enrichment
from .query_bank import TRADES, selected_plan

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ('queued', 'running', 'stopping')


def source_options(store):
    catalog = json.loads((ROOT/'data/monitor_sources.json').read_text(encoding='utf-8'))
    return [dict(source,key='monitor:'+source['id']) for source in catalog['sources']]


class ResearchController:
    def __init__(self, db_path, transport=None, delay=2, search_transport=None):
        self.db_path, self.transport, self.delay = db_path, transport, delay
        self.threads = []
        self.connection=discovery.SearchConnection()
        self.search_transport=search_transport or discovery.request_search
        self.classifier_connection=llm_classifier.LLMConnection()
        self.classifier_transport=llm_classifier.request_openai
        self.apify_connection=apify_enrichment.ApifyConnection()
        self.apify_transport=apify_enrichment.request_apify

    def start_discovery(self, data, launch=True):
        if not self.connection.key():
            raise ValueError('Connect Tavily in Search connection first. No searches were sent.')
        trade=data.get('trade',['construction'])[0]
        location=data.get('location',['Dallas Fort Worth Texas'])[0]
        signal=data.get('signal',['hiring'])[0]
        query=data.get('query',[''])[0].strip()
        period=data.get('period',['month'])[0]
        key=data.get('request_key',[''])[0]
        if not 16<=len(key)<=100:
            raise ValueError('Invalid submission. Reload the discovery form.')
        requests=selected_plan(trade,location,signal,query,period,data.get('query_ids',[]),
                               data.get('query_set',['tested'])[0])
        industry=TRADES[trade][0]
        store=Store(self.db_path)
        try:
            store.db.execute('BEGIN IMMEDIATE')
            existing=store.rows('SELECT id FROM research_runs WHERE request_key=?',(key,))
            if existing:
                store.db.rollback()
                return existing[0]['id']
            if store.rows("SELECT id FROM research_runs WHERE status IN ('queued','running','stopping')"):
                raise ValueError('Another run is active. Stop it or wait for it to finish.')
            remaining=discovery.budget_remaining(store)
            if len(requests)>remaining:
                raise ValueError(f'This batch needs {len(requests)} credits; only {remaining} remain in the local budget. Select fewer queries or wait for the budget to reset.')
            ident=store.db.execute("INSERT INTO research_runs(request_key,query,signal,source_ids,max_pages,max_depth,status,created_at) VALUES (?,?,?,'[]',0,0,'queued',?)",(key,query,signal,now())).lastrowid
            store.db.execute('INSERT INTO discovery_config VALUES (?,?,?,?,?)',(ident,industry,location,period,json.dumps(requests)))
            store.db.commit()
        except Exception:
            store.db.rollback()
            raise
        finally:
            store.close()
        if launch:
            self.launch(ident)
        return ident

    def launch(self, ident):
        thread=threading.Thread(target=self.run,args=(ident,),daemon=True)
        self.threads=[t for t in self.threads if t.is_alive()]
        self.threads.append(thread)
        thread.start()

    def recover(self):
        """Called once after binding the dashboard port, never on a browser refresh."""
        store = Store(self.db_path)
        try:
            with store.db:
                store.db.execute("UPDATE jobs SET status='interrupted',owner=NULL,lease_until=0 WHERE id IN (SELECT job_id FROM research_jobs WHERE run_id IN (SELECT id FROM research_runs WHERE status IN ('queued','running','stopping'))) AND status IN ('queued','running')")
                store.db.execute("UPDATE research_runs SET status='interrupted',finished_at=?,note='Dashboard restarted. Evidence retained; start a new run to continue.' WHERE status IN ('queued','running','stopping')", (now(),))
                store.db.execute("UPDATE classification_runs SET status='interrupted',finished_at=?,note='Dashboard restarted. Completed classifications were retained.' WHERE status IN ('queued','running')", (now(),))
                store.db.execute("UPDATE apify_runs SET status='interrupted',finished_at=?,note='Dashboard restarted. Saved evidence was retained.' WHERE status IN ('queued','running')", (now(),))
                store.db.execute("UPDATE contractor_verifications SET status='interrupted',finished_at=?,error='Dashboard restarted. Start verification again.' WHERE status IN ('queued','running')", (now(),))
                store.db.execute("UPDATE contact_runs SET status='interrupted',finished_at=?,error='Dashboard restarted. Start contact lookup again.' WHERE status IN ('queued','running')", (now(),))
        finally:
            store.close()

    def start_classification(self, limit=500, launch=True):
        key=self.classifier_connection.key()
        if not key:
            raise ValueError('Connect an OpenAI API key before classifying stored results.')
        if not 1<=limit<=1000:
            raise ValueError('Choose between 1 and 1000 stored results')
        store=Store(self.db_path)
        try:
            if store.rows("SELECT id FROM classification_runs WHERE status IN ('queued','running')"):
                raise ValueError('A classification run is already active.')
            total=len(llm_classifier.pending_rows(store,limit))
            if not total:
                raise ValueError('There are no unclassified results.')
            with store.db:
                ident=store.db.execute("INSERT INTO classification_runs(status,model,total,created_at) VALUES ('queued',?,?,?)",
                    (llm_classifier.model_name(),total,now())).lastrowid
        finally:
            store.close()
        if launch:
            thread=threading.Thread(target=self.run_classification,args=(ident,limit),daemon=True)
            self.threads=[t for t in self.threads if t.is_alive()]
            self.threads.append(thread)
            thread.start()
        return ident

    def run_classification(self, ident, limit=500):
        store=Store(self.db_path)
        claimed=False
        try:
            with store.db:
                claimed=store.db.execute("UPDATE classification_runs SET status='running' WHERE id=? AND status='queued'",(ident,)).rowcount
            if not claimed:
                return
            key=self.classifier_connection.key()
            if not key:
                raise ValueError('Classifier key unavailable. Reconnect and start another run.')
            def progress(processed,total):
                with store.db:
                    store.db.execute('UPDATE classification_runs SET processed=? WHERE id=?',(processed,ident))
            processed=llm_classifier.classify_pending(store,key,self.classifier_transport,
                llm_classifier.model_name(),limit=limit,progress=progress)
            with store.db:
                store.db.execute("UPDATE classification_runs SET status='completed',processed=?,finished_at=? WHERE id=?",
                    (processed,now(),ident))
        except Exception as exc:
            if claimed:
                message=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
                key=self.classifier_connection.key()
                if key:
                    message=message.replace(key,'[redacted]')
                with store.db:
                    store.db.execute("UPDATE classification_runs SET status='failed',finished_at=?,note=? WHERE id=?",
                        (now(),message[:300],ident))
        finally:
            store.close()

    def start_apify(self,result_id,mode,launch=True):
        token=self.apify_connection.key()
        if not token:
            raise ValueError('Connect an Apify API token before enrichment.')
        store=Store(self.db_path)
        try:
            plan=apify_enrichment.enrichment_plan(store,result_id,mode)
            if store.rows("SELECT id FROM apify_runs WHERE result_id=? AND mode=? AND status IN ('queued','running')",(result_id,mode)):
                raise ValueError('This enrichment is already running.')
            with store.db:
                ident=store.db.execute("""INSERT INTO apify_runs
                  (result_id,mode,target_url,status,created_at) VALUES (?,?,?,'queued',?)""",
                  (result_id,mode,plan['target_url'],now())).lastrowid
        finally:
            store.close()
        if launch:
            thread=threading.Thread(target=self.run_apify,args=(ident,),daemon=True)
            self.threads=[t for t in self.threads if t.is_alive()]
            self.threads.append(thread)
            thread.start()
        return ident

    def run_apify(self,ident):
        store=Store(self.db_path)
        claimed=False
        try:
            with store.db:
                claimed=store.db.execute("UPDATE apify_runs SET status='running' WHERE id=? AND status='queued'",(ident,)).rowcount
            if not claimed:
                return
            token=self.apify_connection.key()
            if not token:
                raise ValueError('Apify token unavailable. Reconnect and start another run.')
            count=apify_enrichment.run_enrichment(store,ident,token,self.apify_transport)
            with store.db:
                store.db.execute("UPDATE apify_runs SET status='completed',finished_at=?,note=? WHERE id=?",
                    (now(),f'{count} evidence pages saved.',ident))
        except Exception as exc:
            if claimed:
                message=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
                token=self.apify_connection.key()
                if token:
                    message=message.replace(token,'[redacted]')
                with store.db:
                    store.db.execute("UPDATE apify_runs SET status='failed',finished_at=?,note=? WHERE id=?",
                        (now(),message[:300],ident))
        finally:
            store.close()

    def start_contact_enrichment(self, result_id, launch=True):
        if not self.apify_connection.key():
            raise ValueError('Connect an Apify API token before finding contacts.')
        if not self.classifier_connection.key():
            raise ValueError('Connect OpenAI before finding contacts so their roles can be reviewed.')
        store=Store(self.db_path)
        try:
            plan=contact_enrichment.contact_plan(store,result_id)
            active=store.rows("SELECT id FROM contact_runs WHERE result_id=? AND status IN ('queued','running')",(result_id,))
            if active:
                raise ValueError('This contact lookup is already running.')
            with store.db:
                ident=store.db.execute("INSERT INTO contact_runs(result_id,company,status,created_at) VALUES (?,?, 'queued', ?)",
                    (result_id,plan['company'],now())).lastrowid
        finally:
            store.close()
        if launch:
            thread=threading.Thread(target=self.run_contact_enrichment,args=(ident,),daemon=True)
            self.threads=[t for t in self.threads if t.is_alive()]; self.threads.append(thread); thread.start()
        return ident

    def run_contact_enrichment(self, ident):
        store=Store(self.db_path); claimed=False
        try:
            with store.db:
                claimed=store.db.execute("UPDATE contact_runs SET status='running' WHERE id=? AND status='queued'",(ident,)).rowcount
            if not claimed: return
            run=store.rows('SELECT * FROM contact_runs WHERE id=?',(ident,))[0]
            plan=contact_enrichment.contact_plan(store,run['result_id'])
            # Retain the exact non-secret request for diagnosis, even if the call fails.
            with store.db:
                store.db.execute("UPDATE contact_runs SET note=? WHERE id=?",(
                    'Actor input: '+json.dumps(plan['input'],ensure_ascii=False),ident))
            items=contact_enrichment.request_contacts(plan['input'],self.apify_connection.key())
            contacts=contact_enrichment.normalize_contacts(items)
            count_before_review=len(contacts)
            note=f'{len(contacts)} people found from {len(items)} returned records. Company target: {plan["company"]}. Confirm company and role before contacting.'
            if not contacts:
                note+=' Apify returned an empty dataset for these filters; this does not prove the company has no matching employees.'
            if contacts:
                if not self.classifier_connection.key():
                    raise ValueError('OpenAI connection unavailable. Contacts could not be reviewed; reconnect OpenAI and retry.')
                try:
                    contacts=contact_enrichment.rank_contacts(contacts,plan['company'],self.classifier_connection.key(),self.classifier_transport)
                except ValueError as exc:
                    raise ValueError('OpenAI contact review failed: '+str(exc)[:160]) from None
                note=f'AI role review: {len(contacts)} suitable of {count_before_review} returned contacts. Employment and emails are not independently verified.'
            contact_enrichment.save_contacts(store,ident,contacts)
            with store.db:
                store.db.execute("UPDATE contact_runs SET status='completed',finished_at=?,note=? WHERE id=?",(now(),note,ident))
        except Exception as exc:
            if claimed:
                message=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
                for secret in (self.apify_connection.key(), self.classifier_connection.key()):
                    if secret: message=message.replace(secret,'[redacted]')
                with store.db:
                    store.db.execute("UPDATE contact_runs SET status='failed',finished_at=?,error=? WHERE id=?",(now(),message[:300],ident))
        finally:
            store.close()

    def start_contractor_verification(self,result_id,launch=True):
        if not self.connection.key():
            raise ValueError('Connect Tavily before verifying a contractor.')
        if not self.classifier_connection.key():
            raise ValueError('Connect OpenAI before verifying a contractor.')
        store=Store(self.db_path)
        reused=None
        try:
            row=contractor_verification.eligible(store,result_id)
            reused=contractor_verification.reuse_completed(store,result_id,row)
            if reused is None:
                with store.db:
                    store.db.execute("""INSERT INTO contractor_verifications(result_id,status,created_at)
                      VALUES (?,'queued',?) ON CONFLICT(result_id) DO UPDATE SET status='queued',
                      contractor_name=NULL,developer_name=NULL,project_name=NULL,project_address=NULL,
                      confidence=NULL,verification_json=NULL,created_at=excluded.created_at,
                      finished_at=NULL,error=NULL""",(result_id,now()))
        finally:
            store.close()
        if launch and reused is None:
            thread=threading.Thread(target=self.run_contractor_verification,args=(result_id,),daemon=True)
            self.threads=[t for t in self.threads if t.is_alive()]
            self.threads.append(thread); thread.start()
        return result_id

    def run_contractor_verification(self,result_id):
        store=Store(self.db_path)
        try:
            with store.db:
                claimed=store.db.execute("UPDATE contractor_verifications SET status='running' WHERE result_id=? AND status='queued'",(result_id,)).rowcount
            if not claimed: return
            contractor_verification.run(store,result_id,self.connection.key(),
                self.classifier_connection.key(),self.search_transport,self.classifier_transport)
        except Exception as exc:
            message=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
            for secret in (self.connection.key(),self.classifier_connection.key()):
                if secret: message=message.replace(secret,'[redacted]')
            with store.db:
                store.db.execute("UPDATE contractor_verifications SET status='failed',finished_at=?,error=? WHERE result_id=?",(now(),message[:300],result_id))
        finally:
            store.close()

    def start(self, data, launch=True):
        query = data.get('query',[''])[0].strip()
        signal = data.get('signal',[''])[0]
        geography = data.get('geography',[''])[0]
        pages = int(data.get('max_pages',['6'])[0])
        depth = int(data.get('max_depth',['1'])[0])
        key = data.get('request_key',[''])[0]
        profile = load_profile()
        if len(query)>500 or (signal and signal not in profile['signals']) or (geography and geography not in profile['geography']):
            raise ValueError('Invalid research terms, signal or county')
        if not 1<=pages<=20 or not 0<=depth<=3 or not 16<=len(key)<=100:
            raise ValueError('Choose 1–20 pages and depth 0–3')
        store = Store(self.db_path)
        try:
            existing = store.rows('SELECT id FROM research_runs WHERE request_key=?',(key,))
            if existing:
                return existing[0]['id']
            choices = {c['key']:c for c in source_options(store)}
            selected = list(dict.fromkeys(data.get('sources',[])))
            if any(k not in choices for k in selected):
                raise ValueError('Unknown source selection')
            urls = [choices[k] for k in selected]
            custom = data.get('custom_url',[''])[0].strip()
            if custom:
                urls.append({'url':canonical(custom),'name':'Added website'})
            if not 1<=len(urls)<=6 or pages<len(urls):
                raise ValueError('Select 1–6 websites and allow at least one page per website')
            ids = list(dict.fromkeys(add_source(store,u['name'],u['url'],u.get('prefix')) for u in urls))
            store.db.execute('BEGIN IMMEDIATE')
            try:
                existing = store.rows('SELECT id FROM research_runs WHERE request_key=?',(key,))
                if existing:
                    store.db.rollback()
                    return existing[0]['id']
                if store.rows("SELECT id FROM research_runs WHERE status IN ('queued','running','stopping')"):
                    raise ValueError('A research run is already active. Stop it or wait for it to finish.')
                ident = store.db.execute("INSERT INTO research_runs(request_key,query,signal,geography,source_ids,max_pages,max_depth,status,created_at) VALUES (?,?,?,?,?,?,?,'queued',?)",
                    (key,query,signal or None,geography or None,json.dumps(ids),pages,depth,now())).lastrowid
                store.db.commit()
            except Exception:
                store.db.rollback()
                raise
        finally:
            store.close()
        if launch:
            self.launch(ident)
        return ident

    def stop(self, ident):
        store=Store(self.db_path)
        try:
            if not store.rows('SELECT id FROM research_runs WHERE id=?',(ident,)):
                raise ValueError('Unknown research run')
            with store.db:
                store.db.execute("UPDATE research_runs SET status='stopping',note='Stop requested; waiting for the current HTTP request to finish.' WHERE id=? AND status IN ('queued','running')",(ident,))
        finally:
            store.close()

    def run(self, ident):
        store=Store(self.db_path)
        status,note='completed',None
        claimed=False
        try:
            with store.db:
                claimed=store.db.execute("UPDATE research_runs SET status='running' WHERE id=? AND status='queued'",(ident,)).rowcount
            if not claimed:
                # A stop can arrive between submission and worker startup.
                with store.db:
                    store.db.execute("UPDATE research_runs SET status='cancelled',finished_at=?,note='Stopped before collection began.' WHERE id=? AND status='stopping'",(now(),ident))
                return
            run=store.rows('SELECT * FROM research_runs WHERE id=?',(ident,))[0]
            configs=store.rows('SELECT * FROM discovery_config WHERE run_id=?',(ident,))
            if configs:
                key=self.connection.key()
                if not key:
                    raise ValueError('Search key unavailable. Reconnect Tavily and start a new search.')
                status,note=discovery.execute(store,run,configs[0],key,self.search_transport)
                if status.startswith('completed') or status=='cancelled':
                    classifier_key=self.classifier_connection.key()
                    if classifier_key:
                        try:
                            llm_classifier.classify_pending(store,classifier_key,self.classifier_transport,
                                llm_classifier.model_name(),limit=100,run_id=ident)
                        except ValueError as exc:
                            if status!='cancelled':
                                status='completed_with_gaps'
                            note=(note+' ' if note else '')+'Lead classification failed: '+str(exc)[:180]
                    else:
                        if status!='cancelled':
                            status='completed_with_gaps'
                        note=(note+' ' if note else '')+'Connect the lead classifier to turn results into scored leads.'
                return
            ids=json.loads(run['source_ids'])
            remaining=run['max_pages']
            def stopped():
                return store.rows('SELECT status FROM research_runs WHERE id=?',(ident,))[0]['status']=='stopping'
            for index,source_id in enumerate(ids):
                if stopped():
                    status,note='cancelled','Stopped by user. Collected evidence retained.'
                    break
                crawler=Crawler(store,self.transport,delay=self.delay,should_stop=stopped)
                jid=crawler.submit(source_id)
                with store.db:
                    store.db.execute('INSERT INTO research_jobs VALUES (?,?)',(ident,jid))
                allocation=max(1,remaining//(len(ids)-index))
                result=crawler.run(jid,allocation,run['max_depth'])
                consumed=store.db.execute("SELECT COUNT(*) FROM frontier WHERE job_id=? AND status!='pending'",(jid,)).fetchone()[0]
                remaining-=max(consumed,1)
                if result['status']=='cancelled' or stopped():
                    status,note='cancelled','Stopped by user. Collected evidence retained.'
                    break
                if result['status']!='completed':
                    status,note='completed_with_gaps','Some pages were blocked, failed or deferred by limits. See website details.'
        except Exception as exc:
            status,note='failed',str(exc)[:300] if isinstance(exc,ValueError) else type(exc).__name__
        finally:
            if claimed:
                with store.db:
                    store.db.execute("UPDATE research_runs SET status=CASE WHEN status='stopping' THEN 'cancelled' ELSE ? END,finished_at=?,note=? WHERE id=? AND status IN ('running','stopping')",(status,now(),note,ident))
            store.close()


def run_details(store, ident):
    rows=store.rows('SELECT * FROM research_runs WHERE id=?',(ident,))
    if not rows:
        raise ValueError('Unknown research run')
    run=rows[0]
    run['sources']=[store.rows('SELECT * FROM sources WHERE id=?',(sid,))[0] for sid in json.loads(run['source_ids'])]
    run['jobs']=store.rows('SELECT j.*,s.name FROM jobs j JOIN research_jobs r ON r.job_id=j.id JOIN sources s ON s.id=j.source_id WHERE r.run_id=? ORDER BY j.id',(ident,))
    run['attempts']=store.rows('SELECT f.* FROM fetch_attempts f JOIN research_jobs r ON r.job_id=f.job_id WHERE r.run_id=? ORDER BY f.id DESC LIMIT 100',(ident,))
    run['pages']=store.rows('SELECT f.* FROM frontier f JOIN research_jobs r ON r.job_id=f.job_id WHERE r.run_id=? ORDER BY f.job_id,f.depth,f.url',(ident,))
    run['results']=store.search(run['query'],run['signal'],run['geography'],limit=100,run_id=ident)
    run['documents']=store.search(limit=100,run_id=ident)
    return run
