import argparse
import re
import unicodedata

import pandas as pd

TEENCODE = {
    "lm": "làm", "lmj": "làm gì", "lmf": "làm gì",
    "rv": "review", "rev": "review", "rview": "review",
    "hnay": "hôm nay", "hqua": "hôm qua",
    "gr": "group", "grup": "group", "grưp": "group",
    "k": "không", "ko": "không", "kh": "không", "kg": "không",
    "khong": "không", "hok": "không", "hong": "không", "hông": "không",
    "dc": "được", "đc": "được", "dk": "được", "duoc": "được",
    "vs": "với", "vơi": "với",
    "mn": "mọi người", "mng": "mọi người",
    "ng": "người", "ngừoi": "người",
    "ms": "mới", "ns": "nói", "nx": "nữa", "nt": "nhắn tin",
    "e": "em", "a": "anh", "c": "chị", "b": "bạn", "t": "tôi", "m": "mày",
    "r": "rồi", "z": "vậy", "j": "gì", "ji": "gì", "gi": "gì",
    "iu": "yêu", "bt": "bình thường", "bik": "biết", "bjk": "biết",
    "h": "giờ", "ah": "à", "ak": "à", "ạk": "ạ",
    "fim": "phim", "fjm": "phim", "film": "phim",
    "ntn": "như thế nào", "trc": "trước",
    "cx": "cũng", "cũg": "cũng", "ok": "ổn", "oke": "ổn",
    "vcl": "rất", "vl": "rất",
    "đth": "điện thoại", "dt": "điện thoại",
    "vn": "việt nam", "tui": "tôi", "tụi": "bọn", "ae": "anh em",
    "ad": "quản trị viên", "admin": "quản trị viên",
    "ngta": "người ta", "nta": "người ta", "mik": "mình",
    "cmt": "bình luận", "cmn": "rất",
    "nma": "nhưng mà", "nhma": "nhưng mà", "nch": "nói chung",
    "bth": "bình thường", "bthg": "bình thường", "bthuong": "bình thường",
    "cg": "cũng", "sv": "sinh viên", "hs": "học sinh", "gv": "giáo viên",
    "ls": "lịch sử", "lsu": "lịch sử", "vd": "ví dụ", "vdu": "ví dụ",
    "fb": "facebook", "yt": "youtube", "sp": "sản phẩm", "pk": "phải không",
    "sr": "xin lỗi", "tks": "cảm ơn", "thks": "cảm ơn",
    "okla": "ổn", "okie": "ổn",
    "vkl": "rất", "vcc": "rất", "vch": "rất", "đhs": "rất", "sml": "rất",
    "ck": "chồng", "vk": "vợ", "bn": "bao nhiêu", "kb": "không biết",
    "clgt": "cái gì thế", "dag": "đang", "dg": "đang",
}

STOP_WORDS = {
    "là", "của", "và", "các", "có", "được", "cho", "trong", "một", "những",
    "với", "để", "này", "đó", "khi", "cũng", "đã", "sẽ", "đang", "thì",
    "mà", "nhưng", "nên", "vì", "do", "bởi", "tại", "ở", "từ", "đến",
    "về", "ra", "vào", "lên", "xuống", "qua", "lại", "nữa", "rồi",
    "ai", "gì", "nào", "sao", "đâu", "bao", "nhiêu",
    "tôi", "tao", "mình", "bạn", "anh", "chị", "em", "nó", "họ",
    "chúng", "ta", "mày", "người", "ông", "bà", "cô", "chú",
    "ạ", "à", "ơi", "nhé", "nha", "nhỉ", "đấy", "ấy", "thôi", "luôn",
    "vậy", "thế", "ý", "cái", "con", "chiếc", "việc",
}

TU_PHU_DINH = {"không", "chẳng", "chưa", "đừng", "chả", "đéo", "méo", "khỏi"}
STOP_WORDS -= TU_PHU_DINH

GO_DAU = {
    "oà": "òa", "oá": "óa", "oả": "ỏa", "oã": "õa", "oạ": "ọa",
    "oè": "òe", "oé": "óe", "oẻ": "ỏe", "oẽ": "õe", "oẹ": "ọe",
    "uỳ": "ùy", "uý": "úy", "uỷ": "ủy", "uỹ": "ũy", "uỵ": "ụy",
}
_RE_GO_DAU = re.compile("(" + "|".join(GO_DAU) + r")(?![\wÀ-ỹ])", re.IGNORECASE)

