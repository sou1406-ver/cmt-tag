"""Minh họa MMR bằng Manim.

Chạy:
    manim -pqh mmr_manim.py MMRDemo                     # ví dụ slide 16–17 + 3 trường hợp đặc biệt
    MMR_PRESET=mua manim -pqh mmr_manim.py MMRDemo      # ví dụ tính TF-IDF từ văn bản
    manim -pqh mmr_manim.py MMRCases                    # chỉ 3 trường hợp đặc biệt
    manim -pqh mmr_manim.py CaseTie                     # từng trường hợp: CaseTie / CaseConflict / CaseSingleton
    MMR_CASES=0 manim ... MMRDemo                       # bỏ phần trường hợp đặc biệt khỏi MMRDemo
"""
import os

from manim import *

from mmr_core import PRESETS, compute, mmr, topk, avg_redundancy, find_conflicts

PRESET = os.environ.get("MMR_PRESET", "slide")
P = PRESETS[PRESET]
D = compute(P)
LAM, K = P["lam"], P["K"]

# Bảng màu giống bản HTML
BG = "#0d131e"
PANEL = "#151f2e"
LINE = "#283850"
FG = "#e7eef7"
MUTED = "#8c9db5"
REL = "#6fa8ec"
PICK = "#5fd3a6"
GOLD = "#e8c26a"
PEN = "#ec7f7f"
FONT = "DejaVu Sans"
SUB = "₀₁₂₃₄₅₆₇₈₉"
LET = "ABCDEFGHIJ"

config.background_color = BG


def T(s, size=26, color=FG, weight=NORMAL):
    return Text(s, font=FONT, font_size=size, color=color, weight=weight)


def SL(i):
    return "s" + "".join(SUB[int(d)] for d in str(i + 1))


def f(x, d=3):
    return f"{0 if abs(x) < 5e-5 else x:.{d}f}"


def fit(m, w):
    if m.width > w:
        m.scale_to_fit_width(w)
    return m


def box(m, color=LINE, buff=0.18, fill=PANEL):
    r = SurroundingRectangle(m, buff=buff, corner_radius=0.08, color=color, stroke_width=1.5)
    r.set_fill(fill, 1)
    return VGroup(r, m)


def heat(v, color, maxv=1.0):
    return interpolate_color(ManimColor(PANEL), ManimColor(color), 0.15 + 0.75 * min(1, max(0, v) / maxv))


