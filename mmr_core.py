"""Tính toán MMR (tách câu, TF-IDF, centroid, Sim1, Sim2, MMR, Top-K) — port từ MMR_demo.html.

Thêm 3 trường hợp đặc biệt:
  1. Hòa điểm (tie-breaking): |điểm chênh| < eps → ưu tiên câu đứng đầu bài (pos nhỏ) → Sim1 cao hơn → index nhỏ.
  2. Xung đột thông tin: MMR thuần không phát hiện được. Thêm bước kiểm tra NLI trước khi nạp câu vào S.
     Ở đây nhãn NLI lấy từ preset (giả lập); khi làm thật thay `nli_label` bằng model NLI (vd. XLM-R / mDeBERTa-XNLI).
  3. Thông tin chỉ có ở 1 câu:
     - SAI / lạc đề: đặt ngưỡng liên quan θ, loại câu có Sim1 < θ trước khi chạy MMR.
     - ĐÚNG / quan trọng: dùng Q theo truy vấn (query-focused) thay cho centroid.
"""
import math
import re

STOP_VI = ("có với của và là thì cho gây sau khoảng nhiều khiến được các những một "
           "đã đang sẽ bị trong tại từ này ở theo")

PRESETS = {
    # Đúng số liệu slide 16–17 (Sim1, Sim2 nhập tay)
    "slide": dict(
        K=2, lam=0.5,
        arts=["Mưa lớn khiến nhiều tuyến phố ngập sâu.",
              "Nhiều tuyến đường ngập nặng sau mưa lớn.",
              "Nhiều trường học cho học sinh nghỉ học. Trận mưa kéo dài khoảng 3 giờ."],
        stop=STOP_VI,
        manual=dict(R=[0.80, 0.75, 0.60, 0.40],
                    M=[[1, .90, .20, .10], [.90, 1, .15, .20],
                       [.20, .15, 1, .05], [.10, .20, .05, 1]]),
    ),
    # Tính Sim1, Sim2 từ văn bản bằng TF-IDF
    "mua": dict(
        K=3, lam=0.6,
        arts=["Mưa lớn khiến nhiều tuyến phố Hà Nội ngập sâu. Mưa lớn khiến học sinh Hà Nội nghỉ học.",
              "Nhiều tuyến đường Hà Nội ngập nặng sau mưa lớn. Trận mưa lớn kéo dài 3 giờ.",
              "Hà Nội huy động 500 công nhân xử lý điểm ngập."],
        stop=STOP_VI,
    ),
    # TH1 – hòa điểm ở vòng 2: s2 = s3 = 0.150
    "tie": dict(
        K=2, lam=0.5,
        arts=["Bão số 5 đổ bộ vào Thanh Hóa. Gió giật cấp 12 làm đổ nhiều cây xanh.",
              "Hơn 3.000 hộ dân bị mất điện sau bão.",
              "Bão số 5 gây mưa to diện rộng."],
        stop=STOP_VI,
        manual=dict(R=[0.80, 0.60, 0.50, 0.30],
                    M=[[1, .30, .20, .70], [.30, 1, .10, .15],
                       [.20, .10, 1, .10], [.70, .15, .10, 1]]),
    ),
    # TH2 – hai câu mâu thuẫn (thời gian, địa điểm hội nghị)
    "conflict": dict(
        K=3, lam=0.5,
        arts=["Hội nghị đầu tư diễn ra vào thứ Hai tại Hà Nội. Hội nghị đầu tư thu hút 300 doanh nghiệp.",
              "Hội nghị đầu tư bị hoãn sang thứ Sáu tại TP.HCM.",
              "Hội nghị đầu tư có 300 doanh nghiệp đăng ký."],
        time=["08:00", "15:30", "09:00"],   # giờ đăng của từng báo, dùng khi giải quyết theo độ mới
        stop=STOP_VI,
        # nhãn NLI giả lập giữa các cặp câu (index theo thứ tự sau tách câu)
        nli={(0, 2): "contradiction"},
    ),
    # TH3 – thông tin đơn lẻ: s4 đúng (hotline), s5 rác (quảng cáo)
    "singleton": dict(
        K=2, lam_low=0.3, lam_high=0.8, theta=0.4,
        query="hotline hỗ trợ nạn nhân tai nạn",
        arts=["Tai nạn xe khách trên cao tốc làm 5 người bị thương. Xe khách mất lái lao vào dải phân cách trên cao tốc.",
              "Vụ tai nạn xe khách khiến 5 người bị thương nặng. Hotline hỗ trợ người nhà nạn nhân: 1900 1234.",
              "Đăng ký nhận ưu đãi khuyến mãi tại website."],
        stop=STOP_VI,
    ),
}


