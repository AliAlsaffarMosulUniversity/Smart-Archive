from __future__ import annotations
import os, sys, threading, queue
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QTableWidget,QTableWidgetItem,QHeaderView,QSplitter,QFormLayout,QLineEdit,QComboBox,QTextEdit,QMessageBox,QTabWidget,QProgressBar)
from core import *

class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('الأرشيف الذكي | Smart Archive • 0.1'); self.resize(1280,820)
        self.proposals={}; self.jobs=queue.Queue(); self.busy=False; self.stop=threading.Event(); self.archive=None
        self.setAcceptDrops(True)
        base=QWidget(); self.setCentralWidget(base); layout=QVBoxLayout(base); layout.setContentsMargins(26,22,26,22)
        title=QLabel('الأرشيف الذكي  ◈'); title.setObjectName('title'); layout.addWidget(title)
        sub=QLabel('وثائقك مرتبة، وقرار التصنيف بين يديك  •  معالجة محلية  •  الأصول محفوظة'); layout.addWidget(sub)
        bar=QHBoxLayout(); layout.addLayout(bar)
        self.root=QLineEdit(str(Path.home()/'Documents'/'SmartArchive')); bar.addWidget(self.root)
        self.button(bar,'مجلد الأرشيف',self.choose_root)
        self.button(bar,'إضافة ملفات',self.pick)
        self.button(bar,'إضافة مجلد',self.pick_folder)
        self.button(bar,'إيقاف بعد الملف الحالي',lambda:self.stop.set())
        self.tabs=QTabWidget(); layout.addWidget(self.tabs)
        review=QWidget(); rl=QVBoxLayout(review); self.tabs.addTab(review,'الوارد والمراجعة')
        split=QSplitter(); rl.addWidget(split)
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(['الملف','الحالة','التصنيف'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.itemSelectionChanged.connect(self.selected); self.table.currentCellChanged.connect(lambda *_: self.selected()); split.addWidget(self.table)
        pane=QWidget(); form=QFormLayout(pane); split.addWidget(pane)
        self.fields={}
        for key,label in [('category','التصنيف'),('date','تاريخ الإصدار YYYY-MM-DD'),('issuer','الجهة المصدرة'),('number','رقم الكتاب'),('subject','الموضوع')]:
            field=QComboBox() if key=='category' else QLineEdit()
            if key=='category': field.addItems(CATEGORIES)
            self.fields[key]=field; form.addRow(label,field)
        self.order=QComboBox(); self.order.addItems(['السنة ← التصنيف ← الجهة','التصنيف ← السنة ← الجهة','الجهة ← السنة ← التصنيف']); form.addRow('ترتيب المجلدات',self.order)
        self.preview=QTextEdit(); self.preview.setReadOnly(True); form.addRow('النص والأدلة والتنبيهات',self.preview)
        self.model=QLineEdit(); self.model.setPlaceholderText('اسم نموذج مثبت في Ollama، اختياري'); form.addRow('ذكاء اصطناعي محلي',self.model)
        actions=QHBoxLayout(); form.addRow(actions)
        self.button(actions,'اقتراح بالنموذج المحلي',self.ai)
        self.button(actions,'فتح الأصل',self.open_source)
        self.save_button=self.button(actions,'اعتماد ونسخ آمن',self.save)
        self.save_button.setObjectName('primary')
        index=QWidget(); il=QVBoxLayout(index); self.tabs.addTab(index,'البحث وسجل الأرشيف')
        searchbar=QHBoxLayout(); il.addLayout(searchbar); self.query=QLineEdit(); self.query.setPlaceholderText('ابحث داخل النصوص والبيانات'); searchbar.addWidget(self.query)
        self.button(searchbar,'بحث / تحديث',self.search); self.button(searchbar,'تصدير CSV',self.export); self.button(searchbar,'فتح الملف',self.open_archive); self.button(searchbar,'تراجع آمن',self.undo)
        self.records=QTableWidget(0,7); self.records.setHorizontalHeaderLabels(['المعرف','التصنيف','السنة','الجهة','الموضوع','المسار','الحالة']); self.records.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.records.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.records.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); il.addWidget(self.records)
        self.progress=QProgressBar(); layout.addWidget(self.progress); self.status=QLabel('اسحب الملفات هنا للبدء. لا تُنقل الأصول ولا تُرفع المستندات إلى الإنترنت.'); layout.addWidget(self.status)
        self.timer=QTimer(); self.timer.timeout.connect(self.poll); self.timer.start(150)
        self.setStyleSheet('''QWidget{background:#101827;color:#e5eaf3;font-family:"Segoe UI";font-size:13px} QLabel#title{font-size:30px;font-weight:700;color:#e9c67c} QPushButton{background:#25334a;border:1px solid #3b4a63;border-radius:7px;padding:10px} QPushButton:hover{background:#354765} QPushButton#primary{background:#b08a42;color:white} QLineEdit,QComboBox,QTextEdit{background:#182439;border:1px solid #34435b;border-radius:5px;padding:7px} QTableWidget{background:#142036;gridline-color:#2a3850;selection-background-color:#38516d} QHeaderView::section{background:#25334a;padding:9px;border:0} QTabBar::tab{padding:12px 24px;background:#1c2b40} QTabBar::tab:selected{color:#e9c67c;background:#30415a} QProgressBar{height:8px;border:0;background:#25334a} QProgressBar::chunk{background:#d2b16b}''')
    def button(self,layout,text,fn):
        b=QPushButton(text); b.clicked.connect(fn); layout.addWidget(b); return b
    def warn(self,e): QMessageBox.warning(self,'تنبيه',str(e))
    def choose_root(self):
        if self.busy: return self.warn('انتظر انتهاء المعالجة')
        d=QFileDialog.getExistingDirectory(self,'مجلد الأرشيف')
        if d: self.root.setText(d)
    def pick(self):
        files,_=QFileDialog.getOpenFileNames(self,'اختر وثائق'); self.scan(files)
    def pick_folder(self):
        d=QFileDialog.getExistingDirectory(self,'مجلد الوارد')
        if d:
            root=Path(self.root.text()).resolve()
            self.scan([str(p) for p in Path(d).rglob('*') if p.is_file() and not p.resolve().is_relative_to(root)])
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self,event): self.scan([u.toLocalFile() for u in event.mimeData().urls() if Path(u.toLocalFile()).is_file()])
    def scan(self,files):
        if self.busy: return self.warn('توجد معالجة قيد التنفيذ')
        files=list(dict.fromkeys(str(Path(f).resolve()) for f in files))
        if not files: return
        self.busy=True; self.stop.clear(); self.progress.setRange(0,len(files)); self.progress.setValue(0); self.root.setEnabled(False)
        def run():
            for i,f in enumerate(files):
                if self.stop.is_set(): break
                try:
                    pages,notes=extract(f); p=propose(f,pages,notes); self.jobs.put(('result',f,p))
                except Exception as e: self.jobs.put(('error',f,str(e)))
                self.jobs.put(('progress',i+1))
            self.jobs.put(('done',))
        threading.Thread(target=run,daemon=True).start()
    def poll(self):
        while not self.jobs.empty():
            msg=self.jobs.get(); kind=msg[0]
            if kind in ('result','error'):
                row=self.table.rowCount(); self.table.insertRow(row)
                p=msg[2] if kind=='result' else None
                if p: self.proposals[row]=p
                for col,value in enumerate([Path(msg[1]).name,'جاهز للمراجعة' if p else msg[2],p['category'] if p else 'تعذر الفحص']): self.table.setItem(row,col,QTableWidgetItem(value))
            elif kind=='progress': self.progress.setValue(msg[1]); self.status.setText(f'تم فحص {msg[1]} ملف')
            elif kind=='done': self.busy=False; self.root.setEnabled(True); self.status.setText('انتهت المعالجة. اختر ملفًا، راجع بياناته ثم اعتمده.'); self.selected()
            elif kind=='ai':
                self.busy=False; self.preview.append('\nاقتراح النموذج المحلي (غير معتمد):\n'+json.dumps(msg[1],ensure_ascii=False,indent=2))
            elif kind=='ai_error': self.busy=False; self.warn(msg[1])
            elif kind=='saved':
                self.busy=False; self.root.setEnabled(True); self.status.setText(('نسخة مطابقة موجودة: ' if msg[2] else 'تم النسخ والتحقق: ')+msg[1]); self.search()
            elif kind=='save_error': self.busy=False; self.root.setEnabled(True); self.warn(msg[1])
    def current(self): return self.proposals.get(self.table.currentRow())
    def selected(self):
        p=self.current()
        if not p: return
        for key,field in self.fields.items():
            if key=='category': field.setCurrentText(p[key])
            else: field.setText(p.get(key,''))
        self.preview.setPlainText('تنبيهات: '+'؛ '.join(p['notes'])+'\n\nالأدلة:\n'+'\n'.join(f"{ {'date':'تاريخ الإصدار','issuer':'الجهة المصدرة','number':'رقم الكتاب','subject':'الموضوع'}.get(k,k)} — {v['location']}\n{v['quote']}" for k,v in p['evidence'].items())+'\n\n'+'\n\n'.join(x['location']+'\n'+x['text'] for x in p['pages']))
    def get_archive(self):
        root=Path(self.root.text()).resolve()
        if self.archive and self.archive.root!=root: self.archive.close(); self.archive=None
        if not self.archive: self.archive=Archive(root)
        return self.archive
    def save(self):
        if self.busy: return self.warn('انتظر انتهاء العملية الحالية')
        p=self.current()
        if not p: return self.warn('اختر ملفًا صالحًا أولًا')
        p=dict(p)
        for key,field in self.fields.items(): p[key]=field.currentText() if key=='category' else field.text().strip()
        if p['date']:
            try:
                datetime.strptime(p['date'],'%Y-%m-%d')
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',p['date']): raise ValueError()
            except ValueError: return self.warn('استخدم تاريخًا صحيحًا بصيغة YYYY-MM-DD أو اتركه فارغًا')
        p['year']=p['date'][:4] or 'غير محدد'; p['reviewed_at']=datetime.now().isoformat()
        root=self.root.text(); order=[('year','category','issuer'),('category','year','issuer'),('issuer','year','category')][self.order.currentIndex()]
        self.busy=True; self.root.setEnabled(False)
        def run():
            a=None
            try:
                a=Archive(root); dest,duplicate=a.store(p,order); self.jobs.put(('saved',dest,duplicate))
            except Exception as e: self.jobs.put(('save_error',str(e)))
            finally:
                if a: a.close()
        threading.Thread(target=run,daemon=True).start()
    def ai(self):
        if self.busy: return self.warn('انتظر انتهاء المعالجة')
        p=self.current(); model=self.model.text().strip()
        if not p or not model: return self.warn('اختر وثيقة وحدد اسم نموذج Ollama المحلي المثبت')
        self.busy=True
        def run():
            try: self.jobs.put(('ai',local_ai(p,model)))
            except Exception as e: self.jobs.put(('ai_error',str(e)))
        threading.Thread(target=run,daemon=True).start()
    def open_source(self):
        if self.current(): QDesktopServices.openUrl(QUrl.fromLocalFile(self.current()['source']))
    def search(self):
        try:
            rows=self.get_archive().search(self.query.text()); self.records.setRowCount(len(rows))
            for i,row in enumerate(rows):
                for j,value in enumerate(row): self.records.setItem(i,j,QTableWidgetItem(str(value)))
        except Exception as e: self.warn(e)
    def open_archive(self):
        i=self.records.currentRow()
        if i>=0: QDesktopServices.openUrl(QUrl.fromLocalFile(self.records.item(i,5).text()))
    def undo(self):
        i=self.records.currentRow()
        if i<0: return
        if QMessageBox.question(self,'تراجع','نقل النسخة المؤرشفة إلى مجلد recovery؟ الأصل سيبقى كما هو.')!=QMessageBox.StandardButton.Yes: return
        try: self.get_archive().undo(self.records.item(i,0).text()); self.search()
        except Exception as e: self.warn(e)
    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'تصدير الفهرس','archive.csv','CSV (*.csv)')
        if path:
            try: self.get_archive().export(path); self.status.setText('تم تصدير الفهرس')
            except Exception as e: self.warn(e)
    def closeEvent(self,event):
        if self.busy: self.warn('انتظر انتهاء العملية أو أوقف الفحص بعد الملف الحالي.'); event.ignore(); return
        if self.archive: self.archive.close()
        event.accept()

if __name__=='__main__':
    app=QApplication(sys.argv); app.setLayoutDirection(Qt.LayoutDirection.RightToLeft); win=Window(); win.show(); sys.exit(app.exec())
