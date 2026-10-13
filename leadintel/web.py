"""Loopback-only operator dashboard. Not a production web server."""
import html
import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

from .store import Store

STYLE = """body{font:16px system-ui;background:#f3f6fa;color:#172438;margin:0}
main{max-width:1100px;margin:auto;padding:30px}h1{font-size:30px;margin-bottom:6px}
.muted{color:#56667d}nav{display:flex;gap:18px;margin:24px 0}a{color:#1465ba}
.card{background:white;border:1px solid #dce3ee;border-radius:12px;padding:20px;margin:16px 0}
input,select,button{font:inherit;padding:10px;border:1px solid #bcc8da;border-radius:6px}
input{max-width:90%}button{background:#1465ba;color:white;cursor:pointer}table{width:100%;border-collapse:collapse}
td,th{text-align:left;padding:10px;border-bottom:1px solid #e2e8f0;overflow-wrap:anywhere}
.tag{background:#e6eef8;padding:4px 8px;border-radius:5px;display:inline-block}
pre{white-space:pre-wrap;overflow-wrap:anywhere}.notice{background:#fff3cc;padding:14px;border-radius:8px}
label{display:inline-block;margin:5px}code{overflow-wrap:anywhere}"""


def esc(value):
    return html.escape(str(value),quote=True)


