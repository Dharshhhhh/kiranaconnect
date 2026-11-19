"""Local-only chat simulator. Standard library only, with an optional customer API bridge."""
from base64 import b64encode
from contextlib import closing
from datetime import datetime
from email.parser import BytesParser
from email.policy import default
from http import client
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import json, mimetypes, re, secrets, sqlite3, sys, threading, webbrowser

ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'connection.json').read_text())
MODE=CONFIG['mode']
REMOTE=urlsplit(CONFIG['kiranaconnect_url'])
if MODE not in ('standalone','connected') or REMOTE.scheme not in ('http','https') or not REMOTE.hostname or REMOTE.path not in ('','/'):
    raise ValueError('Check connection.json: choose standalone or connected and a server origin.')
def db():
    c=sqlite3.connect(ROOT/'demo.sqlite3',timeout=10)
    c.row_factory=sqlite3.Row
    return c
def init():
    with closing(db()) as c:
        c.executescript("""create table if not exists chats(id integer primary key,name text,token text unique);
        create table if not exists messages(id integer primary key,chat integer,side text,body text,at text,nonce text,blob blob,mime text,seen integer default 0,unique(chat,side,nonce));""")
def now():return datetime.now().astimezone().isoformat(timespec='seconds')

class Handler(BaseHTTPRequestHandler):
    def output(self,status,body,mime='application/json',cookie=None):
        if mime=='application/json' and not isinstance(body,bytes):body=json.dumps(body).encode()
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(body)
    def do_GET(self):self.handle_request()
    def do_POST(self):self.handle_request()
    def handle_request(self):
        path=urlsplit(self.path).path
        if self.command=='POST' and self.headers.get('Sec-Fetch-Site')=='cross-site':return self.output(403,{'detail':'Cross-site write blocked'})
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0<=length<=5*1024*1024+65536:return self.output(413,{'detail':'Maximum image size is 5 MB'})
            raw=self.rfile.read(length)
            if path=='/config':return self.output(200,{'mode':MODE,'shop_url':'/?shop' if MODE=='standalone' else REMOTE.geturl()})
            if path.startswith('/api/'):
                if MODE=='connected':return self.bridge(path,raw)
                with closing(db()) as c, c:return self.local(c,path,raw)
            p=(ROOT/'dist'/(path.lstrip('/') or 'index.html')).resolve()
            if not p.is_relative_to(ROOT/'dist') or not p.is_file():return self.output(404,{'detail':'Missing file'})
            self.output(200,p.read_bytes(),mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
        except (OSError,client.HTTPException):self.output(502,{'detail':'Start KiranaConnect and check kiranaconnect_url in connection.json.'})
        except (ValueError,KeyError,TypeError):self.output(422,{'detail':'Invalid message or file'})
    def bridge(self,path,raw):
        owner_route=bool(re.fullmatch(r'/api/(?:chat(?:/confirm)?|inbox(?:/\d+(?:/image)?)?|jobs/\d+/image|shop/photo/\d+)',path))
        if not owner_route and not re.fullmatch(r'/api/customer/(thread|start|message|image|(?:photo|images)/\d+)',path):return self.output(404,{'detail':'Only customer routes are connected'})
        conn=(client.HTTPSConnection if REMOTE.scheme=='https' else client.HTTPConnection)(REMOTE.hostname,REMOTE.port,timeout=30)
        try:
            cookies=SimpleCookie(self.headers.get('Cookie',''));headers={'Content-Type':self.headers.get('Content-Type','application/json')}
            key='kc' if owner_route else 'kc_customer'
            if key in cookies:headers['Cookie']=key+'='+cookies[key].value
            conn.request(self.command,path,body=raw or None,headers=headers)
            r=conn.getresponse();cookie=r.getheader('Set-Cookie')
            self.output(r.status,r.read(),r.getheader('Content-Type') or 'application/json',cookie if cookie and cookie.startswith('kc_customer=') else None)
        finally:conn.close()
    def local(self,c,path,raw):
        posting=self.command=='POST'
        d=json.loads(raw) if raw and self.headers.get('Content-Type','').startswith('application/json') else {}
        if path=='/api/customer/start' and posting:
            key=secrets.token_urlsafe(32);name=str(d.get('name','Meena'))[:60]
            cid=c.execute('insert into chats(name,token) values(?,?)',(name,key)).lastrowid
            c.execute('insert into messages(chat,side,body,at) values(?,?,?,?)',(cid,'shop','Welcome! Send your grocery list or attach a screenshot.',now()))
            return self.output(200,{'name':name},cookie='wa_demo='+key+'; Path=/; HttpOnly; SameSite=Strict')
        cookies=SimpleCookie(self.headers.get('Cookie',''))
        person=c.execute('select * from chats where token=?',(cookies['wa_demo'].value if 'wa_demo' in cookies else '',)).fetchone()
        buyer=path.startswith('/api/customer/')
        if buyer and not person:return self.output(401,{'detail':'Start your chat'})
        if path=='/api/inbox' and not posting:
            return self.output(200,[dict(r) for r in c.execute('select c.id,c.name,m.body from chats c join messages m on m.id=(select max(id) from messages where chat=c.id) order by m.id desc')])
        if re.fullmatch(r'/api/(customer|shop)/photo/\d+',path) and not posting:
            photo=c.execute('select blob,mime from messages where id=? and (?=0 or chat=?)',(int(path.split('/')[-1]),int(buyer),person['id'] if person else 0)).fetchone()
            if not photo or not photo['blob']:return self.output(404,{'detail':'Missing photo'})
            return self.output(200,photo['blob'],photo['mime'])
        other=re.fullmatch(r'/api/inbox/(\d+)(/image)?',path)
        if not other and path not in ('/api/customer/thread','/api/customer/message','/api/customer/image'):return self.output(404,{'detail':'Unknown route'})
        cid=person['id'] if buyer else int(other[1]);side='customer' if buyer else 'shop'
        if not c.execute('select 1 from chats where id=?',(cid,)).fetchone():return self.output(404,{'detail':'Missing chat'})
        if not posting:
            c.execute('update messages set seen=1 where chat=? and side!=?',(cid,side))
            msgs=[dict(r) for r in c.execute('select id,body,side,at,seen,blob is not null as photo from messages where chat=? order by id',(cid,))]
            return self.output(200,dict(messages=msgs,catalog=[],name=person['name']) if buyer else msgs)
        photo=None;mime=None
        if path.endswith('/image'):
            env=BytesParser(policy=default).parsebytes(('Content-Type: '+self.headers.get('Content-Type','')+'\r\n\r\n').encode()+raw)
            parts={p.get_param('name',header='content-disposition'):p.get_payload(decode=True) for p in env.iter_parts()}
            photo=parts['file'];nonce=parts['nonce'].decode()
            if photo.startswith(b'\x89PNG\r\n\x1a\n'):mime='image/png'
            elif photo.startswith(b'\xff\xd8\xff'):mime='image/jpeg'
            elif photo[:4]==b'RIFF' and photo[8:12]==b'WEBP':mime='image/webp'
            else:raise ValueError()
            if len(photo)>5*1024*1024:raise ValueError()
            body='Photo'
        else:body=d['body'].strip();nonce=d['nonce']
        if not (0<len(body)<=1500 and 0<len(nonce)<=100):raise ValueError()
        c.execute('insert or ignore into messages(chat,side,body,at,nonce,blob,mime) values(?,?,?,?,?,?,?)',(cid,side,body,now(),nonce,photo,mime))
        return self.output(200,{'sent':True})

if __name__=='__main__':
    init()
    server=ThreadingHTTPServer(('127.0.0.1',8090),Handler)
    print('WhatsApp Simulator: http://127.0.0.1:8090  |  '+MODE,flush=True)
    if '--open' in sys.argv:threading.Timer(.4,lambda:webbrowser.open('http://127.0.0.1:8090')).start()
    server.serve_forever()
