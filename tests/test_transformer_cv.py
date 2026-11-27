import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.dataset.common import save,sha
from src.models.transformer_cv import view_roster,prepare,verified_pretrained
from src.models.transformer_demo import fit_prepared


class TransformerCVTests(unittest.TestCase):
    def test_verified_cache_is_immutable_and_does_not_require_remote_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'data/local_models/cv_verified_cache'
            folder=cache/'models--uitnlp--visobert/snapshots/revision';folder.mkdir(parents=True)
            weights=folder/'model.safetensors';weights.write_bytes(b'fixture weights')
            save(cache/'visobert_verified.json',dict(revision='revision',files={'model.safetensors':sha(weights)}))
            self.assertEqual(verified_pretrained('visobert','revision',root),folder)
            weights.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'cache changed'):verified_pretrained('visobert','revision',root)
    def rows(self):
        rows=[dict(record_id='a',role='human',group_id='post:a'),
              dict(record_id='b',role='human',group_id='post:b'),
              dict(record_id='c',role='silver',group_id='post:c')]
        views={'a':'unique train','b':'validation text','c':'validation text'}
        fold=dict(baseline_train_ids=['a'],augmented_train_ids=['a','c'],validation_ids=['b'])
        return rows,views,fold

    def test_transformed_silver_duplicate_is_excluded_only_from_train(self):
        rows,views,fold=self.rows()
        tr,va,drop=view_roster(rows,views,fold,'human_plus_silver')
        self.assertEqual((tr,va,drop),(['a'],['b'],['c']))
        self.assertEqual(view_roster(rows,views,fold,'human_only'),(['a'],['b'],[]))

    def test_human_collision_and_post_leak_fail_closed(self):
        rows,views,fold=self.rows();views['a']=views['b']
        with self.assertRaisesRegex(ValueError,'Transformed human'):view_roster(rows,views,fold,'human_only')
        views['a']='unique';rows[0]['group_id']='post:b'
        with self.assertRaisesRegex(ValueError,'Post group'):view_roster(rows,views,fold,'human_only')

    def test_gold_protocol_refused_before_reading_training_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'cfg.json';save(config,dict(gold_allowed=True,approved_release=False,n_splits=5))
            with patch('src.models.transformer_cv.read_jsonl') as read:
                with self.assertRaisesRegex(ValueError,'Development'):prepare(root/'reference',root/'outputs/run',config,root)
                read.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('transformers'),'Optional Transformer runtime')
    def test_real_tiny_fit_starts_fresh_and_reproduces_seed(self):
        import torch
        from transformers import BertConfig,BertForSequenceClassification
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            model=BertForSequenceClassification(BertConfig(vocab_size=20,hidden_size=8,num_hidden_layers=1,
                num_attention_heads=2,intermediate_size=16,num_labels=3))
            model.save_pretrained(root,safe_serialization=False)
            checkpoint_sha=sha(root/'pytorch_model.bin')
            def tokenizer(texts,**kwargs):
                return dict(input_ids=torch.ones((len(texts),4),dtype=torch.long),attention_mask=torch.ones((len(texts),4),dtype=torch.long))
            cfg=dict(threads=1,seed=42,epochs=1,batch_size=2,max_length=16,learning_rate=2e-5,weight_decay=.01)
            with patch('transformers.AutoTokenizer.from_pretrained',return_value=tokenizer):
                a,_,loss_a,_=fit_prepared('visobert',root,['one','two','three'],['POS','NEG','NEU'],cfg,lambda *a,**k:None)
                b,_,loss_b,_=fit_prepared('visobert',root,['one','two','three'],['POS','NEG','NEU'],cfg,lambda *a,**k:None)
            self.assertEqual(loss_a,loss_b)
            self.assertEqual(sha(root/'pytorch_model.bin'),checkpoint_sha)
            self.assertTrue(all(torch.equal(v,b.state_dict()[k]) for k,v in a.state_dict().items()))
            # Windows keeps safetensors memory maps open while model tensors live.
            del a,b,model
            import gc
            gc.collect()


if __name__=='__main__':unittest.main()
