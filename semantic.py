"""Offline multilingual semantic similarity classification, not a generative LLM."""
from __future__ import annotations
import os,sys,threading
from pathlib import Path
import numpy as np

PROTOTYPES={
'شكر وتقدير':['نقدم لكم امتناننا وتثميننا لجهودكم المتميزة وإسهامكم في إنجاح العمل. كتاب شكر وتقدير وتكريم.','إشادة رسمية بعطاء الموظف وتفانيه وأدائه المتميز في خدمة المؤسسة.'],
'تعليم مستمر':['مركز التعليم المستمر ينظم نشاطات تطوير مهارات الموظفين ودورات التأهيل المهني.','خطة برامج التعليم المستمر وتوثيق مشاركة التدريسيين وحصولهم على ساعات تدريب.'],
'دورات وورش عمل':['ندعوكم لحضور برنامج تدريبي وورشة تطوير مهارات تعقد في القاعة خلال الأيام المحددة.','تسجيل المشاركين في الدورة وإصدار شهادات اجتياز التدريب.'],
'أوامر إدارية':['استنادا إلى الصلاحيات المخولة لنا تقرر إصدار الأمر الإداري وتنفيذه من الجهات المختصة.','أمر إداري رسمي بتغيير مسؤوليات الموظف أو نقله أو تعيينه.'],
'تشكيل لجان':['تقرر تأليف فريق من السادة المدرجة أسماؤهم برئاسة أحدهم وعضوية الآخرين لإنجاز المهمة ورفع التوصيات.','تشكيل لجنة وتحديد الرئيس والأعضاء ومهام اللجنة.'],
'تكليفات ومهام':['يرجى تولي مسؤولية العمل الموكول إليكم وإنجاز المهمة وتقديم تقرير بنتائج التنفيذ.','تكليف الموظف بالقيام بمهام إضافية وتحديد المسؤوليات.'],
'ترشيحات ومشاركات':['يرجى تزويدنا بأسماء ممثلي القسم الراغبين بالمشاركة واختيار من تتوفر فيه الشروط.','ترشيح تدريسي لتمثيل الجامعة في فعالية أو مؤتمر.'],
'إيفادات':['الموافقة على سفر الموظف خارج مقر عمله لأداء مهمة رسمية مع تحمل أجور السفر والمبيت.','إيفاد إلى مؤسسة أخرى للمشاركة في مؤتمر علمي وإكمال المهمة الرسمية.'],
'إجازات':['الموافقة على انقطاع الموظف عن الدوام للمدة المطلوبة وتمتعه بإجازة اعتيادية أو مرضية.','طلب إجازة دراسية أو زمنية وتحديد مدة الغياب وتاريخ المباشرة.'],
'مراسلات رسمية':['إشارة إلى كتابكم السابق نرفق لكم البيانات المطلوبة للاطلاع وإجراء اللازم وإجابتنا.','مراسلة إدارية رسمية بين جهتين تطلب معلومات أو تجيب عن استفسار.'],
'تعاميم وتعليمات':['إلى كافة الأقسام يرجى الالتزام بالضوابط والإجراءات التالية وتعميمها على المنتسبين للعمل بموجبها.','تعليمات وزارية وتوجيهات عامة واجبة التطبيق على جميع الوحدات.'],
'محاضر اجتماعات':['اجتمع الأعضاء وناقشوا فقرات جدول الأعمال واتخذوا القرارات والتوصيات وسجلت أسماء الحاضرين.','محضر اجتماع مجلس يتضمن التاريخ والحضور ومناقشة الأعمال والقرارات.'],
'وثائق مالية':['الموافقة على تسديد المستحقات وتخصيص المبالغ من الموازنة وصرفها وفق الفواتير المرفقة.','مطالبة مالية ووصل قبض وسند صرف وتسوية حسابات.'],
'يحتاج مراجعة':['كتاب منهجي يشرح مفاهيم ومهارات تطبيقات الحاسوب للطلبة ويحتوي على فصول وتمارين واختبارات.','بحث علمي ومقال أو صورة شخصية أو وثيقة لا تنتمي إلى المراسلات الإدارية المحددة.']}

