"""Build-time only: install Windows OCR in an isolated temp folder and bundle runtime."""
import hashlib,json,os,shutil,subprocess,tempfile,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'ocr'
def fetch(url,path):
    req=urllib.request.Request(url,headers={'User-Agent':'SmartArchive-build'})
    with urllib.request.urlopen(req,timeout=120) as r,path.open('wb') as out: shutil.copyfileobj(r,out)
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if os.name!='nt': raise SystemExit('Run on Windows')
    DEST.mkdir(exist_ok=True); manifest={}
    with tempfile.TemporaryDirectory(prefix='smartarchive-ocr-') as tmp:
        tmp=Path(tmp); installer=tmp/'ocr-setup.exe'; target=tmp/'installed'
        url='https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe'
        manifest['installer_sha256']=fetch(url,installer)
        result=subprocess.run([str(installer),'/S','/D='+str(target)],timeout=240)
        if result.returncode: raise RuntimeError('OCR installer failed')
        if not (target/'tesseract.exe').is_file(): raise RuntimeError('OCR executable not installed')
        shutil.copy2(target/'tesseract.exe',DEST/'tesseract.exe')
        for p in target.glob('*.dll'): shutil.copy2(p,DEST/p.name)
        # Preserve the included license notices and dependency documentation.
        for p in target.iterdir():
            if p.is_file() and p.suffix.lower() in {'.txt','.html','.md'}: shutil.copy2(p,DEST/p.name)
            elif p.is_dir() and p.name.lower() in {'doc','licenses','share'}: shutil.copytree(p,DEST/p.name,dirs_exist_ok=True)
    data=DEST/'tessdata';data.mkdir(exist_ok=True)
    for language in ('ara','eng'):
        url=f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/{language}.traineddata'
        manifest[language+'_sha256']=fetch(url,data/(language+'.traineddata'))
    fetch('https://raw.githubusercontent.com/tesseract-ocr/tesseract/main/LICENSE',DEST/'TESSERACT-LICENSE.txt')
    fetch('https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/LICENSE',DEST/'TESSDATA-LICENSE.txt')
    (DEST/'BUILD-MANIFEST.json').write_text(json.dumps(manifest,indent=2))
    subprocess.run([str(DEST/'tesseract.exe'),'--tessdata-dir',str(data),'--list-langs'],check=True)
    # The runtime must work without the installation directory or machine PATH.
    print('Bundled Arabic/English OCR ready:',DEST)
if __name__=='__main__': main()
