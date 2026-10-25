from __future__ import annotations
import sys, threading, queue, copy
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QSettings
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QTableWidget,QTableWidgetItem,QHeaderView,QSplitter,QFormLayout,QLineEdit,QComboBox,QTextEdit,QMessageBox,QTabWidget,QProgressBar,QDialog,QDialogButtonBox,QAbstractItemView)
from core import *

LIGHT='''
QWidget{background:#f4f6f8;color:#263b41;font-family:"Segoe UI";font-size:13px}
QLabel#title{font-size:27px;font-weight:700;color:#244d4b}
QLabel#muted{color:#77858d;font-size:12px}
QLabel#count{color:#55706e;font-size:13px;padding:7px 0}
QPushButton{background:#ffffff;border:1px solid #dbe2e6;border-radius:8px;padding:9px 13px;color:#36505a}
QPushButton:hover{background:#e8f0ef;border-color:#afc5c0}
QPushButton:disabled{color:#a8b3b8;background:#f0f3f4}
QPushButton#primary{background:#39766c;border:1px solid #39766c;color:white;font-weight:600}
QPushButton#primary:hover{background:#2d6259}
QPushButton#danger{color:#a75a56}
QLineEdit,QComboBox,QTextEdit{background:#fff;border:1px solid #dce4e7;border-radius:7px;padding:8px;selection-background-color:#d5e9e3;selection-color:#24483f}
QTableWidget{background:#fff;alternate-background-color:#f8fafb;border:1px solid #e0e7ea;border-radius:9px;gridline-color:#edf0f2;selection-background-color:#e0eee9;selection-color:#254e45}
QTableWidget::item{padding:8px;border-bottom:1px solid #edf0f2}
QHeaderView::section{background:#edf2f4;color:#61747c;padding:10px;border:0;font-weight:600}
QTabWidget::pane{border:0}
QTabBar::tab{background:transparent;color:#7a8a91;padding:13px 22px;border-bottom:2px solid transparent}
QTabBar::tab:selected{color:#2f6e63;border-bottom:2px solid #39766c;font-weight:600}
QProgressBar{border:0;background:#e5ebed;border-radius:3px;height:6px;max-height:6px}
QProgressBar::chunk{background:#76a79b;border-radius:3px}
QSplitter::handle{background:#f4f6f8;width:14px}
'''
DARK=LIGHT.replace('#f4f6f8','#182427').replace('#ffffff','#233237').replace('#fff;','#233237;').replace('#fff','#233237').replace('#263b41','#d9e5e4').replace('#244d4b','#a8d3c6').replace('#36505a','#d0dedb').replace('#f8fafb','#26373a').replace('#edf2f4','#2a3b40').replace('#e0eee9','#34544c').replace('#254e45','#d4eee6').replace('#edf0f2','#304349').replace('#dce4e7','#3c5056').replace('#e0e7ea','#3c5056').replace('#dbe2e6','#3c5056')

