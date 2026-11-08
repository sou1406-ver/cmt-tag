import argparse
import json
import pickle

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

CAU_HINH = {
    "bow_1gram": dict(kieu="bow", ngram_range=(1, 1)),
    "bow_12gram": dict(kieu="bow", ngram_range=(1, 2)),
    "tfidf_1gram": dict(kieu="tfidf", ngram_range=(1, 1)),
    "tfidf_12gram": dict(kieu="tfidf", ngram_range=(1, 2)),
}

W2V_DIM = 50
W2V_WINDOW = 5
W2V_EPOCHS = 100
W2V_MIN_COUNT = 2
W2V_SG = 0

PPMI_WINDOW = 5
PPMI_DIM = 50
PPMI_ALPHA = 0.75
PPMI_K = 5
PPMI_MIN_COUNT = 2


def tao_vectorizer(kieu, **kw):
    if kieu == "bow":
        return CountVectorizer(**kw)
    return TfidfVectorizer(sublinear_tf=True, **kw)


def top_tu(vec, X, n=12):
    ten = vec.get_feature_names_out()
    tong = X.sum(axis=0).A1
    idx = tong.argsort()[::-1][:n]
    return [(ten[i], float(tong[i])) for i in idx]


def train_w2v(docs, seed=42):
    from gensim.models import Word2Vec
    cau = [s.split() for s in docs]
    m = Word2Vec(cau, vector_size=W2V_DIM, window=W2V_WINDOW,
                 min_count=W2V_MIN_COUNT, workers=4, epochs=W2V_EPOCHS,
                 sg=W2V_SG, seed=seed)
    return m


def nap_w2v_san(duong_dan):
    from gensim.models import KeyedVectors
    kv = KeyedVectors.load_word2vec_format(duong_dan, binary=duong_dan.endswith(".bin"))

    class Bao:
        wv = kv
    return Bao()


class EmbPPMI:
    def __init__(self, tu, E):
        self.tu = tu
        self.idx = {w: i for i, w in enumerate(tu)}
        self.E = E
        self.vector_size = E.shape[1]

    def __contains__(self, w):
        return w in self.idx

    def __getitem__(self, w):
        return self.E[self.idx[w]]

    def __len__(self):
        return len(self.tu)

    def most_similar(self, w, topn=5):
        if w not in self.idx:
            return []
        s = self.E @ self.E[self.idx[w]]
        s[self.idx[w]] = -9
        return [(self.tu[i], float(s[i])) for i in s.argsort()[::-1][:topn]]


def train_ppmi_svd(docs):
    from collections import Counter
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize

    cau = [s.split() for s in docs]
    dem = Counter(w for c in cau for w in c)
    tu = [w for w, c in dem.items() if c >= PPMI_MIN_COUNT]
    idx = {w: i for i, w in enumerate(tu)}
    V = len(tu)

    r, c, v = [], [], []
    for s in cau:
        ids = [idx[w] for w in s if w in idx]
        for i, a in enumerate(ids):
            lo = max(0, i - PPMI_WINDOW)
            hi = min(len(ids), i + PPMI_WINDOW + 1)
            for j in range(lo, hi):
                if i != j:
                    r.append(a)
                    c.append(ids[j])
                    v.append(1.0 / abs(i - j))

    M = sparse.coo_matrix((v, (r, c)), shape=(V, V)).tocsr()
    hang = np.asarray(M.sum(1)).ravel()
    cot = np.asarray(M.sum(0)).ravel()
    cot_s = cot ** PPMI_ALPHA
    tong, tong_s = M.sum(), cot_s.sum()

    M = M.tocoo()
    pmi = np.log((M.data / tong)
                 / ((hang[M.row] / tong) * (cot_s[M.col] / tong_s)) + 1e-12)
    pmi -= np.log(PPMI_K)
    pmi[pmi < 0] = 0
    P = sparse.coo_matrix((pmi, (M.row, M.col)), shape=(V, V)).tocsr()
    P.eliminate_zeros()

    E = normalize(TruncatedSVD(n_components=PPMI_DIM,
                               random_state=42).fit_transform(P))

    class Bao:
        wv = EmbPPMI(tu, E)
    return Bao()


