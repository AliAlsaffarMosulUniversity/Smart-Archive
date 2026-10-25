"""Offline Ed25519 licensing. Private signing key is never bundled."""
from __future__ import annotations
import base64, ctypes, hashlib, json, os, sys, uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

TRIAL_DAYS=30
PRODUCT='smart-archive-v1'
PUBLIC_KEY='PBExsFMNeAYn9FR_GV7EphcBUKi9lHixm9Bo_xu159Y'

def utcnow(): return datetime.now(timezone.utc)
def stamp(t): return t.isoformat()
def parse(s):
    t=datetime.fromisoformat(s)
    if t.tzinfo is None: raise ValueError('وقت غير صالح')
    return t

def device_id():
    if sys.platform!='win32': raise RuntimeError('نظام الترخيص مخصص لويندوز')
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as k:
        machine=winreg.QueryValueEx(k,'MachineGuid')[0]
    return hashlib.sha256((PRODUCT+'|'+machine).encode()).hexdigest().upper()[:32]

class LicenseError(Exception): pass

def b64(data): return base64.urlsafe_b64encode(data).decode().rstrip('=')
def unb64(s): return base64.urlsafe_b64decode(s+'='*((-len(s))%4))

def verify_token(token,device,public_key=PUBLIC_KEY,now=None):
    try:
        payload,signature=token.strip().split('.')
        raw=unb64(payload)
        Ed25519PublicKey.from_public_bytes(unb64(public_key)).verify(unb64(signature),raw)
        data=json.loads(raw)
        if data.get('product')!=PRODUCT or data.get('device')!=device: raise ValueError('رمز لمنتج أو جهاز آخر')
        if data.get('type')!='perpetual': raise ValueError('نوع ترخيص غير مدعوم')
        if parse(data['issued'])>(now or utcnow())+timedelta(minutes=5): raise ValueError('تاريخ الرمز مستقبلي')
        return data
    except Exception as e: raise LicenseError('رمز التفعيل غير صالح لهذا الجهاز أو تم تغييره') from e

class Blob(ctypes.Structure):
    _fields_=[('size',ctypes.c_ulong),('data',ctypes.POINTER(ctypes.c_ubyte))]

def dpapi(data,decrypt=False):
    if sys.platform!='win32': raise LicenseError('حفظ الترخيص يتطلب Windows')
    buffer=ctypes.create_string_buffer(data)
    incoming=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte))); outgoing=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True); kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p]; kernel.LocalFree.restype=ctypes.c_void_p
    crypt.CryptProtectData.argtypes=[ctypes.POINTER(Blob),ctypes.c_wchar_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(Blob)]
    crypt.CryptProtectData.restype=ctypes.c_int
    crypt.CryptUnprotectData.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(Blob)]
    crypt.CryptUnprotectData.restype=ctypes.c_int
    if decrypt: ok=crypt.CryptUnprotectData(ctypes.byref(incoming),None,None,None,None,1,ctypes.byref(outgoing))
    else: ok=crypt.CryptProtectData(ctypes.byref(incoming),'SmartArchive',None,None,None,1,ctypes.byref(outgoing))
    if not ok: raise LicenseError('تعذر التحقق من بيانات الترخيص المحمية')
    try: return ctypes.string_at(outgoing.data,outgoing.size)
    finally: kernel.LocalFree(ctypes.cast(outgoing.data,ctypes.c_void_p))

class WindowsStore:
    """Per-Windows-user state, mirrored in registry to survive normal reinstall."""
    def __init__(self):
        self.path=Path(os.environ['LOCALAPPDATA'])/'SmartArchive'/'license-state.bin'
    def read(self):
        import winreg
        blobs=[]
        if self.path.exists(): blobs.append(self.path.read_bytes())
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\SmartArchive\Licensing') as k: blobs.append(winreg.QueryValueEx(k,'State')[0])
        except FileNotFoundError: pass
        if not blobs: return None
        states=[]
        try:
            for blob in blobs: states.append(json.loads(dpapi(blob,True)))
            for s in states:
                parse(s['first']); parse(s['last'])
                if s['device']!=device_id(): raise ValueError('جهاز مختلف')
            # Prefer earliest trial start and most recent observed clock; token signatures checked later.
            result=dict(max(states,key=lambda s:parse(s['last'])))
            result['first']=min(s['first'] for s in states)
            tokens={s.get('token','') for s in states if s.get('token')}
            if tokens: result['token']=next(iter(tokens))
            return result
        except Exception as e: raise LicenseError('بيانات الترخيص تالفة أو لا تخص حساب Windows الحالي. استخدم رمز تفعيل صالح.') from e
    def write(self,state):
        import winreg
        blob=dpapi(json.dumps(state).encode())
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_name('license-'+uuid.uuid4().hex+'.tmp')
        try:
            with open(tmp,'xb') as f: f.write(blob); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,self.path)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\SmartArchive\Licensing') as k: winreg.SetValueEx(k,'State',0,winreg.REG_BINARY,blob)
        finally: tmp.unlink(missing_ok=True)

class Licensing:
    def __init__(self,store=None,device=None,public_key=PUBLIC_KEY,clock=utcnow):
        self.store=store if store is not None else WindowsStore()
        self.device=device if device is not None else device_id(); self.public_key=public_key; self.clock=clock
    def check(self):
        now=self.clock(); state=self.store.read()
        if state is None:
            state={'first':stamp(now),'last':stamp(now),'device':self.device,'token':''}; self.store.write(state)
        if state.get('device')!=self.device: raise LicenseError('بيانات تخص جهازًا آخر')
        if state.get('token'):
            data=verify_token(state['token'],self.device,self.public_key,now)
            return {'active':True,'licensed':True,'days':None,'customer':data.get('customer','')}
        if now<parse(state['last'])-timedelta(minutes=5): raise LicenseError('تم رصد إرجاع ساعة الجهاز. صحح الوقت أو فعّل البرنامج.')
        first=parse(state['first']); last=parse(state['last'])
        if first>last or first>now+timedelta(minutes=5): raise LicenseError('تاريخ بداية غير صالح')
        state['last']=stamp(max(now,last)); self.store.write(state)
        remaining=first+timedelta(days=TRIAL_DAYS)-now
        days=max(0,(int(remaining.total_seconds())+86399)//86400)
        return {'active':remaining.total_seconds()>0,'licensed':False,'days':days,'customer':''}
    def activate(self,token):
        now=self.clock(); data=verify_token(token,self.device,self.public_key,now)
        # A valid signed license can recover damaged trial state.
        try: state=self.store.read()
        except LicenseError: state=None
        state=state or {'first':stamp(now),'device':self.device}
        state.update(token=token.strip(),last=stamp(now),device=self.device); self.store.write(state)
        return data