class MMRDemo(Scene):
    def construct(self):
        self.main()
        if os.environ.get("MMR_CASES", "1") != "0":
            self.case_tie()
            self.case_conflict()
            self.case_singleton()

    def main(self):
        self.title()
        self.split()
        if not D["manual"]:
            self.tfidf()
        self.relevance()
        self.top_k()
        self.redundancy()
        self.mmr_rounds()
        self.lambda_effect()
        self.compare()

    # ---------- tiện ích ----------
    def header(self, title, sub=None):
        g = VGroup(T(title, 38, weight=BOLD))
        if sub:
            g.add(T(sub, 22, MUTED))
        g.arrange(DOWN, buff=0.12).to_edge(UP, buff=0.35)
        return g

    def clear(self):
        if self.mobjects:
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.6)

    def bars(self, order, values, width=6.0, colors=None, maxv=None):
        maxv = maxv or max(values)
        rows = VGroup()
        for k, i in enumerate(order):
            lab = T(SL(i), 26, PICK, BOLD)
            trk = Rectangle(width=width, height=0.32, stroke_width=0).set_fill("#223047", 1)
            seg = Rectangle(width=max(1e-3, values[i] / maxv * width), height=0.32, stroke_width=0)
            seg.set_fill(colors[i] if colors else REL, 1)
            val = T(f(values[i]), 22, MUTED)
            row = VGroup(lab, trk, val).arrange(RIGHT, buff=0.3)
            seg.align_to(trk, LEFT).move_to(trk, coor_mask=[0, 1, 0])
            row.add(seg)
            row.i = i
            rows.add(row)
        rows.arrange(DOWN, buff=0.3, aligned_edge=LEFT)
        return rows

    # ---------- 1. tiêu đề ----------
    def title(self):
        t = T("Minh họa MMR", 64, weight=BOLD)
        s = T("Maximal Marginal Relevance · Tóm tắt đa văn bản", 28, MUTED)
        n = T("Nhóm 16", 26, GOLD)
        g = VGroup(t, s, n).arrange(DOWN, buff=0.3)
        self.play(Write(t), run_time=1.2)
        self.play(FadeIn(s, shift=UP * 0.2), FadeIn(n, shift=UP * 0.2))
        self.wait(1.2)
        self.clear()

    # ---------- 2. tách câu ----------
    def split(self):
        h = self.header("Tách câu", f"{len(P['arts'])} bản tin cùng một sự kiện → {D['n']} câu ứng viên (tập R)")
        self.play(FadeIn(h))
        arts = VGroup()
        for ai, a in enumerate(P["arts"]):
            lines = VGroup(*[T(x.strip() + ".", 20) for x in a.split(".") if x.strip()]).arrange(DOWN, buff=0.1)
            body = VGroup(T(f"BÁO {LET[ai]}", 20, REL, BOLD), lines).arrange(DOWN, buff=0.15)
            fit(body, 4.0)
            arts.add(box(body))
        arts.arrange(RIGHT, buff=0.3).next_to(h, DOWN, buff=0.45)
        fit(arts, 13)
        self.play(LaggedStart(*[FadeIn(a, shift=DOWN * 0.2) for a in arts], lag_ratio=0.25))

        rows = VGroup()
        for i, s in enumerate(D["sents"]):
            r = VGroup(T(SL(i), 24, PICK, BOLD), T(s["text"], 22), T(f"BÁO {LET[s['art']]}", 16, MUTED))
            r.arrange(RIGHT, buff=0.35)
            rows.add(r)
        rows.arrange(DOWN, buff=0.22, aligned_edge=LEFT).next_to(arts, DOWN, buff=0.55)
        fit(rows, 12.5)
        for i, r in enumerate(rows):
            src = arts[D["sents"][i]["art"]]
            self.play(TransformFromCopy(src[1][1][D["sents"][i]["pos"]], r[1]), FadeIn(r[0]), FadeIn(r[2]), run_time=0.7)
        if D["manual"]:
            note = T("Ví dụ slide 16: Sim₁ và Sim₂ lấy đúng số trên slide", 20, GOLD).to_edge(DOWN, buff=0.4)
            self.play(FadeIn(note))
        self.wait(1.5)
        self.clear()

    # ---------- 3. TF-IDF + centroid (chỉ khi tính từ văn bản) ----------
    def tfidf(self):
        h = self.header("Biểu diễn câu bằng TF-IDF")
        fx = MathTex(r"\mathrm{idf}(w)=\ln\frac{1+n}{1+\mathrm{df}(w)}+1", r"\qquad",
                     r"v_{i,w}=\frac{\mathrm{tf}_{i,w}\cdot\mathrm{idf}(w)}{\|v_i\|}", color=GOLD).scale(0.8)
        fx.next_to(h, DOWN, buff=0.3)
        self.play(FadeIn(h), Write(fx))
        V, X, C = D["V"], D["X"], D["C"]
        cw, ch = min(0.62, 11.5 / len(V)), 0.42
        grid = VGroup()
        heads = VGroup(*[T(w, 15, GOLD).rotate(PI / 4) for w in V])
        for j, hd in enumerate(heads):
            hd.move_to([j * cw, 0.55, 0])
        grid.add(heads)
        rows = VGroup()
        for i, r in enumerate(X + [C]):
            row = VGroup()
            for j, v in enumerate(r):
                col = PICK if i < len(X) else GOLD
                sq = Rectangle(width=cw * 0.94, height=ch * 0.9, stroke_color=LINE, stroke_width=1)
                sq.set_fill(heat(v, col, 0.7) if v > 1e-9 else PANEL, 1).move_to([j * cw, -(i + (i == len(X)) * 0.3) * ch - 0.1, 0])
                txt = T(f(v, 2) if v > 1e-9 else "0", 11, FG if v > 1e-9 else MUTED).move_to(sq)
                row.add(VGroup(sq, txt))
            lab = T("Q" if i == len(X) else SL(i), 20, GOLD if i == len(X) else PICK, BOLD).next_to(row, LEFT, buff=0.2)
            rows.add(VGroup(lab, row))
        grid.add(rows)
        grid.next_to(fx, DOWN, buff=0.35)
        fit(grid, 13)
        self.play(FadeIn(heads))
        for r in rows[:-1]:
            self.play(FadeIn(r[0]), LaggedStart(*[GrowFromCenter(c) for c in r[1]], lag_ratio=0.03), run_time=0.8)
        cfx = MathTex(r"Q=\frac{1}{n}\sum_{i=1}^{n} v_i", color=PICK).scale(0.8).to_corner(DR, buff=0.4)
        self.play(Write(cfx), FadeIn(rows[-1], shift=DOWN * 0.2))
        self.wait(1.5)
        self.clear()

    # ---------- 4. Sim1 ----------
    def relevance(self):
        h = self.header("Độ liên quan với chủ đề chung", "Câu nào gần vector trung tâm Q nhất?")
        fx = MathTex(r"\mathrm{Sim}_1(s_i,Q)=\cos(v_i,Q)=\frac{v_i\cdot Q}{\|v_i\|\,\|Q\|}", color=GOLD).scale(0.85)
        fx.next_to(h, DOWN, buff=0.3)
        self.play(FadeIn(h), Write(fx))
        best = max(range(D["n"]), key=lambda i: D["R"][i])
        bars = self.bars(range(D["n"]), D["R"]).next_to(fx, DOWN, buff=0.5)
        for r in bars:
            self.play(FadeIn(VGroup(r[0], r[1], r[2])), GrowFromEdge(r[3], LEFT), run_time=0.6)
        self.play(bars[best][3].animate.set_fill(PICK), Indicate(bars[best][0], color=PICK))
        cap = T(f"{SL(best)} gần chủ đề chung nhất", 24, PICK, BOLD).next_to(bars, DOWN, buff=0.45)
        self.play(FadeIn(cap))
        self.wait(1.2)
        self.clear()

    # ---------- 5. Top-K ----------
    def top_k(self):
        Tk = topk(D, K)
        h = self.header("Chọn Top-K", f"Sắp xếp theo Sim₁ giảm dần, chọn K = {K}")
        self.play(FadeIn(h))
        bars = self.bars(range(D["n"]), D["R"]).next_to(h, DOWN, buff=0.6)
        self.play(FadeIn(bars))
        order = sorted(range(D["n"]), key=lambda i: (-D["R"][i], i))
        target = self.bars(order, D["R"]).move_to(bars, aligned_edge=UP)
        self.play(*[bars[i].animate.move_to(next(t for t in target if t.i == i)) for i in range(D["n"])], run_time=1)
        rects = VGroup(*[SurroundingRectangle(bars[i], color=GOLD, buff=0.08, corner_radius=0.06) for i in Tk])
        self.play(Create(rects), *[bars[i][3].animate.set_fill(PICK) for i in Tk])
        cap = T("Top-K = {" + ", ".join(SL(i) for i in Tk) + "}", 26, GOLD, BOLD)
        note = T("Mỗi câu chấm điểm độc lập, không quan tâm câu đã chọn nói gì (MMR với λ = 1)", 20, MUTED)
        g = VGroup(cap, note).arrange(DOWN, buff=0.2).next_to(bars, DOWN, buff=0.5)
        fit(note, 12.5)
        self.play(FadeIn(g))
        if len(Tk) >= 2:
            a, b = Tk[0], Tk[1]
            warn = T(f"Nhưng Sim₂({SL(a)}, {SL(b)}) = {f(D['M'][a][b])} → hai câu gần như nói cùng một ý", 22, PEN)
            fit(warn, 12.5).next_to(g, DOWN, buff=0.3)
            self.play(FadeIn(warn))
        self.wait(1.5)
        self.clear()

    # ---------- 6. Sim2 ----------
    def redundancy(self):
        n, M = D["n"], D["M"]
        h = self.header("Độ trùng lặp giữa các câu", "Cosine giữa từng cặp câu (Sim₂), dùng làm điểm phạt trong MMR")
        fx = MathTex(r"\mathrm{Sim}_2(s_i,s_j)=\cos(v_i,v_j)=\frac{v_i\cdot v_j}{\|v_i\|\,\|v_j\|}", color=GOLD).scale(0.85)
        fx.next_to(h, DOWN, buff=0.3)
        self.play(FadeIn(h), Write(fx))
        cs = min(1.0, 4.6 / n)
        cells = {}
        grid = VGroup()
        for i in range(n):
            for j in range(n):
                sq = Square(cs * 0.94, stroke_color=LINE, stroke_width=1)
                sq.set_fill("#2a3446" if i == j else heat(M[i][j], GOLD), 1).move_to([j * cs, -i * cs, 0])
                txt = T(f(M[i][j], 2), max(12, int(20 * cs)), FG).move_to(sq)
                cells[i, j] = VGroup(sq, txt)
                grid.add(cells[i, j])
        labs = VGroup(*[T(SL(i), 22, REL, BOLD).move_to([-cs * 0.85, -i * cs, 0]) for i in range(n)],
                      *[T(SL(j), 22, REL, BOLD).move_to([j * cs, cs * 0.8, 0]) for j in range(n)])
        mat = VGroup(labs, grid).next_to(fx, DOWN, buff=0.45)
        self.play(FadeIn(labs))
        self.play(LaggedStart(*[FadeIn(cells[i, j], scale=0.6) for i in range(n) for j in range(n)], lag_ratio=0.03))
        # cặp trùng nhiều nhất
        a, b = max(((i, j) for i in range(n) for j in range(i + 1, n)), key=lambda p: M[p[0]][p[1]])
        hl = VGroup(SurroundingRectangle(cells[a, b], color=GOLD, buff=0.02),
                    SurroundingRectangle(cells[b, a], color=GOLD, buff=0.02))
        txt = VGroup(T(SL(a) + ": " + D["sents"][a]["text"], 18), T(SL(b) + ": " + D["sents"][b]["text"], 18),
                     T(f"Sim₂ = {f(M[a][b])} → trùng ý", 22, GOLD, BOLD)).arrange(DOWN, buff=0.15, aligned_edge=LEFT)
        fit(txt, 6).next_to(mat, RIGHT, buff=0.6)
        self.play(Create(hl), FadeIn(txt))
        self.wait(1.5)
        self.clear()

    # ---------- 7. Các vòng MMR ----------
    def mmr_formula(self, lam=None):
        l1 = r"\lambda" if lam is None else f"{lam:.2f}"
        l2 = r"(1-\lambda)" if lam is None else f"{1 - lam:.2f}"
        return MathTex(r"\mathrm{MMR}=\arg\max_{s_i\in R\setminus S}\Big[", l1 + r"\cdot\mathrm{Sim}_1(s_i,Q)",
                       "-", l2 + r"\cdot\max_{s_j\in S}\mathrm{Sim}_2(s_i,s_j)", r"\Big]").scale(0.78) \
            .set_color_by_tex(r"Sim}_1", REL).set_color_by_tex(r"Sim}_2", PEN)

    def mmr_rounds(self):
        S_final, rounds, _ = mmr(D, LAM, K)
        h = self.header("Chọn câu bằng MMR", f"Ưu tiên câu liên quan, hạn chế lặp lại thông tin · λ = {LAM}, K = {K}")
        fx = self.mmr_formula().next_to(h, DOWN, buff=0.25)
        self.play(FadeIn(h), Write(fx))
        self.wait(0.8)
        self.play(Transform(fx, self.mmr_formula(LAM).move_to(fx)))

        width = 4.6
        maxv = LAM * max(D["R"])
        chip = None
        for r, rd in enumerate(rounds):
            # thanh điểm: xanh = điểm MMR, đỏ = phần bị phạt
            rows = VGroup()
            for i in range(D["n"]):
                lab = T(SL(i), 24, PICK, BOLD)
                trk = Rectangle(width=width, height=0.3, stroke_width=0).set_fill("#223047", 1)
                c = next((x for x in rd["cand"] if x["i"] == i), None)
                row = VGroup(lab, trk)
                if c is None:
                    val = T("đã chọn", 18, MUTED)
                    row.add(val).arrange(RIGHT, buff=0.3)
                    row.set_opacity(0.4)
                    row.segs = VGroup()
                else:
                    pos = max(0.0, c["score"])
                    pen = LAM * c["R"] - pos
                    val = T(f(c["score"]), 20, MUTED)
                    row.add(val).arrange(RIGHT, buff=0.3)
                    s1 = Rectangle(width=max(1e-3, pos / maxv * width), height=0.3, stroke_width=0).set_fill(REL, 1)
                    s2 = Rectangle(width=max(1e-3, pen / maxv * width), height=0.3, stroke_width=0).set_fill(PEN, 1)
                    s1.align_to(trk, LEFT).move_to(trk, coor_mask=[0, 1, 0])
                    s2.next_to(s1, RIGHT, buff=0)
                    if pen < 1e-6:
                        s2.set_opacity(0)
                    row.segs = VGroup(s1, s2)
                    row.add(row.segs)
                row.i = i
                rows.add(row)
            rows.arrange(DOWN, buff=0.28, aligned_edge=LEFT).next_to(fx, DOWN, buff=0.55).to_edge(LEFT, buff=0.8)

            Sset = "S = {" + (", ".join(SL(j) for j in rd["S"]) if rd["S"] else "∅") + "}"
            rt = T(f"Vòng {r + 1}", 26, GOLD, BOLD)
            st = T(Sset, 22, PICK)
            calc = VGroup()
            for c in rd["cand"]:
                line = T(f"{SL(c['i'])}:  {LAM:.2f}×{f(c['R'])} − {1 - LAM:.2f}×{f(c['D'])} = {f(c['score'])}", 19)
                calc.add(line)
            calc.arrange(DOWN, buff=0.18, aligned_edge=LEFT)
            note = T("S rỗng → phần phạt = 0" if not rd["S"] else "Phạt = max Sim₂ với các câu trong S", 17, MUTED)
            panel = VGroup(rt, st, note, calc).arrange(DOWN, buff=0.25, aligned_edge=LEFT)
            fit(panel, 6).next_to(rows, RIGHT, buff=0.7).align_to(rows, UP)

            legend = VGroup(Square(0.18, stroke_width=0).set_fill(REL, 1), T("điểm MMR", 16, MUTED),
                            Square(0.18, stroke_width=0).set_fill(PEN, 1), T("phần bị phạt", 16, MUTED)) \
                .arrange(RIGHT, buff=0.15).next_to(rows, DOWN, buff=0.3).align_to(rows, LEFT)

            self.play(FadeIn(rt), FadeIn(st), FadeIn(note),
                      *[FadeIn(VGroup(*[m for m in row if m is not getattr(row, "segs", None)])) for row in rows],
                      FadeIn(legend))
            for row, line in zip([rw for rw in rows if len(rw.segs)], calc):
                self.play(GrowFromEdge(row.segs[0], LEFT), FadeIn(line, shift=LEFT * 0.2), run_time=0.55)
                if row.segs[1].get_fill_opacity() > 0:
                    self.play(GrowFromEdge(row.segs[1], LEFT), run_time=0.35)
            wrow = next(rw for rw in rows if rw.i == rd["win"])
            wline = calc[[c["i"] for c in rd["cand"]].index(rd["win"])]
            self.play(Create(SurroundingRectangle(wrow, color=PICK, buff=0.08, corner_radius=0.06)),
                      wline.animate.set_color(PICK), wrow.segs[0].animate.set_fill(PICK))
            newS = rd["S"] + [rd["win"]]
            new_chip = box(T("S = {" + ", ".join(SL(j) for j in newS) + "}", 26, PICK, BOLD), color=PICK, fill="#173a33")
            new_chip.to_edge(DOWN, buff=0.35)
            cap = T(f"chọn {SL(rd['win'])}", 22, PICK).next_to(new_chip, RIGHT, buff=0.3)
            if chip is None:
                self.play(FadeIn(new_chip, shift=UP * 0.2), FadeIn(cap))
            else:
                self.play(Transform(chip[0], new_chip), FadeIn(cap))
            chip = VGroup(chip[0] if chip else new_chip, cap)
            self.wait(1.2)
            keep = [h, fx, chip[0]]
            self.play(FadeOut(Group(*[m for m in self.mobjects if m not in keep])), run_time=0.5)
            chip = VGroup(chip[0])
        stop = T(f"Dừng: đủ K = {K} câu", 24, GOLD, BOLD).next_to(chip, UP, buff=0.4)
        self.play(FadeIn(stop))
        self.wait(1.2)
        self.clear()

    # ---------- 8. ảnh hưởng của λ ----------
    def lambda_effect(self):
        first = max(range(D["n"]), key=lambda i: D["R"][i])
        cands = [i for i in range(D["n"]) if i != first]
        sc = lambda i, l: l * D["R"][i] - (1 - l) * D["M"][i][first]
        h = self.header("Điều chỉnh λ", f"Sau khi chọn {SL(first)} ở vòng 1, điểm vòng 2 của các câu còn lại theo λ")
        self.play(FadeIn(h))
        lo = min(min(sc(i, 0), sc(i, 1)) for i in cands)
        hi = max(max(sc(i, 0), sc(i, 1)) for i in cands)
        step = 0.2 if hi - lo > 0.6 else 0.1
        lo, hi = np.floor(lo / step) * step, np.ceil(hi / step) * step
        ax = Axes(x_range=[0, 1, 0.25], y_range=[lo, hi, step], x_length=7.2, y_length=4.4,
                  axis_config=dict(color=MUTED, include_numbers=True, font_size=24,
                                   decimal_number_config=dict(num_decimal_places=2)),
                  tips=False).to_edge(LEFT, buff=0.9).shift(DOWN * 0.5)
        xl = MathTex(r"\lambda", color=MUTED).scale(0.9).next_to(ax, DOWN, buff=0.15)
        band = Rectangle(width=ax.c2p(0.7, 0)[0] - ax.c2p(0.5, 0)[0], height=ax.y_length, stroke_width=0) \
            .set_fill(GOLD, 0.08).move_to([(ax.c2p(0.5, 0)[0] + ax.c2p(0.7, 0)[0]) / 2, ax.get_center()[1], 0])
        self.play(Create(ax), FadeIn(xl), FadeIn(band))
        COLS = [REL, GOLD, PEN, "#b59cf0", "#7fd0e8", "#f0a96b", "#9bd27a", "#e88fc4"]
        lines = VGroup()
        for k, i in enumerate(cands):
            c = COLS[k % len(COLS)]
            ln = Line(ax.c2p(0, sc(i, 0)), ax.c2p(1, sc(i, 1)), color=c, stroke_width=4)
            lb = T(SL(i), 22, c, BOLD).next_to(ln.get_end(), RIGHT, buff=0.12)
            lines.add(VGroup(ln, lb))
        self.play(LaggedStart(*[Create(l) for l in lines], lag_ratio=0.3))

        lt = ValueTracker(0.0)
        vline = always_redraw(lambda: DashedLine(ax.c2p(lt.get_value(), lo), ax.c2p(lt.get_value(), hi), color=GOLD))
        dots = VGroup(*[always_redraw(lambda i=i, c=COLS[k % len(COLS)]: Dot(ax.c2p(lt.get_value(), sc(i, lt.get_value())), color=c, radius=0.07))
                        for k, i in enumerate(cands)])

        def info():
            l = lt.get_value()
            w = max(cands, key=lambda i: sc(i, l))
            dup = D["M"][w][first] > 0.4
            g = VGroup(T(f"λ = {l:.2f}", 30, GOLD, BOLD),
                       T(f"vòng 2 chọn {SL(w)}", 26, PEN if dup else PICK, BOLD),
                       T(f"trùng ý với {SL(first)}" if dup else "thêm thông tin mới", 22, PEN if dup else PICK))
            if l > 0.995:
                g.add(T("λ = 1: giống Top-K", 20, MUTED))
            elif l < 0.005:
                g.add(T("λ = 0: chỉ xét độ khác biệt", 20, MUTED))
            return g.arrange(DOWN, buff=0.2, aligned_edge=LEFT).next_to(ax, RIGHT, buff=1.0).shift(UP * 0.5)

        panel = always_redraw(info)
        self.play(Create(vline), FadeIn(dots), FadeIn(panel))
        self.play(lt.animate.set_value(1.0), run_time=4, rate_func=linear)
        self.wait(0.5)
        self.play(lt.animate.set_value(LAM), run_time=1.5)
        note = T("Vùng tô nhạt λ ∈ [0.5; 0.7] thường dùng cho tin tức", 18, MUTED).next_to(xl, DOWN, buff=0.25)
        self.play(FadeIn(note))
        self.wait(1.5)
        self.clear()

    # ---------- 9. so sánh ----------
    def compare(self):
        Tk, S = topk(D, K), mmr(D, LAM, K)[0]
        h = self.header("So sánh Top-K và MMR", f"Cùng chọn {K} câu")
        self.play(FadeIn(h))

        def col(name, sub, color, L):
            items = VGroup(*[VGroup(T(SL(i), 20, color, BOLD), T(D["sents"][i]["text"], 18)).arrange(RIGHT, buff=0.2)
                             for i in L]).arrange(DOWN, buff=0.18, aligned_edge=LEFT)
            cov = len({w for i in L for w in D["sents"][i]["tok"]})
            stats = VGroup(
                T(f"Sim₁ trung bình: {f(sum(D['R'][i] for i in L) / len(L))}", 18, MUTED),
                T(f"Sim₂ trung bình giữa các câu chọn: {f(avg_redundancy(D, L))}", 18, MUTED),
                T(f"Từ khóa bao phủ: {cov} / {len(D['V'])}", 18, MUTED),
            ).arrange(DOWN, buff=0.1, aligned_edge=LEFT)
            g = VGroup(T(name, 30, color, BOLD), T(sub, 18, MUTED), items, stats).arrange(DOWN, buff=0.25)
            fit(g, 5.8)
            return box(g, color=LINE, buff=0.3)

        a = col("Top-K", "Chỉ xét Sim₁ (λ = 1)", REL, Tk)
        b = col(f"MMR (λ = {LAM})", "Có phạt thông tin trùng lặp", PICK, S)
        g = VGroup(a, b).arrange(RIGHT, buff=0.5, aligned_edge=UP).next_to(h, DOWN, buff=0.5)
        self.play(FadeIn(a, shift=UP * 0.2))
        self.play(FadeIn(b, shift=UP * 0.2))
        cap = T("MMR giữ độ liên quan cao mà giảm trùng lặp → bản tóm tắt nhiều thông tin hơn", 22, GOLD, BOLD)
        fit(cap, 13).next_to(g, DOWN, buff=0.45)
        self.play(FadeIn(cap))
        self.wait(2.5)
        self.clear()

    # =====================================================================
    #                     CÁC TRƯỜNG HỢP ĐẶC BIỆT
    # =====================================================================
    def sent_rows(self, Dx, tags=None, size=20, width=12.5):
        """Danh sách câu: nhãn sᵢ · nội dung · BÁO X (vị trí) · tag tùy chọn."""
        rows = VGroup()
        for i, s in enumerate(Dx["sents"]):
            r = VGroup(T(SL(i), size + 2, PICK, BOLD), T(s["text"], size),
                       T(f"BÁO {LET[s['art']]} · câu {s['pos'] + 1}", size - 5, MUTED))
            if tags and i in tags:
                r.add(T(tags[i][0], size - 4, tags[i][1], BOLD))
            r.arrange(RIGHT, buff=0.3)
            rows.add(r)
        rows.arrange(DOWN, buff=0.18, aligned_edge=LEFT)
        return fit(rows, width)

    def chip(self, S, color=PICK, label="S"):
        txt = label + " = {" + (", ".join(SL(j) for j in S) if S else "∅") + "}"
        return box(T(txt, 24, color, BOLD), color=color, fill="#173a33" if color == PICK else "#3a1b1f")

    def case_title(self, k, name, sub):
        t = VGroup(T(f"Trường hợp {k}", 28, GOLD, BOLD), T(name, 44, weight=BOLD), T(sub, 22, MUTED))
        t.arrange(DOWN, buff=0.25)
        self.play(FadeIn(t, shift=UP * 0.2))
        self.wait(1.2)
        self.play(FadeOut(t))

    # ---------- TH1: bằng điểm ----------
    def case_tie(self):
        p = PRESETS["tie"]
        Dx = compute(p)
        lam, Kx = p["lam"], p["K"]
        S, rounds, _ = mmr(Dx, lam, Kx)
        rd = next(r for r in rounds if r["rule"])
        self.case_title(1, "Hai câu bằng điểm MMR", "Chọn câu nào?")

        h = self.header("TH1 · Hai câu bằng điểm", f"λ = {lam}, K = {Kx} · Sim₁, Sim₂ nhập tay")
        rows = self.sent_rows(Dx).next_to(h, DOWN, buff=0.4)
        self.play(FadeIn(h), LaggedStart(*[FadeIn(r) for r in rows], lag_ratio=0.15))

        Sbox = self.chip(rd["S"]).to_corner(UR, buff=0.4).shift(DOWN * 0.9)
        rt = T(f"Vòng {rounds.index(rd) + 1}", 24, GOLD, BOLD)
        calc = VGroup(*[T(f"{SL(c['i'])}:  {lam:.2f}×{f(c['R'])} − {1 - lam:.2f}×{f(c['D'])} = {f(c['score'])}", 22)
                        for c in rd["cand"]]).arrange(DOWN, buff=0.15, aligned_edge=LEFT)
        blk = VGroup(rt, calc).arrange(DOWN, buff=0.2, aligned_edge=LEFT).next_to(rows, DOWN, buff=0.5).to_edge(LEFT, buff=1.0)
        self.play(FadeIn(Sbox), FadeIn(rt))
        self.play(LaggedStart(*[FadeIn(c, shift=LEFT * 0.2) for c in calc], lag_ratio=0.3))
        idx = [c["i"] for c in rd["cand"]]
        tl = VGroup(*[calc[idx.index(i)] for i in rd["tied"]])
        self.play(*[l.animate.set_color(GOLD) for l in tl])
        eq = T(" = ".join(f(rd["cand"][idx.index(i)]["score"]) for i in rd["tied"]) + "  → bằng điểm", 24, GOLD, BOLD)
        eq.next_to(blk, RIGHT, buff=0.8).align_to(blk, UP)
        note = T("Số thực: coi là bằng điểm khi |chênh lệch| < ε = 10⁻⁶", 17, MUTED).next_to(eq, DOWN, buff=0.15, aligned_edge=LEFT)
        self.play(FadeIn(eq), FadeIn(note))
        self.wait(0.8)

        rules = VGroup(
            T("Quy tắc phá bằng điểm (theo thứ tự):", 20, FG, BOLD),
            T("1. Câu đứng đầu bài hơn (lead sentence)", 19),
            T("2. Sim₁ cao hơn (bám chủ đề hơn)", 19),
            T("3. Vẫn bằng điểm → câu xuất hiện trước (như argmax)", 19),
        ).arrange(DOWN, buff=0.12, aligned_edge=LEFT).next_to(note, DOWN, buff=0.35, aligned_edge=LEFT)
        self.play(FadeIn(rules))
        k = {"pos": 1, "sim1": 2, "index": 3}[rd["rule"]]
        self.play(rules[k].animate.set_color(PICK), Indicate(rules[k], color=PICK, scale_factor=1.05))
        why = VGroup(*[T(f"{SL(i)}: câu {Dx['sents'][i]['pos'] + 1} của BÁO {LET[Dx['sents'][i]['art']]}"
                         f" · Sim₁ = {f(Dx['R'][i])}", 18, PICK if i == rd["win"] else MUTED) for i in rd["tied"]])
        why.arrange(DOWN, buff=0.1, aligned_edge=LEFT).next_to(rules, DOWN, buff=0.25, aligned_edge=LEFT)
        self.play(FadeIn(why))
        self.play(Create(SurroundingRectangle(rows[rd["win"]], color=PICK, buff=0.06, corner_radius=0.05)),
                  Transform(Sbox, self.chip(S).move_to(Sbox)))
        self.wait(2)
        self.clear()

    # ---------- TH2: xung đột thông tin ----------
    def case_conflict(self):
        p = PRESETS["conflict"]
        Dx = compute(p)
        lam, Kx = p["lam"], p["K"]
        S0, r0, _ = mmr(Dx, lam, Kx)
        S1, r1, _ = mmr(Dx, lam, Kx, preset=p, conflict="newer")
        a, b = find_conflicts(p, S0)[0]
        self.case_title(2, "Xung đột thông tin", "Hai nguồn nói ngược nhau")

        h = self.header("TH2 · Xung đột thông tin", f"Sim₁, Sim₂ tính bằng TF-IDF · λ = {lam}, K = {Kx}")
        tags = {a: (f"đăng {p['time'][Dx['sents'][a]['art']]}", MUTED),
                b: (f"đăng {p['time'][Dx['sents'][b]['art']]}", MUTED)}
        rows = self.sent_rows(Dx, tags).next_to(h, DOWN, buff=0.4)
        self.play(FadeIn(h), LaggedStart(*[FadeIn(r) for r in rows], lag_ratio=0.15))

        # MMR thuần
        lab = T("MMR thuần", 24, REL, BOLD)
        steps = VGroup(*[T(f"Vòng {k + 1} → {SL(rd['win'])} ({f(next(c['score'] for c in rd['cand'] if c['i'] == rd['win']))})", 20)
                         for k, rd in enumerate(r0)]).arrange(DOWN, buff=0.1, aligned_edge=LEFT)
        left = VGroup(lab, steps).arrange(DOWN, buff=0.2, aligned_edge=LEFT).next_to(rows, DOWN, buff=0.5).to_edge(LEFT, buff=1.0)
        self.play(FadeIn(lab))
        self.play(LaggedStart(*[FadeIn(s) for s in steps], lag_ratio=0.4))
        c0 = self.chip(S0).next_to(left, DOWN, buff=0.3, aligned_edge=LEFT)
        self.play(FadeIn(c0))
        # đánh dấu cặp mâu thuẫn
        ra = SurroundingRectangle(rows[a], color=PEN, buff=0.05, corner_radius=0.05)
        rb = SurroundingRectangle(rows[b], color=PEN, buff=0.05, corner_radius=0.05)
        warn = VGroup(T(f"Sim₂({SL(a)}, {SL(b)}) = {f(Dx['M'][a][b])}  → MMR tưởng là thông tin mới", 19, PEN),
                      T("Bản tóm tắt chứa cả 2 câu mâu thuẫn (thứ Hai / Hà Nội vs thứ Sáu / TP.HCM)", 19, PEN))
        warn.arrange(DOWN, buff=0.1, aligned_edge=LEFT).next_to(left, RIGHT, buff=1.0).align_to(left, UP)
        fit(warn, 6.5)
        self.play(Create(ra), Create(rb), FadeIn(warn))
        self.wait(1.5)

        # MMR + NLI
        lab2 = T("MMR + kiểm tra NLI trước khi thêm câu", 22, PICK, BOLD)
        rc = next(rd for rd in r1 if rd["conflict"] is not None)
        old, new = rc["conflict"], rc["win"]
        ta, tb = p["time"][Dx["sents"][old]["art"]], p["time"][Dx["sents"][new]["art"]]
        info = VGroup(
            T(f"NLI({SL(new)}, {SL(old)}) = contradiction  (nhãn giả lập)", 19, GOLD),
            T(f"Giữ tin đăng muộn hơn: {tb} > {ta} → thay {SL(old)} bằng {SL(new)}", 19),
            T(f"Chọn tiếp câu kế để đủ K = {Kx}", 19, MUTED),
        ).arrange(DOWN, buff=0.12, aligned_edge=LEFT)
        right = VGroup(lab2, info).arrange(DOWN, buff=0.2, aligned_edge=LEFT)
        fit(right, 6.5).move_to(warn, aligned_edge=UL)
        self.play(FadeOut(warn), FadeIn(lab2))
        self.play(LaggedStart(*[FadeIn(x) for x in info], lag_ratio=0.5))
        cross = Line(rows[old].get_left(), rows[old].get_right(), color=PEN, stroke_width=3)
        self.play(Create(cross), rows[old].animate.set_opacity(0.4), FadeOut(rb))
        c1 = self.chip(S1).next_to(right, DOWN, buff=0.3, aligned_edge=LEFT)
        self.play(FadeIn(c1, shift=UP * 0.2))
        alt = T("Cách khác: đưa cả 2 câu cho LLM viết lại “Theo báo A… nhưng báo B cập nhật…”", 17, MUTED)
        fit(alt, 12.5).to_edge(DOWN, buff=0.3)
        self.play(FadeIn(alt))
        self.wait(2)
        self.clear()

    # ---------- TH3: thông tin chỉ có ở 1 câu ----------
    def case_singleton(self):
        p = PRESETS["singleton"]
        Dc = compute(p)
        Dq = compute(p, query=p["query"])
        Kx, lo, hi, th = p["K"], p["lam_low"], p["lam_high"], p["theta"]
        n = Dc["n"]
        good, bad = 3, 4  # s4 hotline (đúng), s5 quảng cáo (rác)
        self.case_title(3, "Thông tin chỉ có ở 1 câu", "Nếu đúng thì sao, nếu sai thì sao?")

        h = self.header("TH3 · Thông tin đơn lẻ", f"Sim tính bằng TF-IDF · K = {Kx}")
        tags = {good: ("đúng, chỉ 1 câu", PICK), bad: ("rác / lạc đề", PEN)}
        rows = self.sent_rows(Dc, tags, size=18).next_to(h, DOWN, buff=0.25)
        self.play(FadeIn(h), LaggedStart(*[FadeIn(r) for r in rows], lag_ratio=0.15))
        self.wait(0.8)

        # --- A: câu SAI ---
        sub = T(f"A · Câu rác: λ = {lo} (ưu tiên đa dạng), Q = centroid", 22, PEN, BOLD)
        bars = self.bars(range(n), Dc["R"], width=5.0, maxv=1.0).scale(0.75)
        part = VGroup(sub, bars).arrange(DOWN, buff=0.25, aligned_edge=LEFT).next_to(rows, DOWN, buff=0.3).to_edge(LEFT, buff=0.9)
        self.play(FadeIn(sub), FadeIn(bars))
        SA = mmr(Dc, lo, Kx)[0]
        cA = self.chip(SA, PEN).next_to(bars, RIGHT, buff=0.8).align_to(bars, UP)
        nA = fit(T(f"Sim₂({SL(bad)}, mọi câu) = 0 → được thưởng ‘mới lạ’", 18, PEN), 5.6).next_to(cA, DOWN, buff=0.2, aligned_edge=LEFT)
        self.play(FadeIn(cA), FadeIn(nA), bars[bad][3].animate.set_fill(PEN))
        self.wait(1)
        # ngưỡng θ
        trk = bars[0][1]
        x = trk.get_left()[0] + th * trk.width
        tl = DashedLine([x, bars.get_top()[1] + 0.15, 0], [x, bars.get_bottom()[1] - 0.15, 0], color=GOLD)
        tlab = T(f"θ = {th}", 18, GOLD, BOLD).next_to(tl, DOWN, buff=0.08)
        self.play(Create(tl), FadeIn(tlab))
        drop = [i for i in range(n) if Dc["R"][i] < th]
        SA2 = mmr(Dc, lo, Kx, theta=th)[0]
        cA2 = self.chip(SA2).move_to(cA, aligned_edge=LEFT)
        nA2 = fit(T(f"Loại câu có Sim₁ < θ trước khi chạy MMR → {SL(good)} vào thay", 18, PICK), 5.6).move_to(nA, aligned_edge=LEFT)
        self.play(*[bars[i].animate.set_opacity(0.3) for i in drop], Transform(cA, cA2), Transform(nA, nA2))
        self.wait(1.5)
        self.play(FadeOut(VGroup(sub, bars, cA, nA, tl, tlab)))

        # --- B: câu ĐÚNG ---
        sub = T(f"B · Câu đúng: λ = {hi} (ưu tiên liên quan), Q = centroid", 22, PICK, BOLD)
        bars = self.bars(range(n), Dc["R"], width=5.0, maxv=1.0).scale(0.75)
        VGroup(sub, bars).arrange(DOWN, buff=0.25, aligned_edge=LEFT).move_to(part, aligned_edge=UL)
        self.play(FadeIn(sub), FadeIn(bars))
        SB = mmr(Dc, hi, Kx)[0]
        cB = self.chip(SB, PEN).next_to(bars, RIGHT, buff=0.8).align_to(bars, UP)
        nB = fit(T(f"{SL(good)} ít giống ‘đám đông’ → Sim₁ thấp → bị bỏ sót", 18, PEN), 5.6).next_to(cB, DOWN, buff=0.2, aligned_edge=LEFT)
        self.play(FadeIn(cB), FadeIn(nB), Indicate(bars[good], color=PEN))
        self.wait(1)
        # query-focused Q
        sub2 = T(f"B · Q = truy vấn “{p['query']}”", 22, PICK, BOLD).move_to(sub, aligned_edge=LEFT)
        bars2 = self.bars(range(n), Dq["R"], width=5.0, maxv=1.0).scale(0.75).move_to(bars, aligned_edge=UL)
        best = max(range(n), key=lambda i: Dq["R"][i])
        bars2[best][3].set_fill(PICK)
        SB2 = mmr(Dq, hi, Kx)[0]
        cB2 = self.chip(SB2).move_to(cB, aligned_edge=LEFT)
        nB2 = fit(T(f"Sim₁({SL(good)}, Q) tăng lên {f(Dq['R'][good])} → được chọn ngay vòng 1", 18, PICK), 5.6).move_to(nB, aligned_edge=LEFT)
        self.play(Transform(sub, sub2), Transform(bars, bars2), Transform(cB, cB2), Transform(nB, nB2), run_time=1.2)
        extra = fit(T("Cách khác: cộng điểm cho câu có số liệu, ngày tháng, tên riêng (NER)", 17, MUTED), 5.6)
        extra.next_to(nB, DOWN, buff=0.3, aligned_edge=LEFT)
        self.play(FadeIn(extra))
        self.wait(2)
        self.clear()


class MMRCases(MMRDemo):
    def construct(self):
        self.case_tie()
        self.case_conflict()
        self.case_singleton()


class CaseTie(MMRDemo):
    def construct(self):
        self.case_tie()


class CaseConflict(MMRDemo):
    def construct(self):
        self.case_conflict()


class CaseSingleton(MMRDemo):
    def construct(self):
        self.case_singleton()