# ---------------- tiền xử lý ----------------
def split_sentences(arts):
    out = []
    for ai, a in enumerate(arts):
        pos = 0
        for s in re.split(r"(?<=[.!?])\s+", a.strip()):   # không cắt "TP.HCM", "3.000"
            s = s.strip()
            if re.search(r"\w", s):
                out.append(dict(text=s, art=ai, pos=pos))
                pos += 1
    return out


def tokenize(text, stop):
    return [w for w in re.findall(r"\w+", text.lower()) if w not in stop]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def compute(preset, query=None):
    """query=None → Q là centroid các câu; query='...' → Q là vector TF-IDF của câu truy vấn."""
    stop = set(preset["stop"].lower().split())
    sents = split_sentences(preset["arts"])
    for s in sents:
        s["tok"] = tokenize(s["text"], stop)
    sents = [s for s in sents if s["tok"]]
    n = len(sents)
    V = sorted({w for s in sents for w in s["tok"]})
    df = [sum(w in s["tok"] for s in sents) for w in V]
    idf = [math.log((1 + n) / (1 + d)) + 1 for d in df]            # sklearn smooth_idf

    def vec(tok):
        raw = [tok.count(w) * idf[j] for j, w in enumerate(V)]
        nr = math.sqrt(sum(x * x for x in raw))
        return [x / nr for x in raw] if nr else raw

    tf = [[s["tok"].count(w) for w in V] for s in sents]
    X = [vec(s["tok"]) for s in sents]                               # L2-normalized
    if query:
        C = vec(tokenize(query, stop))                               # query-focused Q
    else:
        C = [sum(r[j] for r in X) / n for j in range(len(V))]        # centroid Q
    nC = math.sqrt(sum(c * c for c in C)) or 1.0
    R = [dot(x, C) / nC for x in X]                                  # Sim1(s_i, Q)
    M = [[dot(a, b) for b in X] for a in X]                          # Sim2(s_i, s_j)
    manual = "manual" in preset and len(preset["manual"]["R"]) == n and not query
    if manual:
        R = list(preset["manual"]["R"])
        M = [list(r) for r in preset["manual"]["M"]]
    return dict(sents=sents, n=n, V=V, df=df, idf=idf, tf=tf, X=X, C=C, nC=nC,
                R=R, M=M, manual=manual, query=query)


# ---------------- TH1: phá thế hòa ----------------
def tie_key(D, c):
    """Trong nhóm hòa điểm: câu đứng đầu bài (pos nhỏ) → Sim1 cao → index nhỏ."""
    return (D["sents"][c["i"]]["pos"], -c["R"], c["i"])


def pick(D, cand, eps=1e-6):
    best = max(c["score"] for c in cand)
    tied = [c for c in cand if best - c["score"] < eps]       # coi là hòa nếu chênh < eps
    win = min(tied, key=lambda c: tie_key(D, c))
    rule = None
    if len(tied) > 1:
        poss = {D["sents"][c["i"]]["pos"] for c in tied}
        if len(poss) > 1:
            rule = "pos"        # thắng nhờ đứng đầu bài
        elif len({round(c["R"], 9) for c in tied}) > 1:
            rule = "sim1"       # cùng vị trí → Sim1 cao hơn
        else:
            rule = "index"      # vẫn hòa → câu xuất hiện trước
    return win["i"], [c["i"] for c in tied], rule


# ---------------- TH2: xung đột ----------------
def nli_label(preset, i, j):
    """Giả lập model NLI. Thay bằng model thật: trả về 'entailment' / 'neutral' / 'contradiction'."""
    nli = preset.get("nli", {})
    return nli.get((i, j)) or nli.get((j, i)) or "neutral"


def find_conflicts(preset, S):
    return [(a, b) for k, a in enumerate(S) for b in S[k + 1:] if nli_label(preset, a, b) == "contradiction"]