def vec_tai_lieu(model, docs, idf=None):
    dim = model.wv.vector_size
    out = np.zeros((len(docs), dim), dtype=np.float32)
    for i, s in enumerate(docs):
        v, tong = np.zeros(dim, dtype=np.float32), 0.0
        for w in s.split():
            if w in model.wv:
                tr = idf.get(w, 1.0) if idf else 1.0
                v += model.wv[w] * tr
                tong += tr
        if tong:
            out[i] = v / tong
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="records.jsonl tu prepare-data; khong dung CSV toan corpus")
    ap.add_argument("--split-manifest", required=True, help="manifest.json cung data version")
    ap.add_argument("--near-duplicates", required=True, help="near_duplicates.jsonl cung data version")
    ap.add_argument("--cot", default="text")
    ap.add_argument("--min-df", type=int, default=2)
    ap.add_argument("--max-features", type=int, default=None)
    ap.add_argument("--khong-w2v", action="store_true")
    ap.add_argument("--w2v-file", default=None)
    ap.add_argument("--ppmi", action="store_true")
    ap.add_argument("-o", "--out", default="dac_trung.pkl")
    args = ap.parse_args()

    from src.data.split import validate_manifest

    with open(args.file, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    with open(args.split_manifest, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(args.near_duplicates, encoding="utf-8") as f:
        candidates = [json.loads(line) for line in f if line.strip()]
    validate_manifest(records, candidates, manifest)
    train_ids = {e["id"] for e in manifest["entries"]
                 if e["split"] == "train" and e["eligible_for_annotation"]}
    d = pd.DataFrame(r for r in records if r["id"] in train_ids)
    if d.empty:
        ap.error("train pool rong")
    if args.cot not in d.columns:
        print(f"khong co cot '{args.cot}'. Cac cot: {list(d.columns)}")
        return
    docs = d[args.cot].fillna("").astype(str).tolist()
    print(f"  {len(d)} dong TRAIN ONLY | cot '{args.cot}' | chua phai thuc nghiem gold\n")

    ket_qua = {}
    print(f"  {'cau hinh':<16}{'dac trung':>11}{'do thua':>10}{'tb/cau':>9}")
    print("  " + "-" * 46)
    for ten, cfg in CAU_HINH.items():
        kw = {k: v for k, v in cfg.items() if k != "kieu"}
        kw["min_df"] = args.min_df
        if args.max_features:
            kw["max_features"] = args.max_features
        vec = tao_vectorizer(cfg["kieu"], **kw)
        X = vec.fit_transform(docs)
        thua = 100 * (1 - X.nnz / (X.shape[0] * X.shape[1]))
        print(f"  {ten:<16}{X.shape[1]:>11,}{thua:>9.2f}%{X.nnz / X.shape[0]:>9.1f}")
        ket_qua[ten] = {"vec": vec, "X": X}

    model = None
    if not args.khong_w2v:
        if args.w2v_file:
            model = nap_w2v_san(args.w2v_file)
            cach = args.w2v_file
        elif args.ppmi:
            model = train_ppmi_svd(docs)
            cach = f"PPMI+SVD (alpha={PPMI_ALPHA}, k={PPMI_K})"
        else:
            try:
                model = train_w2v(docs)
                cach = f"Word2Vec CBOW {W2V_EPOCHS} epochs"
            except ImportError:
                print("  (khong co gensim -> dung PPMI+SVD)")
                model = train_ppmi_svd(docs)
                cach = f"PPMI+SVD (alpha={PPMI_ALPHA}, k={PPMI_K})"
        tfidf = ket_qua["tfidf_1gram"]["vec"]
        idf = dict(zip(tfidf.get_feature_names_out(), tfidf.idf_))
        Xw = vec_tai_lieu(model, docs, idf)
        print(f"  {'emb_tfidf':<16}{Xw.shape[1]:>11,}{0.0:>9.2f}%{Xw.shape[1]:>9.1f}")
        ket_qua["emb_tfidf"] = {"vec": None, "X": Xw}

    print()
    for ten in ["bow_1gram", "tfidf_1gram"]:
        v, X = ket_qua[ten]["vec"], ket_qua[ten]["X"]
        nhan = "tan suat" if ten.startswith("bow") else "tong tf-idf"
        print(f"  TOP 12 theo {nhan} ({ten}):")
        print("    " + "  ".join(w for w, _ in top_tu(v, X)))
        print()

    v, X = ket_qua["tfidf_12gram"]["vec"], ket_qua["tfidf_12gram"]["X"]
    bi = [(w, s) for w, s in top_tu(v, X, 400) if " " in w][:12]
    print("  TOP 12 BIGRAM (tfidf_12gram):")
    print("    " + "  |  ".join(w for w, _ in bi))
    print()

    if model is not None:
        print(f"  EMB: {len(model.wv):,} tu | {model.wv.vector_size} chieu | {cach}")
        for t in ["hay", "chán", "khóc", "chiến_tranh"]:
            if t in model.wv:
                gan = ", ".join(w for w, _ in model.wv.most_similar(t, topn=5))
                print(f"    gan nhat voi '{t}': {gan}")
        print()

    with open(args.out, "wb") as f:
        pickle.dump({k: {"vec": v["vec"], "shape": v["X"].shape}
                     for k, v in ket_qua.items()}, f)
    for ten, v in ket_qua.items():
        if sparse.issparse(v["X"]):
            sparse.save_npz(f"X_{ten}.npz", v["X"])
        else:
            np.save(f"X_{ten}.npy", v["X"])
    if model is not None and hasattr(model, "save") and not args.w2v_file:
        model.save("w2v.model")
    print(f"  da luu vectorizer -> {args.out}")
    print(f"  da luu ma tran    -> X_<cau_hinh>.npz / .npy")


if __name__ == "__main__":
    main()