_instance=None
_lock=threading.Lock()
class SemanticEngine:
    def __init__(self,folder=None):
        from tokenizers import Tokenizer
        import onnxruntime as ort
        folder=Path(folder or Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'models')
        if not (folder/'model_quantized.onnx').is_file(): raise FileNotFoundError('النموذج الدلالي غير مرفق')
        self.tokenizer=Tokenizer.from_file(str(folder/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=128,stride=20)
        pad=self.tokenizer.padding or {}
        token=pad.get('pad_token') or ('<pad>' if self.tokenizer.token_to_id('<pad>') is not None else '[PAD]')
        self.tokenizer.enable_padding(pad_id=pad.get('pad_id',self.tokenizer.token_to_id(token) or 0),pad_token=token)
        opts=ort.SessionOptions();opts.intra_op_num_threads=min(4,os.cpu_count() or 1)
        self.session=ort.InferenceSession(str(folder/'model_quantized.onnx'),sess_options=opts,providers=['CPUExecutionProvider'])
        self.inputs={x.name for x in self.session.get_inputs()}
        self.labels=list(PROTOTYPES);texts=[t for label in self.labels for t in PROTOTYPES[label]]
        encoded=self.embed(texts);centers=[];i=0
        for label in self.labels:
            n=len(PROTOTYPES[label]);v=encoded[i:i+n].mean(axis=0);v/=max(np.linalg.norm(v),1e-9);centers.append(v);i+=n
        self.centers=np.stack(centers)
    def embed_encodings(self,encodings):
        vectors=[]
        # Sequential batches bound inference memory on office PCs.
        for offset in range(0,len(encodings),4):
            group=encodings[offset:offset+4];width=max(len(e.ids) for e in group)
            ids=np.zeros((len(group),width),dtype=np.int64);mask=np.zeros_like(ids);types=np.zeros_like(ids)
            for i,e in enumerate(group):
                n=len(e.ids);ids[i,:n]=e.ids;mask[i,:n]=e.attention_mask;types[i,:n]=e.type_ids
            feed={k:v for k,v in {'input_ids':ids,'attention_mask':mask,'token_type_ids':types}.items() if k in self.inputs}
            hidden=self.session.run(None,feed)[0]
            if hidden.ndim==3:
                weight=mask[:,:,None].astype(np.float32);v=(hidden*weight).sum(axis=1)/np.maximum(weight.sum(axis=1),1e-9)
            else:v=hidden
            v=v/np.maximum(np.linalg.norm(v,axis=1,keepdims=True),1e-9);vectors.append(v)
        return np.concatenate(vectors)
    def embed(self,texts): return self.embed_encodings(self.tokenizer.encode_batch(texts))
    def classify(self,text,subject=''):
        encoded=self.tokenizer.encode(text[:500000]);parts=[encoded]+encoded.overflowing
        if len(parts)>8:
            indices=np.linspace(0,len(parts)-1,8,dtype=int);parts=[parts[i] for i in indices]
        vectors=self.embed_encodings(parts)
        sims=vectors@self.centers.T
        # Combine document-level context and strongest two relevant segments.
        scores=0.45*sims.mean(axis=0)+0.55*np.sort(sims,axis=0)[-min(2,len(parts)):].mean(axis=0)
        if subject.strip():scores=.45*scores+.55*(self.embed([subject])[0]@self.centers.T)
        ranked=np.argsort(scores)[::-1];best,second=int(ranked[0]),int(ranked[1]);margin=float(scores[best]-scores[second]);score=float(scores[best])
        uncertain=score<.34 or margin<.035 or self.labels[best]=='يحتاج مراجعة'
        index=int(np.argmax(sims[:,best]));quote=self.tokenizer.decode(parts[index].ids,skip_special_tokens=True)
        return {'category':'يحتاج مراجعة' if uncertain else self.labels[best],'alternatives':[{'category':self.labels[int(i)],'similarity':round(float(scores[int(i)]),4)} for i in ranked[:3]],'uncertain':uncertain,'quote':quote,'segments_analyzed':len(parts),'engine':'multilingual-MiniLM-ONNX'}

def classify(text,subject=''):
    global _instance
    with _lock:
        if _instance is None:_instance=SemanticEngine()
        return _instance.classify(text,subject)