# ---------------- MMR ----------------
def mmr(D, lam, K, theta=None, preset=None, conflict=None):
    """
    theta    : ngưỡng Sim1 — câu có Sim1 < theta bị loại trước khi chọn (TH3 câu sai/lạc đề).
    conflict : None   → MMR thuần (không kiểm tra mâu thuẫn)
               'skip' → bỏ ứng viên mâu thuẫn với câu đã có trong S, xét câu kế tiếp
               'newer'→ giữ câu từ báo đăng muộn hơn (thay câu cũ trong S nếu cần)
    Trả về S và chi tiết từng vòng.
    """
    R, M, n = D["R"], D["M"], D["n"]
    pool = [i for i in range(n) if theta is None or R[i] >= theta]
    dropped = [i for i in range(n) if i not in pool]
    S, rounds, banned = [], [], set()
    while len(S) < K and pool:
        cand = []
        for i in pool:
            if i in banned:
                continue
            pen, arg = (max((M[i][j], j) for j in S) if S else (0.0, -1))
            cand.append(dict(i=i, R=R[i], D=pen, arg=arg, score=lam * R[i] - (1 - lam) * pen))
        if not cand:
            break
        win, tied, rule = pick(D, cand)
        rd = dict(S=list(S), cand=cand, win=win, tied=tied, rule=rule, conflict=None)
        if conflict and preset is not None:
            clash = [j for j in S if nli_label(preset, win, j) == "contradiction"]
            if clash:
                j = clash[0]
                rd["conflict"] = j
                if conflict == "skip":
                    rd["action"] = "skip"
                    banned.add(win)
                    rounds.append(rd)
                    continue
                if conflict == "newer":
                    t = preset["time"]
                    new_is_win = t[D["sents"][win]["art"]] > t[D["sents"][j]["art"]]
                    rd["action"] = "replace" if new_is_win else "skip"
                    if new_is_win:
                        S[S.index(j)] = win
                        pool.remove(win)
                        banned.add(j)
                    else:
                        banned.add(win)
                    rounds.append(rd)
                    continue
        rounds.append(rd)
        S.append(win)
        pool.remove(win)
    return S, rounds, dropped


def topk(D, K):
    return sorted(range(D["n"]), key=lambda i: (-D["R"][i], i))[:K]


def avg_redundancy(D, S):
    pairs = [(a, b) for k, a in enumerate(S) for b in S[k + 1:]]
    return sum(D["M"][a][b] for a, b in pairs) / len(pairs) if pairs else 0.0


# ---------------- in kết quả ----------------
def show(title, D, S, rounds, dropped=()):
    print(f"\n== {title}")
    print("  Sim1 =", {f"s{i+1}": round(r, 3) for i, r in enumerate(D["R"])})
    if dropped:
        print("  loại do Sim1 < θ:", [f"s{i+1}" for i in dropped])
    for r, rd in enumerate(rounds):
        msg = f"  vòng {r+1}: " + str({f"s{c['i']+1}": round(c["score"], 3) for c in rd["cand"]}) + f" -> s{rd['win']+1}"
        if rd["rule"]:
            msg += f"  [hòa {['s%d' % (i+1) for i in rd['tied']]}, phá hòa theo {rd['rule']}]"
        if rd["conflict"] is not None:
            msg += f"  [mâu thuẫn với s{rd['conflict']+1} → {rd['action']}]"
        print(msg)
    print("  S =", [f"s{i+1}" for i in S])


if __name__ == "__main__":
    for name in ("slide", "mua"):
        p = PRESETS[name]
        D = compute(p)
        S, rd, _ = mmr(D, p["lam"], p["K"])
        show(name, D, S, rd)
        print("  Top-K:", [f"s{i+1}" for i in topk(D, p["K"])])

    p = PRESETS["tie"]; D = compute(p)
    show("TH1 hòa điểm", D, *mmr(D, p["lam"], p["K"])[:2])

    p = PRESETS["conflict"]; D = compute(p)
    for s in D["sents"]:
        print("  ", s["text"])
    S, rd, _ = mmr(D, p["lam"], p["K"])
    show("TH2 MMR thuần", D, S, rd)
    print("  cặp mâu thuẫn trong S:", [(f"s{a+1}", f"s{b+1}") for a, b in find_conflicts(p, S)])
    show("TH2 + NLI (giữ tin mới hơn)", D, *mmr(D, p["lam"], p["K"], preset=p, conflict="newer")[:2])

    p = PRESETS["singleton"]; D = compute(p)
    for i, s in enumerate(D["sents"]):
        print(f"   s{i+1}", s["text"])
    lo, hi, K, th = p["lam_low"], p["lam_high"], p["K"], p["theta"]
    show(f"TH3a câu rác s5 – centroid, λ={lo}", D, *mmr(D, lo, K)[:2])
    show(f"TH3a + ngưỡng θ={th}", D, *mmr(D, lo, K, theta=th))
    show(f"TH3b câu đúng s4 (hotline) – centroid, λ={hi}", D, *mmr(D, hi, K)[:2])
    Dq = compute(p, query=p["query"])
    show(f"TH3b query-focused Q='{p['query']}', λ={hi}", Dq, *mmr(Dq, hi, K)[:2])
