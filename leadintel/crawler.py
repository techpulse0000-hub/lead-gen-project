"""Single-worker, resumable focused HTML crawler with public-IP pinning."""
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote
from urllib.robotparser import RobotFileParser

from .store import now
from .profile import load_profile

USER_AGENT = "LeadIntelPrototype/0.1"
SOCIAL = {"linkedin.com","instagram.com","facebook.com","x.com","twitter.com","indeed.com","tiktok.com","youtube.com","youtu.be"}
SIGNALS = load_profile()["signals"]
RELEVANT = re.compile(r"news|project|permit|development|opening|deal|bid|letting|award|press|blog|construction|groundbreak|underway|expand", re.I)


def canonical(url):
    if len(url)>2048 or any(c.isspace() or ord(c)<32 for c in url) or "\\" in url:
        raise ValueError("Invalid URL")
    p = urlsplit(url)
    if p.scheme not in ("http","https") or not p.hostname or p.username or p.password:
        raise ValueError("Only public credential-free HTTP(S) URLs")
    if p.port not in (None,80,443) or (p.port and p.port != (443 if p.scheme=="https" else 80)):
        raise ValueError("Nonstandard port")
    host = p.hostname.lower().rstrip(".").encode("idna").decode()
    if host=="localhost" or host.endswith((".local",".internal")):
        raise ValueError("Private hostname")
    if any(host==s or host.endswith("."+s) for s in SOCIAL):
        raise ValueError("Social/job pages require assessed provider adapters")
    # Reject encoded traversal and control characters before prefix checks.
    decoded = p.path
    for _ in range(3):
        decoded = unquote(decoded)
    if "\\" in decoded or any(ord(c)<32 for c in decoded) or any(x in (".","..") for x in decoded.split("/")):
        raise ValueError("Unsafe URL path")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ValueError("Nonpublic IP")
    netloc = "["+host+"]" if ":" in host else host
    return urlunsplit((p.scheme,netloc,p.path or "/",p.query,""))


def origin(url):
    p = urlsplit(url)
    return p.scheme+"://"+p.netloc


def public_addresses(host, port):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Nonpublic resolved address")
    return addresses


class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, address, timeout, tls=False):
        super().__init__(host, port, timeout=timeout)
        self.address, self.tls = address, tls

    def connect(self):
        family, socktype, proto, _, target = self.address
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(self.timeout)
        try:
            sock.connect(target)  # Address already resolved and validated, never resolve again.
            if self.tls:
                context = ssl.create_default_context()
                context.set_alpn_protocols(["http/1.1"])
                sock = context.wrap_socket(sock, server_hostname=self.host)
            self.sock = sock
        except Exception:
            sock.close()
            raise


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict


