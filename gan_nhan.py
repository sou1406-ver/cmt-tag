import argparse
from pathlib import Path
import re

import pandas as pd

KHEN = {
    "hay": 1.0, "tuyệt_vời": 1.5, "tuyệt": 1.2, "xuất_sắc": 1.5, "đỉnh": 1.2,
    "đáng_xem": 1.5, "cảm_động": 1.2, "xúc_động": 1.2, "tự_hào": 1.2,
    "ý_nghĩa": 1.0, "chân_thực": 1.0, "ấn_tượng": 1.0, "mãn_nhãn": 1.2,
    "chất_lượng": 1.0, "yêu": 1.0, "thích": 1.0, "khen": 0.8, "biết_ơn": 1.0,
    "trân_trọng": 1.0, "ổn": 0.8, "đáng": 0.6, "hài_lòng": 1.2, "nể": 1.0,
    "phục": 0.8, "đẹp": 1.0, "sâu_sắc": 1.2, "hào_hùng": 1.0,
    "thành_công": 1.0, "xứng_đáng": 1.2, "chúc_mừng": 1.0, "đỉnh_cao": 1.2,
    "mượt": 0.8, "hoàn_hảo": 1.5, "tinh_tế": 1.0, "lay_động": 1.2,
    "truyền_cảm_hứng": 1.2, "đáng_tiền": 1.2, "đáng_khen": 1.2,
    "ngưỡng_mộ": 1.2, "cảm_ơn": 0.8, "cám_ơn": 0.8, "anh_dũng": 0.8,
    "kính_phục": 1.2, "khâm_phục": 1.2, "đáng_quý": 1.0,
}

CHE = {
    "dở": -1.2, "chán": -1.2, "tệ": -1.5, "xàm": -1.5, "nhạt": -1.0,
    "sạn": -1.0, "hạt_sạn": -1.0, "lỗ_hổng": -1.0, "phi_lý": -1.2,
    "cường_điệu": -0.8, "thất_vọng": -1.5, "bôi_bác": -1.5, "lố": -1.0,
    "gượng": -0.8, "sượng": -1.0, "kém": -1.2, "yếu": -0.8, "tiếc": -0.5,
    "sến": -1.0, "lê_thê": -1.0, "dài_dòng": -0.8, "khó_hiểu": -0.8,
    "rời_rạc": -1.0, "hụt_hẫng": -1.0, "bực": -1.2, "lừa": -1.2,
    "bịp": -1.5, "vớ_vẩn": -1.5, "nhảm": -1.5, "ngớ_ngẩn": -1.5,
    "thua": -0.6, "dìm": -1.0, "phí": -1.0, "nát": -1.2, "ẩu": -1.2,
    "giả_tạo": -1.2, "khiên_cưỡng": -1.0,
    "hèn": -1.0, "dơ": -1.0, "bẩn": -0.8, "nhàm": -1.2, "nhảm_nhí": -1.5,
    "thảm_hại": -1.5, "qua_loa": -1.0,
}

CAM_XUC = {
    "khóc": 0.5, "thương": 0.5, "nước_mắt": 0.5, "ám_ảnh": 0.4,
    "rưng_rưng": 0.5, "nghẹn_ngào": 0.5, "xót": 0.4, "nghẹn": 0.4,
    "sướt_mướt": 0.5, "nổi_da_gà": 0.5, "xót_xa": 0.5, "nghẹn_lại": 0.4,
}

PHU_DINH = {"không", "chẳng", "chưa", "chả", "đừng", "khỏi", "đéo", "méo"}
CUA_SO_PHU_DINH = 3

TANG = {"rất": 1.5, "quá": 1.4, "cực": 1.6, "siêu": 1.6, "vô_cùng": 1.6,
        "thật_sự": 1.3, "cực_kỳ": 1.6}
GIAM = {"hơi": 0.6, "khá": 0.8, "tạm": 0.6, "cũng": 0.8}

TU_DIEN = {}
TU_DIEN.update(KHEN)
TU_DIEN.update(CHE)
TU_DIEN.update(CAM_XUC)

CHU_DE = (
    r"phim|mưa\s*đỏ|diễn\s*viên|rạp|cảnh|kịch\s*bản|đạo\s*diễn|nhạc|chiếu"
    r"|nhân\s*vật|xem|tiểu\s*thuyết|ê\s*kíp|ekip|trailer|vai|thoại|quay"
    r"|chiến\s*tranh|lính|bộ\s*đội|chiến\s*sĩ|quảng\s*trị|thành\s*cổ"
    r"|hy\s*sinh|hi\s*sinh|liệt\s*sĩ|cựu\s*chiến\s*binh|ccb|lịch\s*sử"
    r"|ông\s*cha|cha\s*ông|đồng\s*đội|trận|bom|đạn|súng|hành\s*quân"
    r"|kháng\s*chiến|tổ\s*quốc|đất\s*nước|hòa\s*bình|hoà\s*bình|anh\s*hùng"
    r"|giải\s*phóng|mỹ|ngụy|nguỵ|vnch|sông\s*thạch\s*hãn|thạch\s*hãn"
    r"|tạ|cường|hồng|sen|hải|bình|quang|tấn|đaqđ|điện\s*ảnh|vtv|tv360"
)
_RE_CHU_DE = re.compile(CHU_DE, re.IGNORECASE)