def handler(db_path):
    token=secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def valid_host(self):
            return self.headers.get("Host") in ("127.0.0.1:"+str(self.server.server_port),
                                                 "localhost:"+str(self.server.server_port))

        def send_page(self, body, status=200):
            content=("<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                     "<title>Lead intelligence · Research engine</title><style>"+STYLE+"</style></head><body><main>"
                     "<h1>Lead intelligence</h1><div class='muted'>Research engine prototype · local operator workspace</div>"
                     "<nav><a href='/'>Search evidence</a><a href='/leads'>Lead review</a><a href='/coverage'>Coverage &amp; jobs</a></nav>"
                     +body+"</main></body></html>").encode()
            self.send_response(status)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(content)))
            self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if not self.valid_host():
                self.send_error(403)
                return
            store=Store(db_path)
            try:
                p=urlsplit(self.path)
                q=parse_qs(p.query)
                if p.path=="/":
                    term=q.get("q",[""])[0]
                    signal=q.get("signal",[""])[0]
                    geo=q.get("geography",[""])[0]
                    results=store.search(term,signal or None,geo or None)
                    def select(name, values, selected):
                        return "<select name='"+name+"'><option value=''>Any "+name+"</option>"+"".join("<option "+("selected " if v==selected else "")+"value='"+v+"'>"+v+"</option>" for v in values)+"</select>"
                    body="<div class='notice'>Results are research evidence. Geography tags are text mentions, not verified project locations. Demo records are explicitly labelled.</div>"
                    body+="<form class='card' method='get'><input name='q' placeholder='Search collected evidence' value='"+esc(term)+"'> "+select("signal",["award","hiring","mobilization","expansion"],signal)+" "+select("geography",["Dallas","Tarrant","Collin","Denton"],geo)+" <button>Search</button></form>"
                    body+="<p>"+str(len(results))+" results · searches only stored evidence; sends no network requests</p>"
                    for r in results:
                        body+="<article class='card'><span class='tag'>"+("SYNTHETIC DEMO" if r["is_demo"] else "UNVERIFIED EVIDENCE")+"</span><h2><a href='/evidence?id="+str(r["id"])+"'>"+esc(r["title"])+"</a></h2><p>"+esc(r["excerpt"])+"</p><p class='muted'>"+esc(r["url"])+"</p><p>Signals: "+esc(", ".join(r["signals"]))+" · Geography mentions: "+esc(", ".join(r["geography"]))+"</p></article>"
                    if not results:
                        body+="<div class='card'>No indexed evidence yet. Run the demo or admit and crawl a source using the CLI.</div>"
                elif p.path=="/evidence":
                    ident=int(q.get("id",["0"])[0])
                    rows=store.rows("SELECT * FROM documents WHERE id=?", (ident,))
                    if not rows:
                        raise ValueError("Unknown evidence")
                    r=rows[0]
                    body="<article class='card'><h2>"+esc(r["title"])+"</h2><p>"+("SYNTHETIC DEMO · " if r["is_demo"] else "")+"Unverified evidence</p><p>Source: "+esc(r["url"])+"</p><p>Retrieved: "+esc(r["retrieved_at"])+"<br>Last checked: "+esc(r["checked_at"])+"<br>Reported publication date: "+esc(r["publication_date"] or "Unknown")+"<br>Event date: Unknown</p><pre>"+esc(r["body"])+"</pre></article>"
                    body+="<form class='card' method='post' action='/flag'><h2>Flag a potential lead</h2><p>This saves a candidate. It does not run the company/contact scraper.</p><input type='hidden' name='csrf' value='"+token+"'><input type='hidden' name='document_id' value='"+str(ident)+"'><label>Company <input name='company' required maxlength='200'></label><label>Evidence reason <input name='reason' required maxlength='2000'></label><button>Flag candidate</button></form>"
                elif p.path=="/leads":
                    body="<div class='notice'>Company/contact enrichment is queued only when qualification begins. The enrichment worker is not implemented yet.</div>"
                    for r in store.rows("SELECT * FROM leads ORDER BY id DESC"):
                        body+="<article class='card'><h2>"+esc(r["company"])+"</h2><span class='tag'>"+esc(r["status"])+"</span><p>"+esc(r["reason"])+"</p><a href='/evidence?id="+str(r["document_id"])+"'>Supporting evidence</a>"
                        if r["status"]=="flagged":
                            body+="<form method='post' action='/qualify'><input type='hidden' name='csrf' value='"+token+"'><input type='hidden' name='lead_id' value='"+str(r["id"])+"'><p><button>Begin qualification</button></p></form>"
                        body+="</article>"
                    body+="<div class='card'><h2>Qualification enrichment queue</h2><pre>"+esc(json.dumps(store.enrichment_tasks(),indent=2))+"</pre></div>"
                elif p.path=="/coverage":
                    body="<div class='card'><h2>Sources, jobs and request accounting</h2><p>Failures and pending work remain visible. Recurring monitoring is off.</p><pre>"+esc(json.dumps(store.coverage(),indent=2))+"</pre></div>"
                else:
                    self.send_error(404)
                    return
                self.send_page(body)
            except (ValueError,OverflowError) as exc:
                self.send_page("<p>"+esc(exc)+"</p>",400)
            finally:
                store.close()

        def do_POST(self):
            if not self.valid_host():
                self.send_error(403)
                return
            expected="http://"+self.headers.get("Host","")
            if self.headers.get("Origin") not in (None,expected):
                self.send_error(403)
                return
            try:
                size=int(self.headers.get("Content-Length","0"))
                if not 0<size<=8192:
                    raise ValueError("Request too large or empty")
                if self.headers.get("Content-Type","").split(";")[0]!="application/x-www-form-urlencoded":
                    raise ValueError("Form encoding required")
                data=parse_qs(self.rfile.read(size).decode("utf-8"))
                if not secrets.compare_digest(data.get("csrf",[""])[0],token):
                    self.send_error(403)
                    return
                store=Store(db_path)
                try:
                    if self.path=="/flag":
                        store.flag(int(data["document_id"][0]),data["company"][0],data["reason"][0])
                    elif self.path=="/qualify":
                        store.begin_qualification(int(data["lead_id"][0]))
                    else:
                        self.send_error(404)
                        return
                finally:
                    store.close()
                self.send_response(303)
                self.send_header("Location","/leads")
                self.end_headers()
            except (ValueError,KeyError,UnicodeError):
                self.send_page("<p>Invalid form submission</p>",400)
    return Handler


def serve(db_path, port=8765):
    server=HTTPServer(("127.0.0.1",port),handler(db_path))
    print("Local dashboard: http://127.0.0.1:"+str(server.server_port),flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
