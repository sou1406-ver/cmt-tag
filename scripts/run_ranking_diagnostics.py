"""Frozen cross-topic LinearSVC ranking diagnostics, no target calibration."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from sklearn.metrics import roc_auc_score,average_precision_score,roc_curve,precision_recall_curve
from scripts.prepare_development import load,save,sha,write_csv
from src.baseline.bow_robustness import inputs,make_model
from src.baseline.preprocessing_experiments import offline_network
from src.baseline.core import LABELS,metrics


def aligned_scores(scores,classes):
    scores=np.asarray(scores)
    if len(classes)!=3 or set(classes)!=set(LABELS) or scores.ndim!=2 or scores.shape[1]!=3:
        raise ValueError('Expected three-class decision matrix with explicit class order')
    if not np.isfinite(scores).all():raise ValueError('Nonfinite decision score')
    return scores[:,[list(classes).index(label) for label in LABELS]]


def ranking(y,scores):
    result={};y=np.asarray(y)
    for index,label in enumerate(LABELS):
        binary=(y==label).astype(int);support=int(binary.sum());negative=len(y)-support
        row=dict(support=support,negative_support=negative,prevalence=support/len(y),
                 average_precision_baseline=support/len(y),score_quantiles={})
        for truth in LABELS:
            values=scores[y==truth,index]
            row['score_quantiles'][truth]=np.quantile(values,[0,.25,.5,.75,1]).tolist() if len(values) else None
        if not support or not negative:
            row.update(status='undefined_single_binary_class',roc_auc=None,average_precision=None)
        else:
            fpr,tpr,_=roc_curve(binary,scores[:,index]);precision,recall,_=precision_recall_curve(binary,scores[:,index])
            row.update(status='limited_support' if min(support,negative)<20 else 'descriptive',
                       roc_auc=float(roc_auc_score(binary,scores[:,index])),
                       average_precision=float(average_precision_score(binary,scores[:,index])),
                       roc=dict(fpr=fpr.tolist(),tpr=tpr.tolist()),pr=dict(precision=precision.tolist(),recall=recall.tolist()))
        result[label]=row
    return result


def plots(output,direction,y,scores,summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for kind in ('roc','pr','scores'):
        fig,axes=plt.subplots(1,3,figsize=(13,4.3))
        fig.subplots_adjust(left=.055,right=.99,bottom=.17,top=.73,wspace=.30)
        for index,(axis,label) in enumerate(zip(axes,LABELS)):
            row=summary[label];axis.set_title(f'{label}: n+={row["support"]}, prevalence={row["prevalence"]:.3f}',fontsize=10)
            if kind=='scores':
                low,high=scores[:,index].min(),scores[:,index].max()
                if low==high:low-=.5;high+=.5
                bins=np.linspace(low,high,16)
                for truth in LABELS:
                    values=scores[np.asarray(y)==truth,index]
                    if len(values):axis.hist(values,bins=bins,density=True,histtype='step',label=f'true {truth} (n={len(values)})')
                axis.set_xlabel('Uncalibrated decision score');axis.set_ylabel('Density within true class')
            elif 'roc' in row:
                if kind=='roc':
                    axis.plot(row['roc']['fpr'],row['roc']['tpr'],label=f'AUC={row["roc_auc"]:.3f}')
                    axis.plot([0,1],[0,1],'--',color='gray');axis.set_xlabel('False positive rate');axis.set_ylabel('True positive rate')
                else:
                    axis.step(row['pr']['recall'],row['pr']['precision'],where='post',label=f'AP={row["average_precision"]:.3f}')
                    axis.axhline(row['prevalence'],ls='--',color='gray',label='Prevalence baseline')
                    axis.set_xlabel('Recall');axis.set_ylabel('Precision')
                axis.set_xlim(0,1);axis.set_ylim(0,1.02)
            axis.legend(fontsize=8);axis.grid(alpha=.2)
        fig.suptitle(direction+'\nDevelopment diagnostic, no target tuning',fontsize=12,y=.97)
        fig.savefig(output/(direction+'_'+kind+'.png'),dpi=160)
        fig.savefig(output/(direction+'_'+kind+'.pdf'))
        plt.close(fig)


def run(config_path,output):
    output=Path(output).resolve();cfg=load(config_path);config_sha=sha(config_path)
    if cfg['model_id']!='tfidf_char_svm' or cfg['threshold_tuning'] is not False:raise ValueError('Frozen char-SVM only, no target tuning')
    source=(ROOT/cfg['e1_root']).resolve()
    if output.exists():raise FileExistsError('Do not overwrite existing artifacts')
    if source in output.parents:raise ValueError('Keep E.2 outside immutable E.1')
    if sha(source/'manifest.json')!=cfg['e1_manifest_sha256']:raise ValueError('E.1 manifest changed')
    manifest=load(source/'manifest.json')
    def verify():
        if sha(source/'manifest.json')!=cfg['e1_manifest_sha256']:raise ValueError('E.1 manifest changed')
        for name,value in manifest['output_sha256'].items():
            if Path(name).name!=name or sha(source/name)!=value:raise ValueError('E.1 artifact changed')
    verify();e1cfg=load(source/'config.json');rows,_,_,oldcfg=inputs(e1cfg);by={r['id']:r for r in rows}
    spec=next(s for s in e1cfg['models'] if s['id']==cfg['model_id'])
    diagnostics=load(source/'transfer_diagnostics.json');all_scores=[];results=[]
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ranking-',dir=output.parent) as temp,offline_network():
        staged=Path(temp)/'run';staged.mkdir()
        shutil.copyfile(config_path,staged/'config.json');shutil.copyfile(source/'manifest.json',staged/'e1_manifest.json')
        for d in diagnostics:
            if d['status']=='skipped':
                results.append(dict(direction=d['direction'],status='skipped',reasons=d['skip_reasons']));continue
            pipeline=make_model(spec,e1cfg,oldcfg);train=d['train_ids'];valid=d['evaluation_ids']
            pipeline.fit([by[i]['text_raw'] for i in train],[by[i]['label'] for i in train])
            x=[by[i]['text_raw'] for i in valid];y=[by[i]['label'] for i in valid]
            pred=pipeline.predict(x).tolist();classes=pipeline['model'].classes_.tolist()
            native_scores=pipeline.decision_function(x)
            scores=aligned_scores(native_scores,classes)
            if [classes[i] for i in native_scores.argmax(axis=1)]!=pred:raise ValueError('Decision columns disagree with predict')
            original=next(r for r in d['results'] if r['model_id']==cfg['model_id'])
            classification=metrics(y,pred)
            if classification!=original['metrics']:raise ValueError('Classification differs from E.1')
            summary=ranking(y,scores)
            results.append(dict(direction=d['direction'],status='limited_development_diagnostic',support=d['support'],
                native_class_order=classes,export_class_order=LABELS,classification=classification,ranking=summary,
                independent_test=False,threshold_tuning=False))
            for rid,truth,guess,values in zip(valid,y,pred,scores):
                all_scores.append(dict(direction=d['direction'],id=rid,human_label=truth,predicted_label=guess,
                                       **{label+'_score':float(v) for label,v in zip(LABELS,values)}))
            plots(staged,d['direction'],y,scores,summary)
        save(staged/'results.json',results)
        write_csv(staged/'decision_scores.csv',all_scores,['direction','id','human_label','predicted_label',*[c+'_score' for c in LABELS]])
        comparison=[]
        for r in results:
            if r['status']=='skipped':continue
            for label,v in r['ranking'].items():comparison.append(dict(direction=r['direction'],label=label,
                **{k:v[k] for k in ('support','negative_support','prevalence','roc_auc','average_precision','status')}))
        write_csv(staged/'ranking_comparison.csv',comparison,['direction','label','support','negative_support','prevalence','roc_auc','average_precision','status'])
        verify();inputs(e1cfg)
        if sha(config_path)!=config_sha:raise ValueError('Config changed during run')
        save(staged/'manifest.json',dict(purpose='cross_domain_ranking_development_only',independent_test=False,
            threshold_tuning=False,e1_manifest_sha256=cfg['e1_manifest_sha256'],config_sha256=config_sha,
            output_sha256={p.name:sha(p) for p in staged.iterdir()}))
        staged.rename(output)
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'configs/ranking_diagnostics.json')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/phase_e2')
    args=parser.parse_args()
    try:run(args.config,args.output)
    except (ValueError,OSError,KeyError) as exc:parser.exit(2,f'{type(exc).__name__}: {exc}\n')