def fetch_public(url, byte_limit):
    p = urlsplit(canonical(url))
    port = 443 if p.scheme=="https" else 80
    addresses = public_addresses(p.hostname, port)
    conn = PinnedHTTP(p.hostname,port,addresses[0],20,tls=p.scheme=="https")
    try:
        path = urlunsplit(("","",p.path,p.query,""))
        conn.request("GET",path,headers={"User-Agent":USER_AGENT,
                     "Accept":"text/html,text/plain;q=0.9", "Accept-Encoding":"identity"})
        r = conn.getresponse()
        headers = {k.lower():v for k,v in r.getheaders()}
        if headers.get("content-encoding", "identity").lower() not in ("identity", ""):
            raise ValueError("Compressed responses not supported in prototype")
        if int(headers.get("content-length","0")) > byte_limit:
            raise ValueError("Response exceeds byte limit")
        data, deadline = bytearray(), time.monotonic()+25
        while len(data) <= byte_limit:
            if time.monotonic()>deadline:
                raise TimeoutError("Response read deadline")
            if conn.sock:
                conn.sock.settimeout(max(.1,min(20,deadline-time.monotonic())))
            chunk = r.read1(min(65536,byte_limit+1-len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data)>byte_limit:
            raise ValueError("Response exceeds byte limit")
        return Response(r.status,bytes(data),headers)
    finally:
        conn.close()


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.title, self.links = [], [], []
        self.skip, self.in_title, self.publication_date = 0, False, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script","style","noscript"):
            self.skip += 1
        if tag=="title":
            self.in_title=True
        if tag=="a" and a.get("href") and len(self.links)<500:
            self.links.append(a["href"])
        if tag=="meta" and a.get("property",a.get("name")) in ("article:published_time","datePublished"):
            try:
                d = datetime.fromisoformat(a.get("content","").replace("Z","+00:00"))
                self.publication_date=d.isoformat()
            except ValueError:
                pass

    def handle_endtag(self, tag):
        if tag in ("script","style","noscript") and self.skip:
            self.skip-=1
        if tag=="title":
            self.in_title=False

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.text.append(data.strip())
            if self.in_title:
                self.title.append(data.strip())


def classify(text, profile=None):
    profile=profile or load_profile()
    low = text.lower()
    signals = [k for k,words in profile["signals"].items() if any(re.search(r"\b"+re.escape(w.lower())+r"\b",low) for w in words)]
    places = [k for k,words in profile["geography"].items() if any(re.search(r"\b"+re.escape(w.lower())+r"\b",low) for w in words)]
    return signals, places


def add_source(store, name, url, prefix=None):
    url=canonical(url)
    path=urlsplit(url).path
    prefix=prefix if prefix is not None else (path if path.endswith("/") else path.rsplit("/",1)[0]+"/")
    if not prefix.startswith("/") or "?" in prefix or "#" in prefix:
        raise ValueError("Prefix must be an absolute URL path")
    # Validate prefix with the same decoded traversal checks as target URLs.
    canonical(origin(url)+prefix)
    if not within(url,origin(url),prefix):
        raise ValueError("Source URL must be inside the admitted prefix")
    with store.db:
        store.db.execute("INSERT OR IGNORE INTO sources(name,url,origin,prefix) VALUES(?,?,?,?)", (name,url,origin(url),prefix))
    return store.db.execute("SELECT id FROM sources WHERE url=?", (url,)).fetchone()[0]


def within(url, source_origin, prefix):
    p=urlsplit(url)
    path=unquote(p.path)
    return origin(url)==source_origin and (path==prefix.rstrip("/") or path.startswith(prefix if prefix.endswith("/") else prefix+"/"))


class CrawlCancelled(Exception):
    pass


class Crawler:
    def __init__(self, store, transport=None, delay=2, profile=None, should_stop=None):
        self.store,self.transport=store,transport or fetch_public
        self.delay=delay
        self.last_request={}
        self.profile=profile or load_profile()
        self.should_stop=should_stop or (lambda: False)

    def checkpoint(self):
        if self.should_stop():
            raise CrawlCancelled("Stopped by user; collected evidence retained")

    def submit(self, source_id):
        source=self.store.db.execute("SELECT * FROM sources WHERE id=? AND enabled=1", (source_id,)).fetchone()
        if not source:
            raise ValueError("Unknown or disabled source")
        with self.store.db:
            ident=self.store.db.execute("INSERT INTO jobs(source_id,status,created_at) VALUES(?,?,?)", (source_id,"queued",now())).lastrowid
            self.store.db.execute("INSERT INTO frontier(job_id,url,depth) VALUES(?,?,0)", (ident,source["url"]))
        return ident

    def _request(self, job, source, url, limit):
        self.checkpoint()
        url=canonical(url)
        if origin(url)!=source["origin"]:
            raise ValueError("Cross-origin request requires a separate admitted source")
        if source["origin"] not in self.last_request:
            previous=self.store.db.execute("SELECT MAX(started_at) FROM fetch_attempts WHERE origin=?", (source["origin"],)).fetchone()[0]
            if previous:
                elapsed=max(0,time.time()-datetime.fromisoformat(previous).timestamp())
                self.last_request[source["origin"]]=time.monotonic()-elapsed
        pause=self.delay-(time.monotonic()-self.last_request.get(source["origin"],0))
        if pause>0:
            deadline=time.monotonic()+pause
            while time.monotonic()<deadline:
                self.checkpoint()
                time.sleep(min(.2,max(0,deadline-time.monotonic())))
        self.checkpoint()
        ident=self.store.reserve_fetch(job,source["origin"],url)
        self.last_request[source["origin"]]=time.monotonic()
        try:
            response=self.transport(url,limit)
            if len(response.body)>limit:
                raise ValueError("Response exceeds byte limit")
            with self.store.db:
                self.store.db.execute("UPDATE fetch_attempts SET status=?,detail=? WHERE id=?", ("received","HTTP "+str(response.status),ident))
            return response
        except Exception as exc:
            with self.store.db:
                self.store.db.execute("UPDATE fetch_attempts SET status='failed',detail=? WHERE id=?", (type(exc).__name__,ident))
            raise

    def _robots(self, job, source):
        url=source["origin"]+"/robots.txt"
        for _ in range(4):
            r=self._request(job,source,url,65536)
            if r.status in (301,302,303,307,308):
                url=canonical(urljoin(url,r.headers.get("location","")))
                if origin(url)!=source["origin"]:
                    raise ValueError("Cross-origin robots redirect deferred")
                continue
            if r.status==404:
                parser=RobotFileParser()
                parser.parse([])
                return parser
            if r.status!=200:
                raise ValueError("Robots unavailable: HTTP "+str(r.status))
            parser=RobotFileParser()
            parser.parse(r.body.decode("utf-8","replace").splitlines())
            wait=parser.crawl_delay(USER_AGENT)
            if wait and wait>self.delay:
                if wait>30:
                    raise ValueError("Long crawl delay: deferred for later implementation")
                self.delay=wait
            return parser
        raise ValueError("Too many robots redirects")

    def _page(self, job, source, url, robots):
        for _ in range(4):
            url=canonical(url)
            if not within(url,source["origin"],source["prefix"]):
                raise ValueError("URL outside admitted source section")
            if not robots.can_fetch(USER_AGENT,url):
                raise ValueError("Robots disallowed")
            r=self._request(job,source,url,3_000_000)
            if r.status in (301,302,303,307,308):
                url=urljoin(url,r.headers.get("location",""))
                continue
            if r.status!=200:
                raise ValueError("HTTP "+str(r.status)+"; no automatic retry")
            if "text/html" not in r.headers.get("content-type",""):
                raise ValueError("Only HTML supported in this slice")
            charset=re.search(r"charset=([\w-]+)",r.headers.get("content-type",""))
            page=Page()
            try:
                page.feed(r.body.decode(charset.group(1) if charset else "utf-8","replace"))
            except LookupError:
                raise ValueError("Unsupported declared character encoding")
            return url,page
        raise ValueError("Too many redirects")

    def run(self, job_id, max_pages=20, max_depth=3):
        if not 1<=max_pages<=20 or not 0<=max_depth<=3:
            raise ValueError("At most 20 pages and depth 3")
        db=self.store.db
        owner=uuid.uuid4().hex
        db.execute("BEGIN IMMEDIATE")
        try:
            job=db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not job:
                raise ValueError("Unknown job")
            if job["status"]=="completed":
                db.rollback()
                return dict(job)
            active=db.execute("SELECT id FROM jobs WHERE lease_until>?", (time.time(),)).fetchone()
            if active:
                raise ValueError("A crawler job is already owned by a worker; prototype runs one at a time")
            db.execute("UPDATE jobs SET status='running',owner=?,lease_until=? WHERE id=?", (owner,time.time()+300,job_id))
            db.commit()
        except Exception:
            db.rollback()
            raise
        source=db.execute("SELECT * FROM sources WHERE id=? AND enabled=1", (job["source_id"],)).fetchone()
        note,status=None,"completed"
        start=time.monotonic()
        try:
            if not source:
                raise ValueError("Source disabled")
            robots=self._robots(job_id,source)
            count=0
            while count<max_pages:
                self.checkpoint()
                if time.monotonic()-start>120:
                    status,note="deferred","Job time limit; resume remaining frontier"
                    break
                row=db.execute("SELECT * FROM frontier WHERE job_id=? AND status='pending' ORDER BY depth,url LIMIT 1", (job_id,)).fetchone()
                if not row:
                    break
                with db:
                    db.execute("UPDATE jobs SET lease_until=? WHERE id=? AND owner=?", (time.time()+300,job_id,owner))
                if row["depth"]>max_depth:
                    status,note="deferred","Pending URL exceeds requested crawl depth"
                    break
                try:
                    final,page=self._page(job_id,source,row["url"],robots)
                    title=" ".join(page.title)
                    body="\n".join(page.text)
                    signals,places=classify(title+"\n"+body,self.profile)
                    document_id=self.store.ingest(source["id"],final,title,body,page.publication_date,signals,places)
                    with db:
                        db.execute("INSERT OR IGNORE INTO job_documents VALUES (?,?)", (job_id,document_id))
                    if row["depth"]<max_depth:
                        for href in page.links:
                            try:
                                link=canonical(urljoin(final,href))
                                if not within(link,source["origin"],source["prefix"]) or urlsplit(link).query or not RELEVANT.search(urlsplit(link).path):
                                    continue
                                with db:
                                    n=db.execute("SELECT COUNT(*) FROM frontier WHERE job_id=?", (job_id,)).fetchone()[0]
                                    if n<100:
                                        db.execute("INSERT OR IGNORE INTO frontier(job_id,url,depth) VALUES(?,?,?)", (job_id,link,row["depth"]+1))
                                    else:
                                        note="Frontier capped at 100 URLs; link coverage partial"
                            except ValueError:
                                continue
                    with db:
                        db.execute("UPDATE frontier SET status='indexed' WHERE job_id=? AND url=?", (job_id,row["url"]))
                except (ValueError,OSError,http.client.HTTPException) as exc:
                    message=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
                    if "budget exhausted" in message:
                        status,note="deferred",message
                        break
                    with db:
                        db.execute("UPDATE frontier SET status='blocked_or_failed',error=? WHERE job_id=? AND url=?", (message[:300],job_id,row["url"]))
                count+=1
            if status=="completed":
                remaining=db.execute("SELECT COUNT(*) FROM frontier WHERE job_id=? AND status='pending'", (job_id,)).fetchone()[0]
                failed=db.execute("SELECT COUNT(*) FROM frontier WHERE job_id=? AND status='blocked_or_failed'", (job_id,)).fetchone()[0]
                if remaining:
                    status,note="deferred","Page limit; remaining frontier retained"
                elif failed:
                    status="completed_with_gaps"
        except CrawlCancelled as exc:
            status,note="cancelled",str(exc)
        except (ValueError,OSError,http.client.HTTPException) as exc:
            status="deferred"
            note=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
        except Exception as exc:
            status,note="failed","Internal error: "+type(exc).__name__
            raise
        finally:
            with db:
                db.execute("UPDATE jobs SET status=?,note=?,lease_until=0,owner=NULL WHERE id=? AND owner=?", (status,note,job_id,owner))
        return dict(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