class Window(QMainWindow):
    def __init__(self,license_manager=None):
        super().__init__(); self.license_manager=license_manager; self.license_blocked=False
        self.setWindowTitle('الأرشيف الذكي | Smart Archive 0.3'); self.resize(1260,820); self.setMinimumSize(1000,700)
        self.prefs=QSettings('SmartArchive','Desktop'); self.root_path=self.prefs.value('archive_path',str(Path.home()/'Documents'/'SmartArchive'))
        self.order_index=int(self.prefs.value('order',0)); self.dark=self.prefs.value('dark','false')=='true'
        self.items={}; self.editing=None; self.jobs=queue.Queue(); self.busy=False; self.stop=threading.Event(); self.archive=None; self.archive_ids={}
        self.setAcceptDrops(True)
        base=QWidget(); self.setCentralWidget(base); layout=QVBoxLayout(base); layout.setContentsMargins(26,22,26,18); layout.setSpacing(14)
        header=QHBoxLayout(); layout.addLayout(header)
        title=QLabel('الأرشيف الذكي'); title.setObjectName('title'); header.addWidget(title); header.addStretch()
        self.license_status=QLabel(''); self.license_status.setObjectName('muted'); header.addWidget(self.license_status)
        self.button(header,'الإعدادات',self.settings)
        self.controls=[]
        bar=QHBoxLayout(); layout.addLayout(bar)
        self.add_button=self.button(bar,'إضافة ملفات',self.pick,'primary'); self.controls.append(self.add_button)
        self.controls.append(self.button(bar,'إضافة مجلد',self.pick_folder))
        self.folder_label=QLabel(); self.folder_label.setObjectName('muted'); self.folder_label.setToolTip(self.root_path); bar.addWidget(self.folder_label); bar.addStretch(); self.update_folder_label()
        self.stop_button=self.button(bar,'إيقاف',self.stop.set); self.stop_button.setVisible(False)
        self.tabs=QTabWidget(); layout.addWidget(self.tabs)
        incoming=QWidget(); il=QVBoxLayout(incoming); il.setContentsMargins(0,10,0,0); self.tabs.addTab(incoming,'الملفات الواردة')
        tools=QHBoxLayout(); il.addLayout(tools)
        self.inbox_query=QLineEdit(); self.inbox_query.setPlaceholderText('بحث في الملفات الواردة'); self.inbox_query.textChanged.connect(self.filter_inbox); tools.addWidget(self.inbox_query)
        self.count=QLabel(''); self.count.setObjectName('count'); tools.addWidget(self.count)
        self.button(tools,'تحديد الكل',self.select_inbox)
        self.controls.append(self.button(tools,'إزالة المحدد',lambda:self.remove_inbox(False),'danger'))
        self.controls.append(self.button(tools,'إفراغ القائمة',lambda:self.remove_inbox(True),'danger'))
        split=QSplitter(Qt.Horizontal); il.addWidget(split,1)
        self.table=self.make_table(['اسم الملف','التصنيف','السنة','الحالة']); split.addWidget(self.table)
        self.table.currentCellChanged.connect(self.selection_changed)
        pane=QWidget(); form=QFormLayout(pane); form.setContentsMargins(12,4,0,4); form.setSpacing(13); split.addWidget(pane); split.setSizes([720,420])
        self.detail_title=QLabel('اختر ملفًا للمراجعة'); self.detail_title.setStyleSheet('font-size:16px;font-weight:600'); self.detail_title.setWordWrap(True); form.addRow(self.detail_title)
        self.fields={}
        for key,label in [('category','التصنيف'),('subject','الموضوع'),('issuer','الجهة المصدرة'),('date','تاريخ الكتاب'),('number','رقم الكتاب')]:
            field=QComboBox() if key=='category' else QLineEdit()
            if key=='category': field.addItems(CATEGORIES)
            if key=='date': field.setPlaceholderText('2026-10-25'); field.setLayoutDirection(Qt.LeftToRight)
            self.fields[key]=field; form.addRow(label,field)
        self.note=QLabel(''); self.note.setWordWrap(True); self.note.setObjectName('muted'); form.addRow(self.note)
        detail_buttons=QHBoxLayout(); form.addRow(detail_buttons)
        self.button(detail_buttons,'معاينة النص',self.show_text); self.button(detail_buttons,'فتح الملف',self.open_source)
        form.addRow(QLabel(''))
        self.save_current=self.button(form,'أرشفة هذا الملف',lambda:self.archive_inbox('current'),'primary'); self.controls.append(self.save_current)
        bottom=QHBoxLayout(); il.addLayout(bottom)
        self.controls.append(self.button(bottom,'أرشفة المحدد',lambda:self.archive_inbox('selected'),'primary'))
        self.controls.append(self.button(bottom,'أرشفة الكل',lambda:self.archive_inbox('all')))
        bottom.addStretch(); hint=QLabel('تُحفظ الأصول دون تغيير'); hint.setObjectName('muted'); bottom.addWidget(hint)
        archived=QWidget(); al=QVBoxLayout(archived); al.setContentsMargins(0,10,0,0); self.tabs.addTab(archived,'الأرشيف')
        ab=QHBoxLayout(); al.addLayout(ab); self.query=QLineEdit(); self.query.setPlaceholderText('بحث في محتوى الأرشيف'); ab.addWidget(self.query); self.query.returnPressed.connect(self.search)
        self.button(ab,'بحث',self.search); self.button(ab,'تحديد الكل',lambda:self.records.selectAll()); self.button(ab,'فتح الملف',self.open_archive); self.button(ab,'تصدير الفهرس',self.export)
        self.records=self.make_table(['اسم الملف','التصنيف','السنة','الجهة','الموضوع']); self.records.cellDoubleClicked.connect(lambda *_:self.open_archive()); al.addWidget(self.records)
        ar=QHBoxLayout(); al.addLayout(ar)
        self.controls.append(self.button(ar,'حذف المحدد',lambda:self.delete_archive(False),'danger')); self.controls.append(self.button(ar,'حذف جميع الملفات',lambda:self.delete_archive(True),'danger'))
        ar.addStretch(); self.archive_count=QLabel(''); self.archive_count.setObjectName('muted'); ar.addWidget(self.archive_count)
        recycle=QWidget(); tl=QVBoxLayout(recycle); tl.setContentsMargins(0,10,0,0); self.tabs.addTab(recycle,'سلة الاستعادة')
        self.trash=self.make_table(['اسم الملف','التصنيف','السنة','الجهة','الموضوع']); tl.addWidget(self.trash)
        tb=QHBoxLayout(); tl.addLayout(tb); self.button(tb,'تحديد الكل',lambda:self.trash.selectAll()); self.controls.append(self.button(tb,'استعادة المحدد',self.restore_selected,'primary')); tb.addStretch()
        self.tabs.currentChanged.connect(lambda *_:self.refresh_archive_if_needed())
        self.progress=QProgressBar(); self.progress.setTextVisible(False); self.progress.setRange(0,1); self.progress.setValue(0); self.progress.setVisible(False); layout.addWidget(self.progress)
        self.status=QLabel('أضف ملفاتك أو اسحبها إلى النافذة'); self.status.setObjectName('muted'); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.timer=QTimer(self); self.timer.timeout.connect(self.poll); self.timer.start(120)
        self.setStyleSheet(DARK if self.dark else LIGHT); self.update_count(); self.set_detail_enabled(False)
        if self.license_manager:
            self.license_timer=QTimer(self); self.license_timer.timeout.connect(self.enforce_license); self.license_timer.start(60000); self.enforce_license()
    def button(self,layout,text,fn,kind=''):
        b=QPushButton(text); b.setCursor(Qt.PointingHandCursor); b.clicked.connect(fn)
        if kind: b.setObjectName(kind)
        if isinstance(layout,QFormLayout): layout.addRow(b)
        else: layout.addWidget(b)
        return b
    def make_table(self,headers):
        t=QTableWidget(0,len(headers)); t.setHorizontalHeaderLabels(headers); t.setAlternatingRowColors(True); t.setShowGrid(False)
        t.setSelectionBehavior(QAbstractItemView.SelectRows); t.setSelectionMode(QAbstractItemView.ExtendedSelection); t.setEditTriggers(QAbstractItemView.NoEditTriggers); t.verticalHeader().hide(); t.verticalHeader().setDefaultSectionSize(46)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); t.horizontalHeader().setSectionResizeMode(0,QHeaderView.Interactive); t.setColumnWidth(0,260); return t
    def warn(self,e): QMessageBox.warning(self,'الأرشيف الذكي',str(e))
    def confirm(self,title,text): return QMessageBox.question(self,title,text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes
    def guard(self):
        if self.busy: self.warn('انتظر انتهاء العملية الحالية أو أوقفها.'); return False
        if self.license_manager:
            if not self.enforce_license(): return False
        return True
    def enforce_license(self):
        if self.license_blocked: return False
        try:
            result=self.license_manager.check()
            if result['active']:
                self.license_status.setText('مفعّل' if result['licensed'] else f"التجربة: {result['days']} يومًا"); return True
        except Exception: pass
        self.stop.set()
        if self.busy: return False
        self.license_blocked=True
        from licensing_ui import ActivationDialog
        accepted=ActivationDialog(self.license_manager,self).exec()==QDialog.Accepted
        self.license_blocked=False
        if not accepted: QApplication.instance().quit(); return False
        return self.enforce_license()
    def settings(self):
        if self.busy: return self.warn('انتظر انتهاء العملية')
        d=QDialog(self); d.setWindowTitle('الإعدادات'); d.setMinimumWidth(560); f=QFormLayout(d)
        path=QLineEdit(self.root_path); row=QHBoxLayout(); row.addWidget(path)
        def choose():
            selected=QFileDialog.getExistingDirectory(d,'مجلد الأرشيف',path.text())
            if selected: path.setText(selected)
        self.button(row,'اختيار',choose); f.addRow('حفظ الأرشيف',row)
        order=QComboBox(); order.addItems(['السنة / التصنيف / الجهة','التصنيف / السنة / الجهة','الجهة / السنة / التصنيف']); order.setCurrentIndex(self.order_index); f.addRow('ترتيب المجلدات',order)
        theme=QComboBox(); theme.addItems(['فاتح هادئ','داكن']); theme.setCurrentIndex(1 if self.dark else 0); f.addRow('المظهر',theme)
        info=QLabel('قراءة النصوص والصور بالعربية والإنجليزية مدمجة.\nتحليل المعنى بالعربية مدمج ويعمل دون الإنترنت. راجع التصنيف قبل الأرشفة.'); info.setWordWrap(True); f.addRow(info)
        if self.license_manager:
            self.button(f,'التفعيل والترخيص',lambda:__import__('licensing_ui').ActivationDialog(self.license_manager,d).exec())
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(d.accept); buttons.rejected.connect(d.reject); f.addRow(buttons)
        if d.exec()==QDialog.Accepted:
            if not path.text().strip(): return self.warn('اختر مجلدًا صالحًا')
            self.root_path=str(Path(path.text()).resolve()); self.order_index=order.currentIndex(); self.dark=bool(theme.currentIndex())
            self.prefs.setValue('archive_path',self.root_path); self.prefs.setValue('order',self.order_index); self.prefs.setValue('dark','true' if self.dark else 'false')
            if self.archive: self.archive.close(); self.archive=None
            self.setStyleSheet(DARK if self.dark else LIGHT); self.update_folder_label(); self.refresh_archive_if_needed()
    def update_folder_label(self): self.folder_label.setText('الحفظ: '+Path(self.root_path).name); self.folder_label.setToolTip(self.root_path)
    def pick(self):
        if not self.guard(): return
        files,_=QFileDialog.getOpenFileNames(self,'اختر الملفات'); self.scan(files)
    def pick_folder(self):
        if not self.guard(): return
        folder=QFileDialog.getExistingDirectory(self,'اختر مجلد الملفات')
        if folder: self.scan(self.expand_paths([folder]))
    def expand_paths(self,paths):
        result=[]; archive=Path(self.root_path).resolve()
        for name in paths:
            p=Path(name)
            if p.is_dir(): result.extend(str(x) for x in p.rglob('*') if x.is_file() and not x.resolve().is_relative_to(archive) and x.suffix.lower() in SUPPORTED)
            elif p.is_file(): result.append(str(p))
        return result
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self,e): self.scan(self.expand_paths([u.toLocalFile() for u in e.mimeData().urls()]))
    def set_busy(self,value,total=0):
        self.busy=value
        for b in self.controls: b.setEnabled(not value)
        self.stop_button.setVisible(value); self.progress.setVisible(value)
        if value: self.stop.clear(); self.progress.setRange(0,max(total,1)); self.progress.setValue(0)
    def scan(self,files):
        if not self.guard(): return
        existing={x['source'] for x in self.items.values()}
        files=[f for f in dict.fromkeys(str(Path(f).resolve()) for f in files) if f not in existing]
        if not files: self.status.setText('لا توجد ملفات جديدة'); return
        self.commit_editor(); self.set_busy(True,len(files)); self.tabs.setCurrentIndex(0); self.status.setText('جارٍ فحص الملفات…')
        def run():
            for i,path in enumerate(files):
                if self.stop.is_set(): break
                self.jobs.put(('working',Path(path).name))
                try:
                    pages,notes=extract(path); p=propose(path,pages,notes); item={'source':path,'proposal':p,'state':'جاهز','error':''}
                except Exception as e: item={'source':path,'proposal':None,'state':'تعذر الفحص','error':str(e)}
                self.jobs.put(('item',uuid.uuid4().hex,item)); self.jobs.put(('progress',i+1))
            self.jobs.put(('done','اكتمل الفحص' if not self.stop.is_set() else 'توقف الفحص'))
        threading.Thread(target=run,daemon=True).start()
    def poll(self):
        while not self.jobs.empty():
            msg=self.jobs.get(); kind=msg[0]
            if kind=='item': self.items[msg[1]]=msg[2]; self.add_row(msg[1]); self.update_count()
            elif kind=='progress': self.progress.setValue(msg[1])
            elif kind=='working': self.status.setText('جارٍ معالجة: '+msg[1])
            elif kind=='archived':
                ident,duplicate=msg[1:]; self.items[ident]['state']='مكرر' if duplicate else 'مؤرشف'; self.repaint_row(ident)
            elif kind=='operation_error': self.operation_errors.append(msg[1])
            elif kind=='batch_done':
                self.set_busy(False); self.status.setText(msg[1]); self.update_count(); self.search()
                if self.operation_errors: self.show_dialog('ملفات تحتاج مراجعة','\n\n'.join(self.operation_errors))
            elif kind=='done':
                self.set_busy(False); self.status.setText(msg[1]); self.filter_inbox(); self.update_count()
                if self.table.currentRow()<0 and self.table.rowCount(): self.table.setCurrentCell(0,0)
        if self.license_manager and not self.busy and not self.license_blocked:
            # Periodic license timer handles normal checks; no disk writes on every UI tick.
            pass
    def add_row(self,ident):
        row=self.table.rowCount(); self.table.insertRow(row); self.fill_row(row,ident)
    def fill_row(self,row,ident):
        item=self.items[ident]; p=item['proposal'] or {}
        values=[Path(item['source']).name,p.get('category','—'),p.get('year','—'),item['state']]
        for col,value in enumerate(values):
            cell=QTableWidgetItem(str(value)); cell.setData(Qt.UserRole,ident); cell.setToolTip(str(value) if not item['error'] else item['error']); self.table.setItem(row,col,cell)
    def repaint_row(self,ident):
        for row in range(self.table.rowCount()):
            if self.table.item(row,0).data(Qt.UserRole)==ident: self.fill_row(row,ident); break
    def selected_ids(self,table): return list(dict.fromkeys(table.item(i.row(),0).data(Qt.UserRole) for i in table.selectionModel().selectedRows()))
    def select_inbox(self):
        self.table.clearSelection()
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                from PySide6.QtCore import QItemSelectionModel
                self.table.selectionModel().select(self.table.model().index(row,0),QItemSelectionModel.Select|QItemSelectionModel.Rows)
    def filter_inbox(self):
        query=normalize(self.inbox_query.text())
        for row in range(self.table.rowCount()): self.table.setRowHidden(row,query not in normalize(' '.join(self.table.item(row,c).text() for c in range(4))))
    def update_count(self):
        ready=sum(x['proposal'] is not None and x['state']=='جاهز' for x in self.items.values()); self.count.setText(f'{len(self.items)} ملف · {ready} جاهز')
    def set_detail_enabled(self,enabled):
        for field in self.fields.values(): field.setEnabled(enabled)
    def commit_editor(self):
        if self.editing not in self.items or not self.items[self.editing]['proposal'] or self.items[self.editing]['state'] in ('مؤرشف','مكرر'): return
        p=self.items[self.editing]['proposal']
        for key,field in self.fields.items(): p[key]=field.currentText() if key=='category' else field.text().strip()
        p['year']=p['date'][:4] if re.fullmatch(r'\d{4}-\d{2}-\d{2}',p['date']) else 'غير محدد'
        if self.items[self.editing]['state'] in ('مؤرشف','مكرر'): self.note.setText('تعديل البيانات يتطلب إعادة الأرشفة؛ النسخة السابقة لا تتغير.')
        self.repaint_row(self.editing)
    def selection_changed(self,*_):
        self.commit_editor(); row=self.table.currentRow(); self.editing=self.table.item(row,0).data(Qt.UserRole) if row>=0 and self.table.item(row,0) else None
        item=self.items.get(self.editing); p=item['proposal'] if item else None
        self.detail_title.setText(Path(item['source']).name if item else 'اختر ملفًا للمراجعة'); self.detail_title.setToolTip(item['source'] if item else '')
        self.set_detail_enabled(bool(p) and item['state'] not in ('مؤرشف','مكرر'))
        for key,field in self.fields.items():
            value=p.get(key,'') if p else ''
            if key=='category': field.setCurrentText(value or CATEGORIES[-1])
            else: field.setText(value)
        self.note.setText(('؛ '.join(p['notes']) if p else item['error'] if item else '')[:500])
    def remove_inbox(self,all_items=False):
        if not self.guard(): return
        ids=list(self.items) if all_items else self.selected_ids(self.table)
        if not ids: return self.warn('حدد الملفات أولًا')
        if not self.confirm('إزالة من القائمة',f'إزالة {len(ids)} ملفًا من قائمة الوارد؟ لن تُحذف الملفات من الجهاز أو الأرشيف.'): return
        self.remove_ids(ids)
    def remove_ids(self,ids):
        self.editing=None
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()-1,-1,-1):
            if self.table.item(row,0).data(Qt.UserRole) in ids: self.table.removeRow(row)
        for ident in ids: self.items.pop(ident,None)
        self.table.blockSignals(False); self.selection_changed(); self.update_count()
    def show_dialog(self,title,text):
        d=QDialog(self); d.setWindowTitle(title); d.resize(750,580); l=QVBoxLayout(d); v=QTextEdit(); v.setReadOnly(True); v.setPlainText(text); l.addWidget(v); self.button(l,'إغلاق',d.accept); d.exec()
    def show_text(self):
        item=self.items.get(self.editing)
        if not item: return
        p=item['proposal']
        text='\n\n'.join(x['location']+'\n'+x['text'] for x in p['pages']) if p else item['error']; self.show_dialog('معاينة النص',text)
    def open_source(self):
        item=self.items.get(self.editing)
        if item: QDesktopServices.openUrl(QUrl.fromLocalFile(item['source']))
    def archive_inbox(self,mode):
        if not self.guard(): return
        self.commit_editor()
        ids=([self.editing] if self.editing else []) if mode=='current' else self.selected_ids(self.table) if mode=='selected' else list(self.items)
        ids=[i for i in ids if i in self.items and self.items[i]['proposal'] is not None and self.items[i]['state'] not in ('مؤرشف','مكرر')]
        if not ids: return self.warn('لا توجد ملفات جاهزة جديدة للأرشفة')
        proposals=[]
        for ident in ids:
            p=copy.deepcopy(self.items[ident]['proposal'])
            if p['date']:
                try:
                    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',p['date']): raise ValueError()
                    datetime.strptime(p['date'],'%Y-%m-%d')
                except ValueError: return self.warn('صحح التاريخ أو اتركه فارغًا للملف: '+Path(p['source']).name)
            p['year']=p['date'][:4] or 'غير محدد'; p['reviewed_at']=datetime.now().isoformat(); proposals.append((ident,p))
        if len(ids)>1 and not self.confirm('أرشفة جماعية',f'أرشفة {len(ids)} ملفًا بالبيانات الحالية؟ راجع التصنيف والجهة والتاريخ قبل المتابعة.'): return
        root=self.root_path; order=[('year','category','issuer'),('category','year','issuer'),('issuer','year','category')][self.order_index]
        self.operation_errors=[]; self.set_busy(True,len(ids))
        def run():
            a=None; done=0
            try:
                a=Archive(root)
                for i,(ident,p) in enumerate(proposals):
                    if self.stop.is_set(): break
                    try:
                        _,duplicate=a.store(p,order); self.jobs.put(('archived',ident,duplicate)); done+=1
                    except Exception as e: self.jobs.put(('operation_error',Path(p['source']).name+': '+str(e)))
                    self.jobs.put(('progress',i+1))
            except Exception as e: self.jobs.put(('operation_error',str(e)))
            finally:
                if a: a.close()
                self.jobs.put(('batch_done',f'اكتملت أرشفة {done} ملفًا'))
        threading.Thread(target=run,daemon=True).start()
    def get_archive(self):
        root=Path(self.root_path).resolve()
        if self.archive and self.archive.root!=root: self.archive.close(); self.archive=None
        if not self.archive: self.archive=Archive(root)
        return self.archive
    def refresh_archive_if_needed(self):
        if self.tabs.currentIndex()>0: self.search()
    def search(self):
        try:
            archive=self.get_archive(); rows=archive.search(self.query.text()); self.archive_ids={r[0]:r for r in rows}
            self.fill_archive(self.records,[r for r in rows if r[-1]=='active'])
            self.fill_archive(self.trash,[r for r in archive.search() if r[-1]=='undone'])
            self.archive_count.setText(f'{self.records.rowCount()} ملفًا')
        except Exception as e: self.warn(e)
    def fill_archive(self,table,rows):
        table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,value in enumerate([Path(r[5]).name,r[1],r[2],r[3],r[4]]):
                cell=QTableWidgetItem(str(value)); cell.setData(Qt.UserRole,r[0]); cell.setToolTip(r[5] if j==0 else str(value)); table.setItem(i,j,cell)
    def open_archive(self):
        row=self.records.currentRow()
        if row<0: return
        ident=self.records.item(row,0).data(Qt.UserRole); record=self.archive_ids.get(ident)
        if record: QDesktopServices.openUrl(QUrl.fromLocalFile(record[5]))
    def delete_archive(self,all_items=False):
        if not self.guard(): return
        ids=[r[0] for r in self.get_archive().search() if r[-1]=='active'] if all_items else self.selected_ids(self.records)
        if not ids: return self.warn('لا توجد ملفات محددة')
        if not self.confirm('حذف من الأرشيف',f'نقل {len(ids)} ملفًا إلى سلة الاستعادة؟ يمكنك استعادتها لاحقًا. الأصول لن تُحذف.'): return
        self.archive_operation(ids,'undo')
    def restore_selected(self):
        if not self.guard(): return
        ids=self.selected_ids(self.trash)
        if not ids: return self.warn('حدد الملفات المراد استعادتها')
        self.archive_operation(ids,'restore')
    def archive_operation(self,ids,method):
        root=self.root_path; self.operation_errors=[]; self.set_busy(True,len(ids))
        def run():
            archive=None; count=0
            try:
                archive=Archive(root)
                for i,ident in enumerate(ids):
                    if self.stop.is_set(): break
                    try: getattr(archive,method)(ident); count+=1
                    except Exception as e: self.jobs.put(('operation_error',str(e)))
                    self.jobs.put(('progress',i+1))
            except Exception as e: self.jobs.put(('operation_error',str(e)))
            finally:
                if archive: archive.close()
                self.jobs.put(('batch_done',f'تمت معالجة {count} ملفًا'))
        threading.Thread(target=run,daemon=True).start()
    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'تصدير الفهرس','archive.csv','CSV (*.csv)')
        if path:
            try: self.get_archive().export(path); self.status.setText('تم تصدير الفهرس')
            except Exception as e: self.warn(e)
    def closeEvent(self,event):
        if self.busy: self.warn('أوقف العملية وانتظر انتهاء الملف الحالي'); event.ignore(); return
        if self.archive: self.archive.close()
        event.accept()

if __name__=='__main__':
    if '--self-test' in sys.argv:
        from app_selftest import run
        report=sys.argv[sys.argv.index('--report')+1]
        try: run(report)
        except Exception as e:
            Path(report).write_text('FAILED: '+str(e),encoding='utf8'); sys.exit(1)
        sys.exit(0)
    app=QApplication(sys.argv); app.setLayoutDirection(Qt.RightToLeft)
    from licensing import Licensing
    from licensing_ui import ActivationDialog
    try:
        manager=Licensing()
        result=manager.check()
        if not result['active'] and ActivationDialog(manager).exec()!=QDialog.Accepted: sys.exit(0)
    except Exception:
        try:
            manager=Licensing()
            if ActivationDialog(manager).exec()!=QDialog.Accepted: sys.exit(0)
        except Exception as e: QMessageBox.critical(None,'تعذر بدء البرنامج',str(e)); sys.exit(1)
    win=Window(manager); win.show(); sys.exit(app.exec())
