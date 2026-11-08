(() => {
  if (window.__fbNhat) {
    console.log("Da chay roi.");
    return;
  }

  const MIN_LEN = 5;

  const SELECTORS = [
    'div[role="article"] div[dir="auto"]',
    'div[aria-label*="Bình luận"] div[dir="auto"]',
    'ul li div[dir="auto"]',
  ];

  const RAC = [
    "Thích", "Phản hồi", "Trả lời", "Chia sẻ", "Xem thêm",
    "Xem thêm bình luận", "Xem các câu trả lời", "Đã chỉnh sửa",
    "Thích Phản hồi", "Viết bình luận", "Bình luận hàng đầu",
    "Tất cả bình luận", "Mới nhất", "Cũ nhất", "Ẩn", "Báo cáo",
    "Xem bản dịch", "Yêu thích", "Thương thương", "Haha", "Wow",
    "Buồn", "Phẫn nộ", "Người viết", "Tác giả", "Theo dõi",
    "Đang theo dõi", "Thành viên", "Quản trị viên", "Người kiểm duyệt",
    "Tham gia", "Đã tham gia", "Mời", "Viết bài", "Bạn đang nghĩ gì",
  ];

  const laRac = (t) => {
    if (t.length < MIN_LEN) return true;
    if (RAC.some((r) => t === r || t.startsWith(r))) return true;
    if (/^\d+$/.test(t)) return true;
    if (/^\d+\s*(phút|giờ|ngày|tuần|năm|thg)/.test(t)) return true;
    if (/^[\d\s,\.]+$/.test(t)) return true;
    if (/^\d+\s*(bình luận|phản hồi|lượt|thành viên)/.test(t)) return true;
    if (/^(Đã chia sẻ|Được tài trợ|Gợi ý cho bạn)/.test(t)) return true;
    return false;
  };

  const laTagNguoi = (a) => {
    const h = a.getAttribute("href") || "";
    if (!h) return false;
    if (/^https?:\/\//i.test(h) && !/facebook\.com/i.test(h)) return false;
    return /^\/|facebook\.com/i.test(h);
  };

  const layText = (el) => {
    let t = (el.innerText || el.textContent || "").trim().replace(/\s+/g, " ");
    const ten = [];
    el.querySelectorAll("a").forEach((a) => {
      if (!laTagNguoi(a)) return;
      const s = (a.innerText || a.textContent || "").trim().replace(/\s+/g, " ");
      if (s) ten.push(s);
    });

    let doi = true;
    while (doi) {
      doi = false;
      for (const s of ten) {
        if (t.startsWith(s)) { t = t.slice(s.length).trim(); doi = true; }
        if (t.endsWith(s)) { t = t.slice(0, -s.length).trim(); doi = true; }
      }
    }
    return t.replace(/^[=+@\-–—•·\s]+/, "").trim();
  };

  const conCut = (t) => /[…\.]{0,3}\s*Xem thêm\s*$/i.test(t);
  const khoa = (s) => s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "").slice(0, 50);

  let kho = {};

  const soDong = () => Object.keys(kho).length;

  const bang = document.createElement("div");
  bang.style.cssText = `
    position:fixed; right:16px; bottom:16px; z-index:2147483647;
    background:#1c1e21; color:#e4e6eb; font:13px/1.45 system-ui,sans-serif;
    border:1px solid #3e4042; border-radius:10px; padding:12px 14px;
    box-shadow:0 6px 24px rgba(0,0,0,.45); min-width:206px; user-select:none;
  `;
  bang.innerHTML = `
    <div style="font-weight:600;margin-bottom:8px">Nhặt comment</div>
    <div style="font-size:26px;font-weight:700;line-height:1.1" id="fbn-so">0</div>
    <div style="color:#b0b3b8;font-size:11px;margin-bottom:9px" id="fbn-phu">
      chưa nhặt được gì
    </div>
    <button id="fbn-nhat">NHẶT (Ctrl+Q)</button>
    <div style="display:flex;gap:5px;margin-top:7px">
      <button id="fbn-tai" style="flex:1">Tải CSV</button>
      <button id="fbn-xoa" style="color:#ff7b72">Xóa</button>
    </div>
  `;
  document.body.appendChild(bang);

  const css = document.createElement("style");
  css.textContent = `
    #fbn-nhat,#fbn-tai,#fbn-xoa{
      background:#3a3b3c;color:#e4e6eb;border:0;border-radius:6px;
      padding:6px 9px;font:12px system-ui,sans-serif;cursor:pointer;
    }
    #fbn-nhat{width:100%;padding:9px;background:#2d6cdf;color:#fff;
      font-weight:600;font-size:13px}
    #fbn-nhat:hover{background:#4680e8}
    #fbn-tai:hover,#fbn-xoa:hover{background:#4e4f50}
  `;
  document.head.appendChild(css);

  const elSo = bang.querySelector("#fbn-so");
  const elPhu = bang.querySelector("#fbn-phu");

  const veBang = () => {
    elSo.textContent = soDong();
    elPhu.textContent = soDong() ? `${soDong()} dòng` : "chưa nhặt được gì";
  };

  const nhat = () => {
    let them = 0, cut = 0;
    for (const sel of SELECTORS) {
      let els;
      try { els = document.querySelectorAll(sel); } catch (e) { continue; }
      els.forEach((el) => {
        const t = layText(el);
        if (laRac(t)) return;
        if (conCut(t)) { cut++; return; }
        const k = khoa(t);
        if (!k) return;
        if (!(k in kho)) { kho[k] = t; them++; }
        else if (t.length > kho[k].length) kho[k] = t;
      });
    }
    elSo.textContent = soDong();
    const p = [];
    if (them) p.push(`+${them} mới`);
    if (cut) p.push(`bỏ ${cut} chưa bung`);
    elPhu.textContent = p.length
      ? `${p.join(" · ")} · tổng ${soDong()}`
      : `không có gì mới · tổng ${soDong()}`;
    elSo.style.color = them ? "#31a24c" : (cut ? "#e3a008" : "#ff7b72");
    setTimeout(() => { elSo.style.color = ""; veBang(); }, 1800);
    console.log(`+${them} moi | bo ${cut} con "Xem them" | tong ${soDong()}`);
  };

  bang.querySelector("#fbn-nhat").onclick = nhat;

  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && (e.key === "q" || e.key === "Q")) {
      e.preventDefault();
      nhat();
    }
  });

  bang.querySelector("#fbn-tai").onclick = () => {
    const rows = Object.values(kho);
    if (!rows.length) { alert("Chưa có dữ liệu."); return; }
    const esc = (s) => '"' + String(s).replace(/"/g, '""') + '"';
    const csv = "﻿" + "text\n" + rows.map(esc).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8;" }));
    a.download = `comments_fb_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
    console.log(`Da tai ${rows.length} dong.`);
  };

  bang.querySelector("#fbn-xoa").onclick = () => {
    if (!confirm(`Xóa toàn bộ ${soDong()} dòng?`)) return;
    kho = {};
    veBang();
  };

  window.addEventListener("beforeunload", (e) => {
    if (soDong()) {
      e.preventDefault();
      e.returnValue = "";
    }
  });

  window.__fbNhat = true;
  veBang();
  console.log("San sang. Bam NHAT hoac Ctrl+Q.");
})();