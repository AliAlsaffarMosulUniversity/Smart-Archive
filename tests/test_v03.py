import sys,tempfile,unittest,time,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import *
class RecoveryTests(unittest.TestCase):
    def test_restore_and_collision_protection(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'doc.txt';source.write_text('الموضوع: شكر وتقدير',encoding='utf8');p=propose(source,*extract(source));a=Archive(Path(d)/'a')
            try:
                dest,_=a.store(p);ident=a.search()[0][0];a.undo(ident);self.assertFalse(Path(dest).exists());self.assertEqual(a.restore(ident),dest);self.assertEqual(digest(dest),digest(source))
                a.undo(ident);Path(dest).write_text('do not overwrite');self.assertRaises(ValueError,a.restore,ident);self.assertEqual(Path(dest).read_text(),'do not overwrite')
            finally:a.close()
    def test_subject_overrides_body_keywords(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.txt';p.write_text('الموضوع: تشكيل لجنة\nالتعليم المستمر ودورة تدريبية وورشة عمل\nشكر وتقدير وكتاب شكر',encoding='utf8')
            self.assertEqual(propose(p,*extract(p))['category'],'تشكيل لجان')
    def test_render_pdf_without_poppler(self):
        import pypdfium2 as pdfium
        with tempfile.TemporaryDirectory() as d:
            doc=pdfium.PdfDocument.new();page=doc.new_page(120,160);doc.save(Path(d)/'a.pdf');page.close();doc.close()
            render_pdf_page(Path(d)/'a.pdf',0,Path(d)/'a.png');self.assertTrue((Path(d)/'a.png').stat().st_size>50)
class UiBatchTests(unittest.TestCase):
    def test_review_batch_and_clear(self):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        from app import Window
        app=QApplication.instance() or QApplication([]);app.setLayoutDirection(Qt.RightToLeft);w=Window();w.warn=lambda e:self.fail(str(e));w.confirm=lambda *_:True
        with tempfile.TemporaryDirectory() as d:
            w.root_path=str(Path(d)/'archive')
            paths=[]
            for i in range(2):
                p=Path(d)/f'{i}.txt';p.write_text(f'الموضوع: شكر وتقدير\nالعدد: {i}',encoding='utf8');paths.append(str(p))
            def wait():
                end=time.monotonic()+20
                while w.busy and time.monotonic()<end:app.processEvents();time.sleep(.01)
                self.assertFalse(w.busy)
            w.scan(paths);wait();self.assertEqual(len(w.items),2)
            w.table.setCurrentCell(0,0);w.fields['issuer'].setText('اسم معدل');w.table.setCurrentCell(1,0);self.assertEqual(list(w.items.values())[0]['proposal']['issuer'],'اسم معدل')
            w.archive_inbox('all');wait();self.assertEqual(w.records.rowCount(),2)
            w.delete_archive(True);wait();self.assertEqual(w.records.rowCount(),0);self.assertEqual(w.trash.rowCount(),2)
            w.trash.selectAll();w.restore_selected();wait();self.assertEqual(w.records.rowCount(),2)
            w.remove_ids(list(w.items));self.assertEqual(w.table.rowCount(),0);self.assertTrue(all(Path(p).exists() for p in paths))
            if w.archive:w.archive.close();w.archive=None
        w.close()
class BundledOcrTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform=='win32' and (Path(__file__).resolve().parents[1]/'ocr'/'tesseract.exe').exists(),'Windows bundled OCR')
    def test_bundled_english_and_arabic_languages(self):
        from PIL import Image,ImageDraw,ImageFont
        with tempfile.TemporaryDirectory() as d:
            img=Image.new('RGB',(1000,250),'white');draw=ImageDraw.Draw(img);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',64);draw.text((30,70),'SMART ARCHIVE 2026',font=font,fill='black');path=Path(d)/'test.png';img.save(path)
            self.assertIn('ARCHIVE',ocr_image(path).upper())
            result=subprocess.run(ocr_command()+['--list-langs'],capture_output=True,check=True)
            self.assertIn(b'ara',result.stdout);self.assertIn(b'eng',result.stdout)
if __name__=='__main__':unittest.main()

class SemanticIntegrationTests(unittest.TestCase):
    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'models'/'model_quantized.onnx').exists(),'Model not downloaded in development environment')
    def test_indirect_arabic_intents(self):
        from semantic import classify
        examples=[('نثمن عاليا ما قدمتموه من عطاء وجهود متميزة ونعبّر عن امتناننا لإسهامكم في إنجاح العمل.','شكر وتقدير'),('تقرر تأليف فريق برئاسة الدكتور علي وعضوية أحمد ومحمد لدراسة الطلبات ورفع التوصيات.','تشكيل لجان'),('وافق المجلس على غياب الموظف عن الدوام لمدة عشرة أيام لأسباب صحية مع تحديد موعد عودته للعمل.','إجازات')]
        for text,expected in examples:
            with self.subTest(expected=expected):self.assertEqual(classify(text)['category'],expected)