_RE_AN_DANH = re.compile(
    r"^\s*(?:người tham gia ẩn danh|người dùng ẩn danh|thành viên ẩn danh"
    r"|anonymous participant|anonymous member|anonymous user)\s*\d*\s*",
    re.IGNORECASE)


def b0_an_danh(t):
    return _RE_AN_DANH.sub("", t)


def b1_unicode(t):
    return unicodedata.normalize("NFC", t)


def b2_go_dau(t):
    return _RE_GO_DAU.sub(lambda m: GO_DAU[m.group(1).lower()], t)


def b3_thuong(t):
    return t.lower()


def b4_lap(t):
    return re.sub(r"(.)\1{2,}", r"\1", t)


def b5_dau_cau(t):
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\d+", " ", t)
    return " ".join(t.split())


def b6_teencode(t):
    return " ".join(TEENCODE.get(w, w) for w in t.split())


def b7_tach_tu(t, tokenizer):
    return tokenizer(t) if tokenizer else t


def b8_stopword(t):
    return " ".join(w for w in t.split()
                    if w.replace("_", " ") not in STOP_WORDS)


def xu_ly(t, tokenizer=None, bo_stopword=True):
    t = b1_unicode(str(t))
    t = b0_an_danh(t)
    t = b2_go_dau(t)
    t = b3_thuong(t)
    t = b4_lap(t)
    t = b5_dau_cau(t)
    t = b6_teencode(t)
    t = b7_tach_tu(t, tokenizer)
    if bo_stopword:
        t = b8_stopword(t)
    return " ".join(t.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--cot", default=None)
    ap.add_argument("--giu-stopword", action="store_true")
    ap.add_argument("--khong-tach-tu", action="store_true")
    ap.add_argument("--min-tu", type=int, default=1)
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    d = pd.read_csv(args.file)
    if args.cot and args.cot in d.columns:
        cot = args.cot
    elif "text" in d.columns:
        cot = "text"
    else:
        d = pd.read_csv(args.file, header=None, names=["text"])
        cot = "text"
        print("  (file khong co header -> doc lai voi header=None)")

    goc = d[cot].astype(str)
    print(f"  {len(d)} dong | cot '{cot}'")

    tokenizer = None
    if not args.khong_tach_tu:
        from pyvi import ViTokenizer
        tokenizer = ViTokenizer.tokenize

    d["clean"] = [xu_ly(t, tokenizer, not args.giu_stopword) for t in goc]

    so_tu = d["clean"].str.split().str.len().fillna(0)
    it_tu = so_tu <= args.min_tu
    mau_bo = d.loc[it_tu, "clean"].head(6).tolist()
    rong = int((so_tu == 0).sum())
    n_it = int(it_tu.sum())
    d = d[~it_tu]

    trung = d["clean"].duplicated()
    mau_trung = d.loc[trung, "clean"].head(4).tolist()
    n_trung = int(trung.sum())
    d = d[~trung]

    out = args.out or (args.file.rsplit(".", 1)[0] + "_daxuly.csv")
    d.to_csv(out, index=False, encoding="utf-8-sig")

    tu_goc = set(w for s in goc for w in s.lower().split())
    tu_moi = set(w for s in d["clean"] for w in s.split())
    dai_goc = goc.str.split().str.len().mean()
    dai_moi = d["clean"].str.split().str.len().mean()

    print(f"\n  tu vung  : {len(tu_goc):>6} -> {len(tu_moi):>6} "
          f"(giam {(1-len(tu_moi)/len(tu_goc))*100:.0f}%)")
    print(f"  so tu/cau: {dai_goc:>6.1f} -> {dai_moi:>6.1f}")
    print(f"  bo {n_it} dong con <= {args.min_tu} tu ({rong} dong rong)")
    if mau_bo:
        print("    vd: " + " | ".join(repr(x) for x in mau_bo))
    print(f"  bo {n_trung} dong trung nhau sau xu ly")
    if mau_trung:
        print("    vd: " + " | ".join(repr(x[:38]) for x in mau_trung))
    print(f"  con lai  : {len(d)} dong -> {out}\n")

    for g, c in list(zip(goc, d["clean"]))[:4]:
        print(f"    goc : {g[:74]}")
        print(f"    sach: {c[:74]}\n")


if __name__ == "__main__":
    main()