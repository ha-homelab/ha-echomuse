#!/usr/bin/env python3
"""Loopback-only recorder UI. Credentials stay on the Mac; audio is private."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import urllib.error
import urllib.request


class App:
    def __init__(self, args):
        self.args = args
        self.creds = json.loads(args.credentials.read_text())
        self.base = self.creds['url'].rstrip('/')
        self.token = None
        self.csrf = secrets.token_urlsafe(32)
        self.session = None
        self.lock = threading.Lock()
        self.output = args.output.resolve()
        self.output.mkdir(parents=True, exist_ok=True, mode=0o700)

    def request(self, path, data=None, binary=False):
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        r = urllib.request.Request(self.base+path, headers=headers,
            data=json.dumps(data).encode() if data is not None else None)
        with urllib.request.urlopen(r, timeout=8) as f:
            raw = f.read()
        return raw if binary else json.loads(raw)

    def login(self):
        if self.token:
            try:
                self.request("/api/auth/logout", {})
            except Exception:
                # An expired or unreachable old login must not prevent a new one.
                pass
            self.token = None
        data = self.request('/api/auth/login', {k: self.creds[k] for k in ('username', 'password')})
        self.token = data.get('token') or data['access_token']

    def sync(self, view):
        folder = self.output / view['id']
        folder.mkdir(exist_ok=True, mode=0o700)
        for take in view['takes']:
            path = folder / f"{take['number']:02d}.wav"
            if path.exists():
                if hashlib.sha256(path.read_bytes()).hexdigest() != take['sha256']:
                    raise ValueError('Saved recording checksum changed')
            else:
                raw = self.request(f"/api/training/sessions/{view['id']}/takes/{take['number']}", binary=True)
                if hashlib.sha256(raw).hexdigest() != take['sha256']:
                    raise ValueError('Downloaded recording checksum mismatch')
                temp = path.with_suffix('.partial')
                temp.write_bytes(raw)
                temp.replace(path)
            path.with_suffix('.json').write_text(json.dumps(take, ensure_ascii=False, indent=2))
        (folder/'session.json').write_text(json.dumps(view, ensure_ascii=False, indent=2))
        view['saved_on_mac'] = len(view['takes'])
        return view

    def action(self, action, body):
        with self.lock:
            if action == 'history':
                # Restore the last completed result after a page/server reload.
                # This never arms capture, renews a lease, or resumes a session.
                if self.session and not self.session.get('closed'):
                    return None
                for path in sorted(self.output.glob('*/session.json'),
                                   key=lambda p: p.stat().st_mtime, reverse=True):
                    view = json.loads(path.read_text())
                    if (view.get('state') == 'complete' and view.get('closed')
                            and len(view['takes']) == view['count']
                            and all((path.parent / f"{t['number']:02d}.wav").exists()
                                    for t in view['takes'])):
                        return {**view, 'saved_on_mac': len(view['takes'])}
                return None
            elif action == 'start':
                if self.session and not self.session.get('closed'):
                    raise ValueError('A session is already active')
                self.login()
                split = body.get('split', 'train')
                count = {'train': 12, 'val': 8, 'test': 8}.get(split)
                if count is None:
                    raise ValueError('Invalid split')
                self.session = self.request(f'/api/training/devices/{self.args.device}/sessions',
                                             {'split': split, 'count': count})
            elif action in ('heartbeat', 'close', 'tap') and self.session:
                sid = self.session['id']
                if body.get('session_id') != sid:
                    raise ValueError('This page belongs to a different session')
                if not self.session.get('closed'):
                    self.session = self.request(f'/api/training/sessions/{sid}/{action}', {})
            else:
                raise ValueError('No active session')
            return self.sync(dict(self.session))


HTML = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Teach Myshka · Echo recorder</title><style>
:root{font-family:system-ui;color:#e7edf7;background:#0c1423;color-scheme:dark}body{max-width:780px;margin:8vh auto;padding:24px}h1{font-size:clamp(32px,5vw,48px);margin:12px 0}p{line-height:1.65;color:#adbed6}.card{padding:30px;border:1px solid #283a52;border-radius:22px;background:#121f33}.tag{color:#65d9e9;letter-spacing:.08em;font-size:13px}#phrase{font-size:42px;color:white;margin:28px 0}button,select{padding:14px 22px;border-radius:12px;border:1px solid #486179;font:inherit}button{background:#5bd4e8;color:#071825;font-weight:700;cursor:pointer}button:disabled{opacity:.5;cursor:wait}select{margin:0 12px 12px 0;background:#182b41}progress{width:100%;height:12px;accent-color:#64e1b7}#status{font-size:23px;color:#fff}#error{color:#ffc085}.steps{padding-left:22px;line-height:1.9;color:#cbd7e8}small{color:#92a7c3}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:#62d5ed;margin-right:8px}</style>
<div class="tag">ECHOMUSE · __LABEL__</div><h1>Teach Myshka your voice</h1>
<p>Record directly from the Echo microphones. One phrase for the entire batch.</p>
<div class="card"><div class="tag">SAY ONLY THIS PHRASE</div><div id="phrase" lang="ru">Привет, Мышка</div>
<select id="split"><option value="train">Training · 12 takes</option><option value="val">Validation · 8 takes</option><option value="test">Final test · 8 takes</option></select>
<button id="action">Start session</button> <button id="end" hidden style="background:transparent;color:#adbed6">End session</button><p id="status">Ready when you are. Recording has not started.</p>
<progress id="progress" value="0" max="12"></progress><p id="count">0 recordings saved on this Mac</p><p id="error" role="alert"></p>
<ol class="steps"><li>Start the session here. Press Record on the Mac or tap the Dot's physical action button.</li><li>Wait for <b>two blue flashes</b>. The microphone stream is already ready.</li><li>Say <span lang="ru">«Привет, Мышка»</span> in your normal voice. Blue segments stay lit while recording.</li><li>Press Stop &amp; save on the Mac or tap the Dot button to stop. A green flash means the take was saved.</li><li>Press Record again whenever you are ready for the next take.</li></ol>
<small>No re-record or next-phrase buttons. Vary your natural intonation and position. Do not shout. Keep this page open; closing it ends an active session within 20 seconds. Each take is limited to 12 seconds; an unfinished take is discarded.</small></div>
<script>
const csrf='__CSRF__';let active=false,busy=false,currentState='idle',sessionId=null;
const statusEl=document.querySelector('#status'),button=document.querySelector('#action'),errorEl=document.querySelector('#error');
async function call(action,body={}){let r=await fetch('/api/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Recorder-CSRF':csrf},body:JSON.stringify({session_id:sessionId,...body})});let d=await r.json();if(!r.ok)throw Error(d.error||'Connection failed');if(d&&d.id)sessionId=d.id;return d;}
function render(s){active=!s.closed;currentState=s.state;button.textContent=active?(s.state==='recording'?'Stop & save':s.state==='armed'?'Record':'Please wait…'):'Start session';button.disabled=active&&!['armed','recording'].includes(s.state);document.querySelector('#end').hidden=!active;document.querySelector('#split').disabled=active;document.querySelector('#split').value=s.split;let n=s.takes.length;document.querySelector('#progress').max=s.count;document.querySelector('#progress').value=n;document.querySelector('#count').textContent=`${s.saved_on_mac} of ${s.count} recordings saved on this Mac`;let states={armed:`Take ${n+1}: press Record or tap the Dot button when ready.`,preparing:'Preparing the microphone. Wait for the blue flashes.',recording:'Recording — say the phrase, then press Stop & save or tap the Dot button.',saving:'Saving your take…',complete:'Batch saved. Take a break before the next batch.',error:'Session ended. Saved takes are safe.'};statusEl.textContent=states[s.state]||s.state;errorEl.textContent=s.error||'';}
button.onclick=async()=>{if(busy)return;busy=true;button.disabled=true;errorEl.textContent='';try{render(await call(active?'tap':'start',{split:document.querySelector('#split').value}));}catch(e){errorEl.textContent=e.message;}finally{busy=false;button.disabled=active&&!['armed','recording'].includes(currentState);}};
document.querySelector('#end').onclick=async()=>{if(busy)return;busy=true;try{render(await call('close'));}finally{busy=false;}};
setInterval(async()=>{if(!active||busy)return;busy=true;try{render(await call('heartbeat'));}catch(e){errorEl.textContent='Connection lost. Recording stops automatically if it cannot reconnect.';}finally{busy=false;}},1000);
busy=true;button.disabled=true;call('history').then(s=>{if(s)render(s);}).catch(()=>{}).finally(()=>{busy=false;button.disabled=false;});
</script></html>'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--credentials', type=Path, required=True)
    p.add_argument('--device', required=True)
    p.add_argument('--label', default='Echo Dot')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--port', type=int, default=8769)
    args=p.parse_args()
    os.umask(0o077)
    app=App(args)
    import html
    page=HTML.replace('__CSRF__',app.csrf).replace('__LABEL__',html.escape(args.label)).encode()
    expected=f'127.0.0.1:{args.port}'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass
        def reply(self,code,data,kind='application/json'):
            if kind=='application/json':data=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(code);self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'")
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            if self.headers.get('Host')!=expected or self.path!='/':
                return self.reply(404,{'error':'Not found'})
            return self.reply(200,page,'text/html; charset=utf-8')
        def do_POST(self):
            if (self.headers.get('Host')!=expected or
                self.headers.get('Origin') not in (None,'http://'+expected) or
                not secrets.compare_digest(self.headers.get('X-Recorder-CSRF',''),app.csrf)):
                return self.reply(403,{'error':'Forbidden'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=2048:raise ValueError('Invalid request size')
                body=json.loads(self.rfile.read(length))
                return self.reply(200,app.action(self.path.removeprefix('/api/'),body))
            except urllib.error.HTTPError as exc:
                return self.reply(409,{'error':f'Controller refused the request (HTTP {exc.code}). Check that the Dot is idle, connected and unmuted.'})
            except Exception:
                return self.reply(503,{'error':'Cannot complete the request. Saved takes are retained; an active recording expires automatically.'})
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Recorder ready at http://{expected}/ — no recording has started.',flush=True)
    try:server.serve_forever()
    finally:
        if app.session and not app.session.get('closed'):
            try:app.action('close',{'session_id':app.session['id']})
            except Exception:
                # If the Controller is unreachable, its bounded lease ends capture.
                pass
        if app.token:
            try:app.request('/api/auth/logout',{})
            except Exception:
                # Shutdown must complete even if logout cannot reach the Controller.
                pass
        server.server_close()

if __name__=='__main__':main()
