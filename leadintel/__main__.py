"""python -m leadintel --help"""
import argparse
import json
from pathlib import Path

from .crawler import Crawler, Response, add_source
from .providers import search_plan, social_plan
from .store import Store
from .profile import DEFAULT_PROFILE, load_profile


DEMO = {
    "https://demo.example.org/news/": """<html><title>Demo contractor newsroom</title><body>
    <p>Synthetic demonstration. These are fictional companies, not real opportunities.</p>
    <a href='/news/project'>Construction project announcement</a>
    <a href='/news/hiring'>Hiring announcement</a>
    <a href='https://unrelated.example.org/news/'>Unrelated external site</a></body></html>""",
    "https://demo.example.org/news/project": """<html><title>Synthetic: Sample Builders awarded Frisco project</title>
    <meta property='article:published_time' content='2026-10-12T09:00:00Z'><body>
    <p>FICTIONAL TEST EVIDENCE: Sample Builders reports it was awarded a construction project in Frisco.
    Groundbreaking is planned. This does not establish apparel demand or purchasing responsibility.</p></body></html>""",
    "https://demo.example.org/news/hiring": """<html><title>Synthetic: Example Mechanical hiring in Fort Worth</title><body>
    <p>FICTIONAL TEST EVIDENCE: Example Mechanical is hiring for field operations in Fort Worth.
    Posting date, hiring quantity and apparel demand are unknown.</p></body></html>""",
}


def run_demo(store):
    ident=add_source(store,"Synthetic demonstration only","https://demo.example.org/news/")
    def transport(url, limit):
        if url.endswith("/robots.txt"):
            return Response(200,b"User-agent: *\nAllow: /",{"content-type":"text/plain"})
        if url in DEMO:
            return Response(200,DEMO[url].encode(),{"content-type":"text/html; charset=utf-8"})
        return Response(404,b"",{})
    job=Crawler(store,transport,delay=0)
    jid=job.submit(ident)
    result=job.run(jid)
    with store.db:
        store.db.execute("UPDATE documents SET is_demo=1,access_method='synthetic_fixture' WHERE source_id=?", (ident,))
        store.db.execute("UPDATE sources SET enabled=0 WHERE id=?", (ident,))
    # Re-enable only for subsequent explicitly requested offline demo runs.
    return result


def main():
    parser=argparse.ArgumentParser(description="Bounded lead research engine; dashboard company discovery requires Tavily")
    parser.add_argument("--db",default="data/engine.sqlite")
    parser.add_argument("--profile",default=str(DEFAULT_PROFILE),help="Data-only crawl classification profile")
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("init")
    sub.add_parser("demo")
    p=sub.add_parser("add-source")
    p.add_argument("--name",required=True)
    p.add_argument("--url",required=True)
    p.add_argument("--prefix")
    p=sub.add_parser("crawl")
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--source",type=int)
    group.add_argument("--job",type=int)
    p.add_argument("--max-pages",type=int,default=20)
    p.add_argument("--max-depth",type=int,default=3)
    p=sub.add_parser("search")
    p.add_argument("query",nargs="?",default="")
    p.add_argument("--signal",choices=["award","hiring","mobilization","expansion"])
    p.add_argument("--geography",choices=["Dallas","Tarrant","Collin","Denton"])
    sub.add_parser("coverage")
    p=sub.add_parser("flag")
    p.add_argument("--document",required=True,type=int)
    p.add_argument("--company",required=True)
    p.add_argument("--reason",required=True)
    p=sub.add_parser("qualify")
    p.add_argument("lead",type=int)
    sub.add_parser("enrichment-queue")
    p=sub.add_parser("plan-search")
    p.add_argument("--company")
    p.add_argument("--location",default="Dallas")
    p.add_argument("--signal",default="award")
    p.add_argument("--domain",action="append",default=[])
    p.add_argument("--since")
    p.add_argument("--advanced",action="store_true")
    p=sub.add_parser("plan-social")
    p.add_argument("--account",required=True)
    p.add_argument("--platform",required=True,choices=["linkedin","instagram"])
    p.add_argument("--since",required=True)
    p.add_argument("--max-posts",type=int,default=20)
    p=sub.add_parser("serve")
    p.add_argument("--port",type=int,default=8765)
    args=parser.parse_args()
    store=Store(args.db)
    try:
        if args.command=="init":
            result={"database":str(Path(args.db).resolve()),"network_requests":0}
        elif args.command=="demo":
            with store.db:
                store.db.execute("UPDATE sources SET enabled=1 WHERE url='https://demo.example.org/news/'")
            result=run_demo(store)
        elif args.command=="add-source":
            result={"source_id":add_source(store,args.name,args.url,args.prefix),"network_requests":0}
        elif args.command=="crawl":
            crawler=Crawler(store,profile=load_profile(args.profile))
            job=args.job if args.job is not None else crawler.submit(args.source)
            result=crawler.run(job,args.max_pages,args.max_depth)
        elif args.command=="search":
            result=store.search(args.query,args.signal,args.geography)
        elif args.command=="coverage":
            result=store.coverage()
        elif args.command=="flag":
            result={"lead_id":store.flag(args.document,args.company,args.reason),"status":"flagged","enrichment_triggered":False}
        elif args.command=="qualify":
            result=store.begin_qualification(args.lead)
        elif args.command=="enrichment-queue":
            result=store.enrichment_tasks()
        elif args.command=="plan-search":
            result=search_plan(args.company,args.location,args.signal,args.domain,args.since,args.advanced)
        elif args.command=="plan-social":
            result=social_plan(args.account,args.platform,args.since,args.max_posts)
        elif args.command=="serve":
            from .web import serve
            store.close()
            serve(args.db,args.port)
            return
        print(json.dumps(result,indent=2,ensure_ascii=False))
    except (ValueError,KeyError) as exc:
        parser.exit(2,str(exc)+"\n")
    finally:
        store.close()


if __name__=="__main__":
    main()
