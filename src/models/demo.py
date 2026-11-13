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

DEFAULT=ROOT/'outputs/demo_baselines_425'
MODELS={
    'bow_multinomial_nb':'BoW + MultinomialNB',
    'bow_complement_nb':'BoW + ComplementNB',
    'tfidf_word_svm':'TF-IDF word + LinearSVC',
    'tfidf_char_svm':'TF-IDF char_wb (3,5) + LinearSVC',
}


def training_rows(root=ROOT):
    root=Path(root).resolve()
    source=root/'outputs/canonical/versions/filtered_20261112_final'
    verify(source)
    rows=[r for r in read_jsonl(source/'candidate.local.jsonl') if r.get('human_label') in LABELS and
          any(d.get('status')=='LABELED' and d.get('label')==r['human_label'] for d in r.get('human_decisions',[]))]
    if len(rows)!=425:raise ValueError('Exactly the existing 425 human development labels are required')
    assert_allowed([dict(r,id=r['record_id'],text_view=r['text_minimal']) for r in rows],'train',
        reservation_root=root/'outputs/phase_g/blind_test',registry=root/'data/test_reservations')
    return rows,source


def build(output=DEFAULT,root=ROOT):
    root,output=Path(root).resolve(),Path(output).resolve()
    if not output.is_relative_to(root/'outputs'):raise ValueError('Keep demo models local under outputs/')
    if output.exists():raise FileExistsError('Demo artifact already exists; use it or choose a new output')
    rows,source=training_rows(root)
    inputs={str(p):sha(p) for p in [source/'manifest.json',source/'candidate.local.jsonl']}
    # Reuse the predeclared fixed pipeline. This function constructs a model,
    # despite its historical name; it does NOT open or evaluate any gold data.
    texts=[preprocess(r['text_minimal']) for r in rows]
    labels=[r['human_label'] for r in rows]
    with staged(output) as out:
        for name in MODELS:
            model=gold_model(name)
            model.fit(texts,labels)
            joblib.dump(model,out/(name+'.joblib'))
        save(out/'model_info.json',dict(status='DEVELOPMENT_DEMO_ONLY',train_records=425,
            train_labels=dict(Counter(r['human_label'] for r in rows)),train_ids=[r['record_id'] for r in rows],
            inputs_sha256=inputs,preprocess='src.preprocessing.preprocess; vectorizer lowercase=True',
            models=MODELS,config='src.models.core.GOLD_CONFIG; fixed, no tuning',
            word_token_pattern=r'(?u)\b\w+\b',
            labels=LABELS,sklearn=sklearn.__version__,python=platform.python_version(),
            source_sha256=sha(Path(__file__)),preprocessing_sha256=sha(ROOT/'src/preprocessing/__init__.py'),
            gold_data_used=False,new_human_labels_used=False,metrics_computed=False,
            note='Manual demo predictions, not a new evaluation or approved research release. No probabilities or accuracy claim.'))
        if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Training input changed')
        seal(out,dict(kind='DEVELOPMENT_INFERENCE_DEMO',approved_release=False))
    return dict(output=str(output),train_records=425,gold_data_used=False)


def load_model(directory=DEFAULT,name='tfidf_char_svm'):
    directory=Path(directory);verify(directory);info=load(directory/'model_info.json')
    if info['status']!='DEVELOPMENT_DEMO_ONLY' or info['sklearn']!=sklearn.__version__:
        raise ValueError('Demo artifact/runtime mismatch')
    if info['preprocessing_sha256']!=sha(ROOT/'src/preprocessing/__init__.py'):
        raise ValueError('Demo preprocessing changed; do not silently use another text pipeline')
    if name not in info.get('models',{'tfidf_char_svm':None}):raise ValueError('Model not built: '+name)
    filename=name+'.joblib' if 'models' in info else 'model.joblib'
    model=joblib.load(directory/filename)  # Only use locally built, checksum-verified artifacts.
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


def menu(directory=DEFAULT,read_line=input,emit=print):
    """Select one fixed baseline or compare them on the same typed comment."""
    models={name:load_model(directory,name) for name in MODELS}
    names=list(models)
    transformers={}
    while True:
        emit('\nChon model (0 de thoat):')
        for i,name in enumerate(names,1):emit(f'{i}. {MODELS[name]}')
        emit('5. So sanh ca 4 baseline')
        emit('6. PhoBERT (demo 425 nhan)')
        emit('7. ViSoBERT (demo 425 nhan)')
        try:choice=read_line('Lua chon: ').strip()
        except (EOFError,KeyboardInterrupt):return
        if choice in ('','0'):return
        if choice not in ('1','2','3','4','5','6','7'):
            emit('Lua chon khong hop le.');continue
        if choice in ('6','7'):
            name='phobert' if choice=='6' else 'visobert'
            from .transformer_demo import TransformerPredictor
            try:
                if name not in transformers:transformers[name]=TransformerPredictor(Path(directory).parent/'demo_transformers_425'/name)
            except (ImportError, OSError, ValueError) as exc:
                emit('Khong tai duoc model: '+str(exc));continue
            active={name:transformers[name]}
        else:
            selected=names if choice=='5' else [names[int(choice)-1]]
            active={name:models[name] for name in selected}
        emit('Nhap /model de doi model; Enter trong de thoat.')
        while True:
            try:text=read_line('Nhap binh luan: ')
            except (EOFError,KeyboardInterrupt):return
            if not text.strip():return
            if text.strip()=='/model':break
            for name,model in active.items():emit(MODELS.get(name,name)+': '+predict(model,text))