DOI_LAP = re.compile(r"\bnhưng\b|\btuy\b|\bmặc dù\b|\bcó điều\b|\bsong\b"
                     r"|\bthế mà\b|\bvậy mà\b", re.IGNORECASE)
MIA = re.compile(r"=\)\)|:\)\)|:v\b|kkk|hài vl|buồn cười|cười ỉa", re.IGNORECASE)
HOI = re.compile(r"\?|\bcho hỏi\b|\bai biết\b|\bkhi nào\b|\bở đâu\b"
                 r"|\blàm sao\b|\bthế nào\b", re.IGNORECASE)


def cham_diem(s):
    tu = s.split()
    duong = am = 0.0
    hit = 0
    for i, w in enumerate(tu):
        if w not in TU_DIEN:
            continue
        v = TU_DIEN[w]
        hit += 1
        for j in range(max(0, i - CUA_SO_PHU_DINH), i):
            if tu[j] in PHU_DINH:
                v = -v * 0.8
                break
        for j in range(max(0, i - 2), i):
            if tu[j] in TANG:
                v *= TANG[tu[j]]
                break
            if tu[j] in GIAM:
                v *= GIAM[tu[j]]
                break
        if v > 0:
            duong += v
        else:
            am += v
    return duong, am, hit


def gan(goc, sach, nguong, nguong_hard):
    duong, am, hit = cham_diem(sach)
    diem = duong + am
    co_chu_de = bool(_RE_CHU_DE.search(goc))

    if duong >= nguong_hard and -am >= nguong_hard:
        return "hard", diem, hit, 0.5
    if DOI_LAP.search(goc) and hit >= 2 and duong > 0 and am < 0:
        return "hard", diem, hit, 0.5
    if MIA.search(goc) and am < -nguong:
        return "hard", diem, hit, 0.4

    if hit == 0 and not co_chu_de:
        return "unrelated", 0.0, 0, 0.3

    tin = min(abs(diem) / 2.0, 1.0)
    if diem >= nguong:
        return "positive", diem, hit, tin
    if diem <= -nguong:
        return "negative", diem, hit, tin
    return "neutral", diem, hit, tin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--cot", default="clean")
    ap.add_argument("--cot-goc", default="text")
    ap.add_argument("--nguong", type=float, default=0.8)
    ap.add_argument("--nguong-hard", type=float, default=0.8)
    ap.add_argument("--chia", type=int, default=0)
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    if args.chia < 0:
        ap.error("--chia phai >= 0")
    out = args.out or (args.file.rsplit(".", 1)[0] + "_gannhan.csv")
    targets = [Path(out)]
    if args.chia:
        if Path(out).suffix.lower() != ".csv":
            ap.error("--chia yeu cau output .csv")
        targets.extend(Path(out).with_name(f"{Path(out).stem}_phan{i+1}.csv") for i in range(args.chia))
    if any(p.exists() or p.resolve() == Path(args.file).resolve() for p in targets):
        ap.error("khong ghi de input/output cu; chon -o la file moi")

    print("LEGACY: nhan luat chua kiem dinh; do_tin KHONG phai xac suat; khong dung lam gold.")

    d = pd.read_csv(args.file)
    for c in (args.cot, args.cot_goc):
        if c not in d.columns:
            print(f"khong co cot '{c}'. Cac cot: {list(d.columns)}")
            return

    kq = [gan(str(g), str(s), args.nguong, args.nguong_hard)
          for g, s in zip(d[args.cot_goc].fillna(""), d[args.cot].fillna(""))]
    d["nhan_may"] = [a for a, _, _, _ in kq]
    d["diem"] = [round(b, 2) for _, b, _, _ in kq]
    d["so_tu_cx"] = [c for _, _, c, _ in kq]
    d["do_tin"] = [round(e, 2) for _, _, _, e in kq]
    if "nhan_nguoi" not in d.columns:
        d["nhan_nguoi"] = ""

    cot = [args.cot_goc, "nhan_may", "nhan_nguoi", "do_tin", "diem",
           "so_tu_cx", args.cot]
    cot = [c for c in cot if c in d.columns]
    cot += [c for c in d.columns if c not in cot]
    d = d[cot].sort_values("do_tin")

    d.to_csv(out, index=False, encoding="utf-8-sig", mode="x")

    print(f"  {len(d)} dong | nguong {args.nguong} | nguong_hard {args.nguong_hard}\n")
    pb = d["nhan_may"].value_counts()
    for k in ["positive", "negative", "neutral", "unrelated", "hard"]:
        n = int(pb.get(k, 0))
        print(f"  {k:<10}: {n:>5} ({n / len(d) * 100:4.1f}%)")
    print(f"\n  do tin trung binh: {d['do_tin'].mean():.2f}")
    print(f"  -> {out}  (do tin thap len dau)\n")

    if args.chia:
        for i in range(args.chia):
            p = d.iloc[i::args.chia]
            f = targets[i + 1]
            p.to_csv(f, index=False, encoding="utf-8-sig", mode="x")
            print(f"  phan {i+1}: {len(p)} dong -> {f}")
        print()

    for k in ["positive", "negative", "hard", "unrelated", "neutral"]:
        m = d[d.nhan_may == k].sort_values("do_tin", ascending=False)
        if not len(m):
            continue
        print(f"  --- {k} ---")
        for _, r in m.head(3).iterrows():
            print(f"    [{r.diem:>5}] {str(r[args.cot_goc])[:74]}")
        print()


if __name__ == "__main__":
    main()
