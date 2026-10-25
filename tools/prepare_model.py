"""Download inference weights at build time; the application never fetches documents remotely."""
from pathlib import Path
import hashlib,json,shutil,time,urllib.request
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'models'
MODEL_HASH='66fc00f5f29afcaff34092e1bdd20008ca3918265a82fb9695a551e510cc4ebc'
REPO='Xenova/paraphrase-multilingual-MiniLM-L12-v2'
def fetch(url,path,expected=None):
    if path.is_file() and (not expected or hashlib.sha256(path.read_bytes()).hexdigest()==expected): return
    req=urllib.request.Request(url+('?' if '?' not in url else '&')+'download=true&build='+str(int(time.time())),headers={'User-Agent':'SmartArchive/0.3'})
    tmp=path.with_suffix(path.suffix+'.part')
    try:
        with urllib.request.urlopen(req,timeout=240) as r,tmp.open('wb') as out: shutil.copyfileobj(r,out)
        if expected and hashlib.sha256(tmp.read_bytes()).hexdigest()!=expected: raise ValueError('Model checksum mismatch')
        tmp.replace(path)
    finally:tmp.unlink(missing_ok=True)
def main():
    DEST.mkdir(exist_ok=True)
    for remote,name,sha in [('onnx/model_quantized.onnx','model_quantized.onnx',MODEL_HASH),('tokenizer.json','tokenizer.json',None),('README.md','MODEL-CARD.md',None)]:
        fetch(f'https://huggingface.co/{REPO}/resolve/main/{remote}',DEST/name,sha)
    fetch('https://www.apache.org/licenses/LICENSE-2.0.txt',DEST/'LICENSE-APACHE-2.0.txt')
    (DEST/'ATTRIBUTION.txt').write_text('Multilingual MiniLM L12 v2. Original: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2. ONNX export: '+REPO+'. Apache-2.0.\n',encoding='utf8')
    (DEST/'CHECKSUMS.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.iterdir() if p.is_file() and p.name!='CHECKSUMS.json'},indent=2))
    print('Offline semantic model ready')
if __name__=='__main__':main()
