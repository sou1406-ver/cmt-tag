"""Development-only inference demo: old human labels, no gold data access."""
from collections import Counter
from pathlib import Path
import platform

import joblib
import sklearn

from src.dataset.common import ROOT,load,read_jsonl,save,sha,staged,seal,verify
from src.dataset.blind import assert_allowed
from src.preprocessing import preprocess
from .core import gold_model,LABELS

DEFAULT=ROOT/'outputs/demo_sentiment_425'


def build(output=DEFAULT,root=ROOT):
    root,output=Path(root).resolve(),Path(output).resolve()
    if not output.is_relative_to(root/'outputs'):raise ValueError('Keep demo models local under outputs/')
    source=root/'outputs/canonical/versions/filtered_20261112_final'
    verify(source)
    if output.exists():raise FileExistsError('Demo artifact already exists; use it or choose a new output')
    rows=[r for r in read_jsonl(source/'candidate.local.jsonl') if r.get('human_label') in LABELS and
          any(d.get('status')=='LABELED' and d.get('label')==r['human_label'] for d in r.get('human_decisions',[]))]
    if len(rows)!=425:raise ValueError('Exactly the existing 425 human development labels are required')
    assert_allowed([dict(r,id=r['record_id'],text_view=r['text_minimal']) for r in rows],'train',
        reservation_root=root/'outputs/phase_g/blind_test',registry=root/'data/test_reservations')
    inputs={str(p):sha(p) for p in [source/'manifest.json',source/'candidate.local.jsonl']}
    # Reuse the predeclared fixed pipeline. This function constructs a model,
    # despite its historical name; it does NOT open or evaluate any gold data.
    model=gold_model('tfidf_char_svm')
    model.fit([preprocess(r['text_minimal']) for r in rows],[r['human_label'] for r in rows])
    with staged(output) as out:
        joblib.dump(model,out/'model.joblib')
        save(out/'model_info.json',dict(status='DEVELOPMENT_DEMO_ONLY',train_records=425,
            train_labels=dict(Counter(r['human_label'] for r in rows)),train_ids=[r['record_id'] for r in rows],
            inputs_sha256=inputs,preprocess='src.preprocessing.preprocess; vectorizer lowercase=True',
            model='TF-IDF char_wb (3,5) + LinearSVC C=1 balanced; seed=20261113',
            labels=LABELS,sklearn=sklearn.__version__,python=platform.python_version(),
            source_sha256=sha(Path(__file__)),preprocessing_sha256=sha(ROOT/'src/preprocessing/__init__.py'),
            gold_data_used=False,new_human_labels_used=False,metrics_computed=False,
            note='Manual demo predictions, not a new evaluation or approved research release. No probabilities or accuracy claim.'))
        if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Training input changed')
        seal(out,dict(kind='DEVELOPMENT_INFERENCE_DEMO',approved_release=False))
    return dict(output=str(output),train_records=425,gold_data_used=False)


def load_model(directory=DEFAULT):
    directory=Path(directory);verify(directory);info=load(directory/'model_info.json')
    if info['status']!='DEVELOPMENT_DEMO_ONLY' or info['sklearn']!=sklearn.__version__:
        raise ValueError('Demo artifact/runtime mismatch')
    if info['preprocessing_sha256']!=sha(ROOT/'src/preprocessing/__init__.py'):
        raise ValueError('Demo preprocessing changed; do not silently use another text pipeline')
    model=joblib.load(directory/'model.joblib')  # Only use locally built, checksum-verified artifacts.
    if set(model.classes_)!=set(LABELS):raise ValueError('Unexpected model classes')
    return model


def predict(model,text):
    if not isinstance(text,str) or not text.strip():raise ValueError('Please enter a nonempty movie comment')
    view=preprocess(text)
    return str(model.predict([view])[0])


def interactive(model,read_line=input,emit=print):
    emit('Demo 3 nhan POS / NEG / NEU. Khong luu binh luan vua nhap.')
    while True:
        try:text=read_line('Nhap binh luan (Enter de ket thuc): ')
        except (EOFError,KeyboardInterrupt):emit('Da ket thuc.');return
        if not text.strip():return
        emit('Nhan du doan: '+predict(model,text))
