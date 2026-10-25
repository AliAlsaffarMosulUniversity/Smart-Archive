"""Noninteractive packaged-app validation. Never opens the user's archive or license state."""
import os,tempfile,time
from pathlib import Path

def run(report):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from app import Window
    from core import ocr_image,extract
    from semantic import classify
    from PIL import Image,ImageDraw,ImageFont
    app=QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as d:
        d=Path(d);image=Image.new('RGB',(1100,240),'white');draw=ImageDraw.Draw(image)
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',64);draw.text((40,65),'SMART ARCHIVE 2026',font=font,fill='black');path=d/'ocr.png';image.save(path)
        assert 'ARCHIVE' in ocr_image(path).upper(),'Bundled OCR failed'
        result=classify('نقدم لكم امتناننا لما بذلتموه من جهود متميزة في إنجاح العمل ونتمنى لكم المزيد من العطاء.')
        assert result['category']=='شكر وتقدير','Bundled semantic model failed'
        source=d/'letter.txt';source.write_text('الموضوع: شكر وتقدير\nالتاريخ: 2026/10/25',encoding='utf8')
        w=Window();w.root_path=str(d/'archive');w.confirm=lambda *_:True
        errors=[];w.warn=lambda e:errors.append(str(e));w.scan([str(source)])
        def wait():
            end=time.monotonic()+90
            while w.busy and time.monotonic()<end:app.processEvents();time.sleep(.01)
            assert not w.busy,'Operation timed out'
        wait();assert len(w.items)==1,'Scan failed';w.archive_inbox('all');wait();assert w.records.rowCount()==1,'Archive failed'
        w.delete_archive(True);wait();assert w.trash.rowCount()==1,'Recycle failed'
        w.trash.selectAll();w.restore_selected();wait();assert w.records.rowCount()==1,'Restore failed';assert not errors,str(errors)
        if w.archive:w.archive.close();w.archive=None
        w.close()
    Path(report).write_text('PASS: frozen Windows EXE, embedded OCR, embedded Arabic semantic model, batch archive, recycle and restore',encoding='utf8')
