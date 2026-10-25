#!/usr/bin/env python3
"""WiFi Share v5 - every device is both a host and a client, like AirForShare.
Double-click this file (.pyw = no black cmd window, no extra window at all).
Your browser opens by itself and all devices running the app on the same Wi-Fi
appear automatically at the top of the page."""
import os, re, sys, io, json, time, uuid, shutil, socket, threading, argparse, webbrowser
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote, unquote

CHUNK = 1024 * 1024  # 1 MB pieces, so huge files never fill your RAM
SHARE_DIR = "shared"
LOCAL_IP = "127.0.0.1"
PORT = 8000
NODE_NAME = socket.gethostname()
NODE_ID = uuid.uuid4().hex[:8]
DISCOVERY_PORT = 48555
SCAN_PORTS = range(8000, 8004)  # ports the subnet scanner checks
PEER_TTL = 20  # seconds before a silent device disappears from the list
PEERS = {}  # other devices found on the Wi-Fi
note = ""
lock = threading.Lock()

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>WiFi Share</title>
<style>
:root{--bg:#f3f5fb;--card:#fff;--txt:#1b2236;--mut:#6c7589;--pri:#4f46e5;--pri2:#7c3aed;--bd:#dfe4f1;--ok:#16a34a;--bad:#dc2626}
@media(prefers-color-scheme:dark){:root{--bg:#10121a;--card:#1a1d29;--txt:#e9ecf5;--mut:#98a0b5;--bd:#2c3144}}
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--txt)}
button{font-family:inherit}
header{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--bd)}
.in{max-width:860px;margin:auto;padding:12px 16px;display:flex;align-items:center;justify-content:space-between;gap:10px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:20px;white-space:nowrap}
.logo{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,var(--pri),var(--pri2));display:grid;place-items:center;font-size:18px;flex:none}
.right{display:flex;align-items:center;gap:8px}
.ib{width:38px;height:38px;border-radius:50%;border:1px solid var(--bd);background:var(--bg);color:var(--txt);font-size:17px;cursor:pointer}
.tabs{display:flex;background:var(--bg);border:1px solid var(--bd);border-radius:12px;padding:4px}
.tabs button{background:none;color:var(--mut);border:0;padding:8px 16px;border-radius:9px;font-size:15px;font-weight:600;cursor:pointer}
.tabs button.on{background:var(--pri);color:#fff}
@media(max-width:520px){.brand span{display:none}.tabs button{padding:8px 12px}}
main{max-width:860px;margin:auto;padding:16px 16px 120px}
.devs{display:flex;gap:8px;overflow-x:auto;padding-bottom:6px;margin-bottom:12px}
.dev{flex:none;display:flex;align-items:center;gap:8px;background:var(--card);color:var(--txt);border:2px solid var(--bd);border-radius:999px;padding:8px 14px;font-size:14px;font-weight:600;cursor:pointer}
.dev.on{background:var(--pri);border-color:var(--pri);color:#fff}
.dot{width:8px;height:8px;border-radius:50%;background:var(--ok)}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between;margin-bottom:14px}
.crumbs{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:15px}
.crumbs a{color:var(--pri);cursor:pointer;font-weight:600}.crumbs span{color:var(--mut)}
.tools{display:flex;gap:8px;flex-wrap:wrap}
.btn{background:var(--card);color:var(--pri);border:1.5px solid var(--pri);border-radius:999px;padding:7px 14px;font-size:14px;font-weight:600;cursor:pointer}
.row{display:flex;align-items:center;gap:12px;background:var(--card);border:2px solid var(--bd);border-radius:999px;padding:8px 10px 8px 12px;margin-bottom:10px;transition:border-color .15s}
.row:hover{border-color:var(--pri)}.row.dir{cursor:pointer}
.ic{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;font-size:20px;background:var(--bg);flex:none}
.nm{flex:1;min-width:0}.nm b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600}
.nm small{color:var(--mut)}
.dl{width:40px;height:40px;border-radius:50%;background:var(--pri);color:#fff;display:grid;place-items:center;text-decoration:none;flex:none;font-size:18px}
.x{width:32px;height:32px;border-radius:50%;border:0;background:transparent;color:var(--bad);cursor:pointer;font-size:16px;flex:none}
.chev{color:var(--mut);font-size:22px;padding-right:8px}
.empty{text-align:center;color:var(--mut);padding:50px 10px;border:2px dashed var(--bd);border-radius:20px}
.fab{position:fixed;right:max(16px,env(safe-area-inset-right));bottom:max(16px,env(safe-area-inset-bottom));background:linear-gradient(135deg,var(--pri),var(--pri2));color:#fff;border:0;border-radius:999px;padding:15px 24px;font-size:16px;font-weight:700;box-shadow:0 8px 24px rgba(79,70,229,.4);cursor:pointer;z-index:6}
.note{background:var(--card);border:2px solid var(--bd);border-radius:20px;padding:14px}
.note:focus-within{border-color:var(--pri)}
textarea{width:100%;height:min(55vh,440px);resize:vertical;border:0;outline:0;background:transparent;color:var(--txt);font-size:16px;line-height:1.55;font-family:inherit}
.acts{display:flex;align-items:center;gap:12px;margin-top:12px;flex-wrap:wrap}
.seg{display:flex;border:2px solid var(--pri);border-radius:12px;overflow:hidden}
.seg button{background:var(--card);color:var(--pri);border:0;padding:10px 22px;font-size:15px;font-weight:700;cursor:pointer}
.seg button+button{border-left:2px solid var(--pri)}.seg button.p{background:var(--pri);color:#fff}
#st{color:var(--mut);font-size:14px}
#ups{position:fixed;right:max(16px,env(safe-area-inset-right));bottom:84px;width:min(360px,calc(100vw - 32px));z-index:7;display:flex;flex-direction:column;gap:8px}
.up{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:10px 12px;box-shadow:0 6px 20px rgba(0,0,0,.15);font-size:14px}
.up b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pb{height:6px;background:var(--bd);border-radius:4px;margin:6px 0 4px;overflow:hidden}
.pb i{display:block;height:100%;width:0;background:var(--pri);transition:width .2s}
.up small{color:var(--mut)}.up.fail small{color:var(--bad)}.up.done small{color:var(--ok)}
#ov{position:fixed;inset:0;background:rgba(79,70,229,.88);color:#fff;display:grid;place-items:center;font-size:24px;font-weight:700;z-index:20;pointer-events:none}
#dlg{position:fixed;inset:0;background:rgba(0,0,0,.55);display:grid;place-items:center;z-index:30;padding:16px}
.dbox{background:var(--card);border-radius:20px;padding:22px;width:min(380px,100%);text-align:center}
.dbox h2{margin:0 0 6px;font-size:19px}.dbox p{color:var(--mut);font-size:14px;margin:6px 0 14px}
#qr{width:200px;height:200px;background:#fff;padding:8px;border-radius:12px;margin:0 auto 10px;display:block}
.addr{font:600 17px ui-monospace,Consolas,monospace;word-break:break-all;margin-bottom:14px}
.dbox .acts{justify-content:center}
</style></head><body>
<header><div class="in">
  <div class="brand"><div class="logo">📡</div><span>WiFi Share</span></div>
  <div class="right">
    <button class="ib" id="bConn" title="Connect a phone or another device">📱</button>
    <button class="ib" id="bQuit" title="Quit the app on this device" hidden>⏻</button>
    <div class="tabs"><button id="tText">Text</button><button id="tFiles" class="on">Files</button></div>
  </div>
</div></header>

<main>
  <div class="devs" id="devs"></div>

  <section id="vFiles">
    <div class="bar">
      <div class="crumbs" id="crumbs"></div>
      <div class="tools">
        <button class="btn" id="bNew">＋ New folder</button>
        <button class="btn" id="bDir">⇪ Upload folder</button>
      </div>
    </div>
    <div id="list"></div>
  </section>

  <section id="vText" hidden>
    <div class="note">
      <textarea id="note" placeholder="Type or paste text here. Everyone on this Wi-Fi can see it."></textarea>
      <div class="acts">
        <div class="seg"><button class="p" id="bSave">Save</button><button id="bClear">Clear</button></div>
        <button class="btn" id="bCopy">Copy</button>
        <span id="st"></span>
      </div>
    </div>
  </section>
</main>

<button class="fab" id="fab">＋ Add Files</button>
<div id="ups"></div>
<div id="ov" hidden>Drop files or folders to share</div>
<div id="dlg" hidden><div class="dbox">
  <h2>Connect a phone or device</h2>
  <p>Scan this code, or open the address. Computers that run WiFi Share appear on their own, so this is only needed for devices without the app.</p>
  <img id="qr" alt="QR code" hidden>
  <div class="addr" id="addr"></div>
  <div class="acts"><button class="btn" id="aCopy">Copy address</button><button class="btn" id="aClose">Close</button></div>
</div></div>
<input type="file" id="pick" multiple hidden>
<input type="file" id="pickDir" webkitdirectory hidden>

<script>
const $=s=>document.querySelector(s);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>{const u=['B','KB','MB','GB','TB'];let i=0;while(n>=1024&&i<4){n/=1024;i++}return n.toFixed(i?1:0)+' '+u[i]};
const url=rel=>'/files/'+rel.split('/').map(encodeURIComponent).join('/');
const ICONS={pdf:'📕',doc:'📘',docx:'📘',xls:'📗',xlsx:'📗',csv:'📗',ppt:'📙',pptx:'📙',
  png:'🖼️',jpg:'🖼️',jpeg:'🖼️',gif:'🖼️',webp:'🖼️',svg:'🖼️',mp4:'🎬',mkv:'🎬',mov:'🎬',avi:'🎬',webm:'🎬',
  mp3:'🎵',wav:'🎵',m4a:'🎵',zip:'🗜️',rar:'🗜️','7z':'🗜️',json:'🧾',txt:'📄',py:'🐍',apk:'📱',exe:'⚙️'};
const icon=n=>ICONS[(n.split('.').pop()||'').toLowerCase()]||'📄';
function copyText(t){
  if(navigator.clipboard&&window.isSecureContext)navigator.clipboard.writeText(t);
  else{const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}
}
/* base = which device we are looking at: '' = the device serving this page, otherwise http://ip:port of another device */
let base='',cur='',tab='files',dirty=false,lastJson='',devSig='',selfUrl='';
function refresh(){tab==='files'?loadFiles():loadNote()}

/* ---------- devices ---------- */
async function loadPeers(){
  try{
    const r=await(await fetch('/api/peers')).json();
    selfUrl=r.self.url;$('#bQuit').hidden=!r.self.host;
    const list=[{key:'',name:r.self.name+(r.self.host?' (this device)':'')}]
      .concat(r.peers.map(p=>({key:'http://'+p.ip+':'+p.port,name:p.name})));
    if(!list.some(d=>d.key===base)){base='';cur='';lastJson='';refresh()}
    const sig=JSON.stringify([list,base]);if(sig===devSig)return;devSig=sig;
    $('#devs').innerHTML=list.map(d=>`<button class="dev${d.key===base?' on':''}" data-key="${esc(d.key)}"><span class="dot"></span>${esc(d.name)}</button>`).join('');
  }catch(e){}
}
$('#devs').onclick=e=>{
  const b=e.target.closest('[data-key]');if(!b||b.dataset.key===base)return;
  base=b.dataset.key;cur='';lastJson='';dirty=false;devSig='';
  $('#note').value='';$('#st').textContent='';refresh();loadPeers();
};

/* ---------- connect dialog and quit ---------- */
$('#bConn').onclick=()=>{
  $('#addr').textContent=selfUrl;const q=$('#qr');q.hidden=false;q.src='/api/qr.svg?'+Date.now();$('#dlg').hidden=false;
};
$('#qr').onerror=()=>{$('#qr').hidden=true};
$('#aClose').onclick=()=>$('#dlg').hidden=true;
$('#dlg').onclick=e=>{if(e.target.id==='dlg')$('#dlg').hidden=true};
$('#aCopy').onclick=()=>{copyText(selfUrl);$('#aCopy').textContent='Copied ✓';setTimeout(()=>$('#aCopy').textContent='Copy address',1500)};
let timer;
$('#bQuit').onclick=async()=>{
  if(!confirm('Stop sharing and close WiFi Share on this device?'))return;
  clearInterval(timer);
  try{await fetch('/api/quit',{method:'POST'})}catch(e){}
  document.body.innerHTML='<div style="display:grid;place-items:center;height:100vh;font:20px system-ui;text-align:center;color:#6c7589">WiFi Share has stopped.<br>You can close this tab.</div>';
};

/* ---------- tabs ---------- */
function setTab(t){
  tab=t;history.replaceState(null,'','#'+t);
  $('#vFiles').hidden=t!=='files';$('#vText').hidden=t!=='text';$('#fab').hidden=t!=='files';
  $('#tFiles').classList.toggle('on',t==='files');$('#tText').classList.toggle('on',t==='text');
  refresh();
}
$('#tFiles').onclick=()=>setTab('files');$('#tText').onclick=()=>setTab('text');

/* ---------- files ---------- */
async function loadFiles(){
  const b=base;
  try{
    const r=await(await fetch(b+'/api/list?path='+encodeURIComponent(cur))).json();
    if(b!==base)return;
    if(r.error){if(cur){cur='';lastJson='';return loadFiles()}return}
    const j=JSON.stringify([b,cur,r]);if(j===lastJson)return;lastJson=j;render(r);
  }catch(e){
    if(b===base&&b){lastJson='';$('#list').innerHTML='<div class="empty">Cannot reach this device right now.</div>'}
  }
}
function render(r){
  const parts=cur?cur.split('/'):[];
  $('#crumbs').innerHTML='<a data-go="">🏠 Home</a>'+parts.map((p,i)=>
    ' <span>›</span> <a data-go="'+esc(parts.slice(0,i+1).join('/'))+'">'+esc(p)+'</a>').join('');
  $('#list').innerHTML=r.items.map(it=>{
    const rel=(cur?cur+'/':'')+it.name;
    const del=r.host?`<button class="x" data-del="${esc(rel)}" title="Delete">✕</button>`:'';
    if(it.type==='dir')return `<div class="row dir" data-open="${esc(rel)}"><div class="ic">📁</div>
      <div class="nm"><b>${esc(it.name)}</b><small>${it.count} item${it.count==1?'':'s'}</small></div>${del}<span class="chev">›</span></div>`;
    return `<div class="row"><div class="ic">${icon(it.name)}</div>
      <div class="nm"><b>${esc(it.name)}</b><small>${fmt(it.size)} · ${new Date(it.mtime*1000).toLocaleString()}</small></div>${del}
      <a class="dl" title="Download" href="${esc(base+url(rel))}" download="${esc(it.name)}">⬇</a></div>`;
  }).join('')||'<div class="empty">Nothing here yet.<br>Tap <b>Add Files</b> to share something.</div>';
}
$('#crumbs').onclick=e=>{const a=e.target.closest('[data-go]');if(a){cur=a.dataset.go;lastJson='';loadFiles()}};
$('#list').onclick=async e=>{
  const d=e.target.closest('[data-del]');
  if(d){if(confirm('Delete "'+d.dataset.del.split('/').pop()+'"?')){
    await fetch(base+'/api/delete?path='+encodeURIComponent(d.dataset.del),{method:'POST'});lastJson='';loadFiles()}return}
  const o=e.target.closest('[data-open]');if(o&&!e.target.closest('a')){cur=o.dataset.open;lastJson='';loadFiles()}
};
$('#bNew').onclick=async()=>{
  const n=prompt('Folder name');if(!n||!n.trim())return;
  await fetch(base+'/api/mkdir?path='+encodeURIComponent(cur)+'&name='+encodeURIComponent(n.trim()),{method:'POST'});
  lastJson='';loadFiles();
};

/* ---------- uploads (3 at a time, with progress) ---------- */
const queue=[];let running=0;
function upload(file,rel){
  const el=document.createElement('div');el.className='up';
  el.innerHTML=`<b>${esc(rel)}</b><div class="pb"><i></i></div><small>Waiting...</small>`;
  $('#ups').appendChild(el);queue.push({file,rel,el,path:cur,base});pump();
}
function pump(){while(running<3&&queue.length){const j=queue.shift();running++;send(j).then(()=>{running--;pump()})}}
function send(j){
  return new Promise(res=>{
    const x=new XMLHttpRequest(),bar=j.el.querySelector('i'),st=j.el.querySelector('small');
    x.open('PUT',j.base+'/upload?path='+encodeURIComponent(j.path)+'&name='+encodeURIComponent(j.rel));
    x.upload.onprogress=e=>{if(e.lengthComputable){const p=Math.round(e.loaded/e.total*100);
      bar.style.width=p+'%';st.textContent=p+'%  ('+fmt(e.loaded)+' / '+fmt(e.total)+')'}};
    x.onload=()=>{const ok=x.status===200;j.el.classList.add(ok?'done':'fail');
      st.textContent=ok?'Done ✓':'Failed ✗';bar.style.width='100%';
      if(ok)setTimeout(()=>j.el.remove(),3500);lastJson='';loadFiles();res()};
    x.onerror=()=>{j.el.classList.add('fail');st.textContent='Failed ✗ (connection lost)';res()};
    x.send(j.file);
  });
}
$('#fab').onclick=()=>$('#pick').click();
$('#bDir').onclick=()=>$('#pickDir').click();
$('#pick').onchange=e=>{[...e.target.files].forEach(f=>upload(f,f.name));e.target.value=''};
$('#pickDir').onchange=e=>{[...e.target.files].forEach(f=>upload(f,f.webkitRelativePath||f.name));e.target.value=''};

/* ---------- drag & drop (files and whole folders) ---------- */
async function walk(en,prefix,out){
  if(en.isFile){await new Promise(r=>en.file(f=>{out.push({f,rel:prefix+f.name});r()},r))}
  else if(en.isDirectory){
    const rd=en.createReader();let all=[];
    for(;;){const b=await new Promise((a,z)=>rd.readEntries(a,z));if(!b.length)break;all=all.concat(b)}
    for(const c of all)await walk(c,prefix+en.name+'/',out);
  }
}
let dc=0;const hasFiles=e=>e.dataTransfer&&[...e.dataTransfer.types].includes('Files');
addEventListener('dragenter',e=>{if(hasFiles(e)){e.preventDefault();dc++;$('#ov').hidden=false}});
addEventListener('dragleave',e=>{if(hasFiles(e)){dc--;if(dc<=0){dc=0;$('#ov').hidden=true}}});
addEventListener('dragover',e=>{if(hasFiles(e))e.preventDefault()});
addEventListener('drop',async e=>{
  if(!hasFiles(e))return;e.preventDefault();dc=0;$('#ov').hidden=true;
  if(tab!=='files')setTab('files');
  const ents=[...e.dataTransfer.items].map(i=>i.webkitGetAsEntry&&i.webkitGetAsEntry()).filter(Boolean);
  if(ents.length){const out=[];for(const en of ents)await walk(en,'',out);out.forEach(x=>upload(x.f,x.rel))}
  else[...e.dataTransfer.files].forEach(f=>upload(f,f.name));
});

/* ---------- shared text ---------- */
const setSt=s=>$('#st').textContent=s;
async function loadNote(){
  const b=base;
  try{const r=await(await fetch(b+'/api/note')).json();
    if(b===base&&!dirty&&$('#note').value!==r.text)$('#note').value=r.text}catch(e){}
}
async function saveNote(){
  await fetch(base+'/api/note',{method:'POST',body:JSON.stringify({text:$('#note').value})});
  dirty=false;setSt('Saved ✓  Everyone can see it now');
}
$('#note').oninput=()=>{dirty=true;setSt('Not saved yet')};
$('#note').onkeydown=e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();saveNote()}};
$('#bSave').onclick=saveNote;
$('#bClear').onclick=async()=>{$('#note').value='';await saveNote();setSt('Cleared ✓')};
$('#bCopy').onclick=()=>{copyText($('#note').value);setSt('Copied ✓')};

setTab(location.hash==='#text'?'text':'files');
loadPeers();
timer=setInterval(()=>{refresh();loadPeers()},3000);
</script></body></html>"""


# ---------------------------------------------------------------- helpers
def clean(name):
    """Make one file or folder name safe on every operating system."""
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip()
    if name.startswith("."):
        name = "_" + name.lstrip(".")
    if name.endswith(".part"):
        name += "_"
    return name or "file"


def resolve(rel):
    """Turn a relative path into a real path that is guaranteed to stay inside the shared folder."""
    parts = [p for p in rel.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return None
    root = os.path.abspath(SHARE_DIR)
    full = os.path.abspath(os.path.join(root, *parts))
    if full != root and not full.startswith(root + os.sep):
        return None
    return full


def visible(n):
    return not n.startswith(".") and not n.endswith(".part")


def unique_path(folder, name):
    base, ext = os.path.splitext(name)
    path, i = os.path.join(folder, name), 1
    while os.path.exists(path) or os.path.exists(path + ".part"):
        path = os.path.join(folder, f"{base} ({i}){ext}")
        i += 1
    return path


def note_path():
    return os.path.join(SHARE_DIR, ".note.txt")


def add_peer(pid, name, ip, port):
    if pid == NODE_ID:
        return
    with lock:
        PEERS[pid] = {"id": pid, "name": str(name)[:40], "ip": ip, "port": int(port), "seen": time.time()}


def qr_svg(text):
    """Returns a QR code as SVG, or None if the optional 'qrcode' package is missing."""
    try:
        import qrcode
        import qrcode.image.svg
        img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, border=1)
        buf = io.BytesIO()
        img.save(buf)
        return buf.getvalue()
    except Exception:
        return None


# ---------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def is_host(self):
        return self.client_address[0] in ("127.0.0.1", "::1", LOCAL_IP)

    def cors(self):  # lets the page on one device talk to the server on another device
        self.send_header("Access-Control-Allow-Origin", "*")

    def send_bytes(self, data, ctype="application/json", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.cors()
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj, code=200):
        self.send_bytes(json.dumps(obj).encode(), code=code)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---- GET
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self.send_bytes(PAGE.encode(), "text/html; charset=utf-8")
        elif u.path == "/api/ping":
            self.send_json({"app": "wifishare", "id": NODE_ID, "name": NODE_NAME, "port": PORT})
        elif u.path == "/api/qr.svg":
            svg = qr_svg(f"http://{LOCAL_IP}:{PORT}")
            if svg:
                self.send_bytes(svg, "image/svg+xml")
            else:
                self.send_bytes(b"no qr", "text/plain", 404)
        elif u.path == "/api/list":
            d = resolve(parse_qs(u.query).get("path", [""])[0])
            if not d or not os.path.isdir(d):
                return self.send_json({"error": "not found"}, 404)
            items = []
            for n in os.listdir(d):
                if not visible(n):
                    continue
                p = os.path.join(d, n)
                try:
                    s = os.stat(p)
                    if os.path.isdir(p):
                        count = sum(1 for x in os.listdir(p) if visible(x))
                        items.append({"name": n, "type": "dir", "count": count, "mtime": s.st_mtime})
                    else:
                        items.append({"name": n, "type": "file", "size": s.st_size, "mtime": s.st_mtime})
                except OSError:
                    continue
            items.sort(key=lambda i: (0, i["name"].lower()) if i["type"] == "dir" else (1, -i["mtime"]))
            self.send_json({"items": items, "host": self.is_host()})
        elif u.path == "/api/peers":
            now = time.time()
            with lock:
                peers = [{"id": p["id"], "name": p["name"], "ip": p["ip"], "port": p["port"]}
                         for p in PEERS.values() if now - p["seen"] < PEER_TTL]
            peers.sort(key=lambda p: p["name"].lower())
            self.send_json({"self": {"name": NODE_NAME, "port": PORT, "host": self.is_host(),
                                     "url": f"http://{LOCAL_IP}:{PORT}"},
                            "peers": peers})
        elif u.path == "/api/note":
            with lock:
                self.send_json({"text": note})
        elif u.path.startswith("/files/"):
            p = resolve(unquote(u.path[7:]))
            if p and os.path.isfile(p) and visible(os.path.basename(p)):
                self.serve_file(p)
            else:
                self.send_bytes(b"Not found", "text/plain", 404)
        else:
            self.send_bytes(b"Not found", "text/plain", 404)

    def serve_file(self, path):
        name = os.path.basename(path)
        total = os.path.getsize(path)
        start, end, code = 0, total - 1, 200
        rng = self.headers.get("Range", "")
        if rng.startswith("bytes=") and total:  # lets videos seek and downloads resume
            try:
                a, b = rng[6:].split("-", 1)
                start = int(a) if a else max(total - int(b), 0)
                end = int(b) if (a and b) else total - 1
                end = min(end, total - 1)
                code = 206
            except ValueError:
                start, end, code = 0, total - 1, 200
        length = max(end - start + 1, 0)
        self.send_response(code)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(name))
        self.cors()
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                left = length
                while left > 0:
                    buf = f.read(min(CHUNK, left))
                    if not buf:
                        break
                    self.wfile.write(buf)
                    left -= len(buf)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---- PUT (file upload, streamed to disk in 1 MB pieces)
    def do_PUT(self):
        u = urlparse(self.path)
        if u.path != "/upload":
            return self.send_bytes(b"Not found", "text/plain", 404)
        q = parse_qs(u.query)
        base = resolve(q.get("path", [""])[0])
        raw = q.get("name", ["file"])[0].replace("\\", "/")
        parts = [clean(p) for p in raw.split("/") if p not in ("", ".", "..")] or ["file"]
        if not base or not os.path.isdir(base):
            self.close_connection = True
            return self.send_json({"error": "bad folder"}, 400)
        left = int(self.headers.get("Content-Length", 0))
        folder = os.path.join(base, *parts[:-1])
        os.makedirs(folder, exist_ok=True)
        with lock:
            final = unique_path(folder, parts[-1])
            tmp = final + ".part"
            open(tmp, "wb").close()  # reserve the name
        try:
            with open(tmp, "wb") as f:
                while left > 0:
                    buf = self.rfile.read(min(CHUNK, left))
                    if not buf:
                        raise ConnectionError("upload interrupted")
                    f.write(buf)
                    left -= len(buf)
            os.replace(tmp, final)
            self.send_json({"ok": True})
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            self.close_connection = True

    # ---- POST
    def do_POST(self):
        global note
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/note":
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
            with lock:
                note = str(data.get("text", ""))[:1_000_000]
                try:
                    with open(note_path(), "w", encoding="utf-8") as f:
                        f.write(note)
                except OSError:
                    pass
            return self.send_json({"ok": True})
        if u.path == "/api/mkdir":
            base = resolve(q.get("path", [""])[0])
            if base and os.path.isdir(base):
                os.makedirs(os.path.join(base, clean(q.get("name", ["folder"])[0])), exist_ok=True)
            return self.send_json({"ok": True})
        if not self.is_host():  # only the owner of this device can delete or quit
            return self.send_json({"error": "host only"}, 403)
        if u.path == "/api/delete":
            p = resolve(q.get("path", [""])[0])
            if p and p != os.path.abspath(SHARE_DIR):
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                elif os.path.isfile(p):
                    os.remove(p)
            return self.send_json({"ok": True})
        if u.path == "/api/quit":
            self.send_json({"ok": True})
            threading.Timer(0.4, lambda: os._exit(0)).start()
            return
        self.send_bytes(b"Not found", "text/plain", 404)


class Server(ThreadingHTTPServer):
    # On Windows, "reuse address" lets two apps share one port, so keep it off there
    allow_reuse_address = os.name != "nt"
    daemon_threads = True


def make_server(port):
    for p in range(port, port + 20):  # if 8000 is busy, try 8001, 8002, ...
        try:
            return Server(("0.0.0.0", p), Handler), p
        except OSError:
            continue
    raise OSError("No free port found")


def find_running(port):
    """If WiFi Share is already running on this device, return its address."""
    for p in range(port, port + 20):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{p}/api/ping", timeout=0.4) as r:
                if json.loads(r.read().decode()).get("app") == "wifishare":
                    return f"http://localhost:{p}"
        except Exception:
            continue
    return None


# ---------------------------------------------------------------- finding other devices
def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no data is sent; just finds your Wi-Fi address
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def start_discovery():
    """Two ways to find other devices, so it still works if one is blocked:
    1) every device shouts 'I am here' (UDP broadcast) and listens for others
    2) every few seconds the app also knocks on its own Wi-Fi neighbours"""
    def listen():
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        try:
            rx.bind(("", DISCOVERY_PORT))
        except OSError:
            return
        while True:
            try:
                data, addr = rx.recvfrom(2048)
                m = json.loads(data.decode())
                if m.get("app") == "wifishare":
                    add_peer(m["id"], m.get("name", "device"), addr[0], m["port"])
            except Exception:
                pass

    def announce():
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tx.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        msg = json.dumps({"app": "wifishare", "id": NODE_ID, "name": NODE_NAME, "port": PORT}).encode()
        targets = {"255.255.255.255"}
        if LOCAL_IP.count(".") == 3:
            targets.add(LOCAL_IP.rsplit(".", 1)[0] + ".255")
        while True:
            for t in targets:
                try:
                    tx.sendto(msg, (t, DISCOVERY_PORT))
                except OSError:
                    pass
            time.sleep(2)

    def probe(target):
        ip, port = target
        try:
            with urllib.request.urlopen(f"http://{ip}:{port}/api/ping", timeout=0.7) as r:
                m = json.loads(r.read().decode())
            if m.get("app") == "wifishare":
                add_peer(m["id"], m.get("name", "device"), ip, m["port"])
        except Exception:
            pass

    def scan():
        if LOCAL_IP.count(".") != 3 or LOCAL_IP.startswith("127."):
            return
        prefix = LOCAL_IP.rsplit(".", 1)[0]
        targets = [(f"{prefix}.{i}", p) for i in range(1, 255) for p in SCAN_PORTS]
        with ThreadPoolExecutor(max_workers=128) as pool:
            while True:
                list(pool.map(probe, targets))
                time.sleep(6)

    for fn in (listen, announce, scan):
        threading.Thread(target=fn, daemon=True).start()


def main():
    global SHARE_DIR, LOCAL_IP, PORT, note
    if sys.stdout is None:  # started by double-click without a console
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    ap = argparse.ArgumentParser(description="Share files and text over Wi-Fi")
    ap.add_argument("-d", "--dir", default="shared", help="folder to share (default: shared)")
    ap.add_argument("-p", "--port", type=int, default=8000, help="port (default: 8000)")
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    ap.add_argument("--new", action="store_true", help="start a second copy even if one is running")
    a = ap.parse_args()

    if not a.new:  # already running? just open it again instead of starting a second copy
        running = find_running(a.port)
        if running:
            if not a.no_browser:
                webbrowser.open(running)
            return

    SHARE_DIR = a.dir
    os.makedirs(SHARE_DIR, exist_ok=True)
    try:
        with open(note_path(), encoding="utf-8") as f:
            note = f.read()
    except OSError:
        pass

    LOCAL_IP = local_ip()
    server, PORT = make_server(a.port)
    start_discovery()
    print(f"WiFi Share is running\n  This device : http://localhost:{PORT}\n  Other devices: http://{LOCAL_IP}:{PORT}")
    if not a.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        try:
            import tkinter as tk
            from tkinter import messagebox
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror("WiFi Share", f"Could not start:\n{ex}")
        except Exception:
            raise