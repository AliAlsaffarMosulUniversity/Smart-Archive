from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QLineEdit,QTextEdit,QPushButton,QHBoxLayout,QMessageBox

class ActivationDialog(QDialog):
    def __init__(self,manager,parent=None):
        super().__init__(parent); self.manager=manager; self.setWindowTitle('تفعيل الأرشيف الذكي'); self.resize(620,420); self.setLayoutDirection(Qt.RightToLeft)
        layout=QVBoxLayout(self)
        self.info=QLabel(); self.info.setWordWrap(True); layout.addWidget(self.info)
        layout.addWidget(QLabel('معرّف الجهاز — أرسله إلى صاحب البرنامج للحصول على رمز التفعيل:'))
        self.device=QLineEdit(manager.device); self.device.setReadOnly(True); self.device.setLayoutDirection(Qt.LeftToRight); layout.addWidget(self.device)
        copy=QPushButton('نسخ معرّف الجهاز'); copy.clicked.connect(lambda: __import__('PySide6.QtWidgets',fromlist=['QApplication']).QApplication.clipboard().setText(manager.device)); layout.addWidget(copy)
        layout.addWidget(QLabel('الصق رمز التفعيل كاملًا:'))
        self.token=QTextEdit(); self.token.setLayoutDirection(Qt.LeftToRight); layout.addWidget(self.token)
        bar=QHBoxLayout(); layout.addLayout(bar)
        activate=QPushButton('تفعيل دائم'); activate.clicked.connect(self.activate); bar.addWidget(activate)
        self.continue_button=QPushButton('متابعة التجربة'); self.continue_button.clicked.connect(self.accept); bar.addWidget(self.continue_button)
        cancel=QPushButton('إغلاق'); cancel.clicked.connect(self.reject); bar.addWidget(cancel)
        self.refresh()
    def refresh(self):
        try:
            result=self.manager.check()
            self.info.setText('البرنامج مفعّل بترخيص دائم.' if result['licensed'] else f"الفترة التجريبية: متبقٍ {result['days']} يومًا. بعد 30 يومًا يتطلب الاستخدام رمز تفعيل مرتبطًا بهذا الجهاز.")
            self.continue_button.setVisible(result['active']); self.continue_button.setText('متابعة' if result['licensed'] else 'متابعة التجربة')
        except Exception as e: self.info.setText(str(e)); self.continue_button.setVisible(False)
    def activate(self):
        try:
            self.manager.activate(''.join(self.token.toPlainText().split()))
            QMessageBox.information(self,'تم التفعيل','تم تفعيل البرنامج بنجاح لهذا الجهاز.'); self.accept()
        except Exception as e: QMessageBox.warning(self,'تعذر التفعيل',str(e))
