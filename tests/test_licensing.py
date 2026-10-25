import unittest,sys,json
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from licensing import *
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
class MemoryStore:
    def __init__(self): self.value=None
    def read(self): return dict(self.value) if self.value else None
    def write(self,s): self.value=dict(s)
class Tests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,1,1,tzinfo=timezone.utc);self.store=MemoryStore();self.key=Ed25519PrivateKey.generate();self.pub=b64(self.key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw))
        self.l=Licensing(self.store,'A'*32,self.pub,lambda:self.now)
    def token(self,device='A'*32):
        raw=json.dumps({'product':PRODUCT,'device':device,'type':'perpetual','issued':stamp(self.now),'customer':'test'}).encode();return b64(raw)+'.'+b64(self.key.sign(raw))
    def test_first_launch(self): self.assertEqual(self.l.check()['days'],30)
    def test_exact_expiry(self):
        self.l.check();self.now+=timedelta(days=30);self.assertFalse(self.l.check()['active'])
    def test_day_before_expiry(self):
        self.l.check();self.now+=timedelta(days=29);self.assertEqual(self.l.check()['days'],1)
    def test_clock_rollback(self):
        self.l.check();self.now-=timedelta(hours=1);self.assertRaises(LicenseError,self.l.check)
    def test_perpetual(self):
        self.l.activate(self.token());self.now+=timedelta(days=4000);self.assertTrue(self.l.check()['licensed'])
    def test_device_binding(self): self.assertRaises(LicenseError,self.l.activate,self.token('B'*32))
    def test_tamper(self):
        token=self.token();payload,signature=token.split('.');raw=unb64(payload).replace(b'test',b'evil');self.assertRaises(LicenseError,self.l.activate,b64(raw)+'.'+signature)
    def test_unsigned_rejected(self): self.assertRaises(LicenseError,self.l.activate,'fake.fake')
    def test_invalid_stored_token(self):
        self.l.check();self.store.value['token']='bad.bad';self.assertRaises(LicenseError,self.l.check)
if __name__=='__main__': unittest.main()

@unittest.skipUnless(sys.platform=='win32','Windows DPAPI only')
class WindowsProtectionTests(unittest.TestCase):
    def test_dpapi_roundtrip(self):
        original=b'{"trial":"protected"}'; protected=dpapi(original)
        self.assertNotEqual(original,protected); self.assertEqual(dpapi(protected,True),original)
    def test_dpapi_modified_rejected(self):
        protected=bytearray(dpapi(b'important'));protected[-1]^=1
        self.assertRaises(LicenseError,dpapi,bytes(protected),True)
    def test_device_id(self):
        self.assertEqual(len(device_id()),32);self.assertEqual(device_id(),device_id())
