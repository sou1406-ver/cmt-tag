"""Fixed full-development Transformer demos; no validation or gold access."""
from pathlib import Path
import random
import time

from src.dataset.common import ROOT, load, save, sha, staged, seal, verify
from src.preprocessing import preprocess
from .core import LABELS
from .demo import training_rows

REPOS={'phobert':'vinai/phobert-base-v2','visobert':'uitnlp/visobert'}
CONFIG=dict(seed=20261113,epochs=3,batch_size=8,max_length=128,learning_rate=2e-5,
            weight_decay=0.01,threads=4)
DEFAULT=ROOT/'outputs/demo_transformers_425'


def text_view(text,name):
    text=preprocess(text)
    if name=='phobert':
        from pyvi import ViTokenizer
        # Explicit approximation to the recommended RDRSegmenter; identical at inference.
        text=ViTokenizer.tokenize(text)
    return text


def fit_prepared(name,snapshot,texts,labels,config,emit=print):
    """Fresh pretrained initialization; caller supplies exactly-once model views."""
    import numpy as np
    import torch
    from transformers import AutoTokenizer,AutoModelForSequenceClassification
    if not texts or len(texts)!=len(labels) or not set(labels)<=set(LABELS):raise ValueError('Invalid training rows')
    torch.set_num_threads(config['threads'])
    random.seed(config['seed']);np.random.seed(config['seed']);torch.manual_seed(config['seed'])
    tokenizer=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False,use_fast=name!='phobert')
    model=AutoModelForSequenceClassification.from_pretrained(snapshot,local_files_only=True,
        trust_remote_code=False,num_labels=3,id2label=dict(enumerate(LABELS)),label2id={v:k for k,v in enumerate(LABELS)})
    # Training must never write through a loader's file-backed parameter storage.
    # Explicitly detach every parameter from pretrained cache/memory maps.
    with torch.no_grad():
        for parameter in model.parameters():parameter.data=parameter.detach().clone()
    targets=torch.tensor([LABELS.index(label) for label in labels])
    optimizer=torch.optim.AdamW(model.parameters(),lr=config['learning_rate'],weight_decay=config['weight_decay'])
    generator=torch.Generator().manual_seed(config['seed']);losses=[];started=time.perf_counter()
    model.train()
    for epoch in range(config['epochs']):
        total=0.;seen=0;order=torch.randperm(len(texts),generator=generator).tolist()
        for start in range(0,len(texts),config['batch_size']):
            ids=order[start:start+config['batch_size']]
            batch=tokenizer([texts[i] for i in ids],padding=True,truncation=True,max_length=config['max_length'],return_tensors='pt')
            optimizer.zero_grad(set_to_none=True);loss=model(**batch,labels=targets[ids]).loss
            if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step()
            total+=loss.item()*len(ids);seen+=len(ids)
            if start%160==0:emit(f'epoch {epoch+1}/{config["epochs"]}, {seen}/{len(texts)}',flush=True)
        losses.append(total/seen);emit(f'epoch {epoch+1} loss={losses[-1]:.4f}',flush=True)
    return model,tokenizer,losses,time.perf_counter()-started


def train(name,output=None,emit=print):
    import numpy as np
    import torch
    import transformers
    from huggingface_hub import HfApi,snapshot_download
    from transformers import AutoTokenizer,AutoModelForSequenceClassification
    if name not in REPOS:raise ValueError('Unknown Transformer')
    output=Path(output) if output else DEFAULT/name
    if not output.resolve().is_relative_to(ROOT/'outputs'):raise ValueError('Keep checkpoints under outputs/')
    if output.exists():raise FileExistsError('Demo checkpoint exists; refusing overwrite')
    rows,source=training_rows()
    inputs={str(p):sha(p) for p in (source/'manifest.json',source/'candidate.local.jsonl')}
    torch.set_num_threads(CONFIG['threads'])
    random.seed(CONFIG['seed']);np.random.seed(CONFIG['seed']);torch.manual_seed(CONFIG['seed'])
    info=HfApi(token=False).model_info(REPOS[name])
    revision=info.sha
    files={f.rfilename for f in info.siblings}
    weights='model.safetensors' if 'model.safetensors' in files else 'pytorch_model.bin'
    snapshot=snapshot_download(REPOS[name],revision=revision,token=False,
        cache_dir=ROOT/'data/local_models/demo_cache',allow_patterns=[weights,'config.json',
        'tokenizer*','special_tokens_map.json','vocab.txt','bpe.codes','sentencepiece.bpe.model'])
    texts=[text_view(r['text_minimal'],name) for r in rows]
    labels=[r['human_label'] for r in rows]
    model,tokenizer,epoch_losses,elapsed=fit_prepared(name,snapshot,texts,labels,CONFIG,emit)
    if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Development input changed')
    with staged(output) as out:
        model.save_pretrained(out,safe_serialization=True);tokenizer.save_pretrained(out)
        save(out/'model_info.json',dict(status='DEVELOPMENT_DEMO_ONLY',name=name,train_records=425,
            train_ids=[r['record_id'] for r in rows],inputs_sha256=inputs,base_model=REPOS[name],
            revision=revision,config=CONFIG,labels=LABELS,train_loss=epoch_losses,
            elapsed_seconds=elapsed,torch=torch.__version__,transformers=transformers.__version__,
            preprocessing='minimal + PyVi 0.1.1 (not RDRSegmenter)' if name=='phobert' else 'minimal',
            preprocessing_sha256=sha(ROOT/'src/preprocessing/__init__.py'),
            implementation_sha256=sha(Path(__file__)),gold_data_used=False,metrics_computed=False,
            note='Fixed final epoch; no evaluation or tuning. Training losses are not accuracy.'))
        seal(out,dict(kind='DEVELOPMENT_TRANSFORMER_DEMO',approved_release=False))
    return str(output)


class TransformerPredictor:
    def __init__(self,directory):
        import torch
        from transformers import AutoTokenizer,AutoModelForSequenceClassification
        directory=Path(directory);verify(directory)
        self.info=load(directory/'model_info.json');self.name=self.info['name']
        if self.info['status']!='DEVELOPMENT_DEMO_ONLY' or self.name not in REPOS:
            raise ValueError('Not a fine-tuned demo checkpoint')
        if self.info['preprocessing_sha256']!=sha(ROOT/'src/preprocessing/__init__.py'):
            raise ValueError('Preprocessing mismatch')
        self.tokenizer=AutoTokenizer.from_pretrained(directory,local_files_only=True,trust_remote_code=False,
                                                    use_fast=self.name!='phobert')
        self.model=AutoModelForSequenceClassification.from_pretrained(directory,local_files_only=True,
                                                                      trust_remote_code=False)
        if set(self.model.config.id2label.values())!=set(LABELS):raise ValueError('Unexpected label mapping')
        torch.set_num_threads(CONFIG['threads']);self.model.eval()
        self.classes_=LABELS

    def predict(self,texts):
        import torch
        batch=self.tokenizer([text_view(t,self.name) for t in texts],padding=True,truncation=True,
                             max_length=self.info['config']['max_length'],return_tensors='pt')
        with torch.inference_mode():ids=self.model(**batch).logits.argmax(dim=-1).tolist()
        return [self.model.config.id2label[i] for i in ids]
