# Git privacy audit

Ngày 15/11/2026 (Asia/Bangkok). Mốc kiểm tra: `0eec814a46ad4796f25ea5b32e4cf50f76a459e9`. Chỉ báo đường dẫn, loại và số lượng; không trích text, tên tài khoản hoặc giá trị credential.

## Trạng thái và quyết định

- GitHub API xác nhận `sou1406-ver/cmt-tag` **public**, kết nối có quyền admin. Người dùng chọn **“Chưa đổi, chỉ lập báo cáo”** khi được hỏi chuyển private. Không đổi visibility.
- Nhánh local/remote chính: `main`; origin HTTPS không nhúng credential. Có WIP Transformer từ trước, giữ nguyên và không đưa vào commit này.
- Remote có `refs/heads/main`, tag `before-cleanup-20261112` tại `0c9e1a240f5661d1df25949ee33f1ff9ff1e4238`, và hai PR refs: `refs/pull/1/head`, `refs/pull/2/head`. Các ref này vẫn có thể dẫn tới lịch sử chứa dữ liệu.
- Không rewrite, force push, mirror push, xóa remote branch/tag hoặc xóa dữ liệu local/backup.

Nếu sau này người dùng chọn private: vào repo → **Settings → Danger Zone → Change repository visibility → Make private**, đọc cảnh báo và xác nhận đúng repo. Công cụ GitHub kết nối hiện có chỉ hỗ trợ đọc metadata, không có thao tác đổi visibility. Đây là hướng dẫn, chưa thực hiện. [Hướng dẫn GitHub](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility) lưu ý public forks vẫn public khi repo gốc đổi private.

## Phạm vi và phát hiện

Đã kiểm 82 commit reachable qua refs local, 735 blob khác nhau, 410 đường dẫn lịch sử; đối chiếu remote refs và PR refs. Cây HEAD ban đầu có 105 file track. Không giới hạn vào `data/`.

| Vị trí/loại | Bằng chứng đếm được | Rủi ro |
|---|---:|---|
| `data/imports/` trong lịch sử | 25 đường dẫn CSV/XLSX/JSON | Cao: bình luận, ID/permalink/provenance và text có thể còn tên được tag |
| `data/tasks/` trong lịch sử | 20 đường dẫn CSV/XLSX/JSON | Cao: annotation, coordinator và dữ liệu dùng để gán nhãn |
| `data/canonical/` trong lịch sử | 5 đường dẫn CSV/XLSX/JSON | Cao: corpus, exclusions và metadata liên kết |
| Hai báo cáo `docs/annotation_reviews/multifilm_20261110/` | 2 file; lần lượt 13 và 17 chuỗi dài trùng literal với nguồn Facebook | Cao: nội dung thật nằm ngoài thư mục dữ liệu |
| Cookie/token/private-key dạng nhận diện được | 0 phát hiện trong blob và mẫu kiểm tra commit message | Chưa phát hiện credential; không chứng minh mọi dạng secret đều vắng mặt |

50 đường dẫn payload lịch sử gồm 20 CSV, 8 XLSX, 22 JSON; đây là số file, **không phải số comment duy nhất**. Hai báo cáo ngoài `data/` là `REVIEW.md` và `audit_report.json`; số match không cộng thành số người hay số comment duy nhất.

Các commit đã xác minh chứa/loại payload:

- `11038810f5a4`: có CSV, Excel và export/import metadata Facebook.
- `b0f88454b88f`: có nhiều import, canonical và annotation payload.
- `39015b479164`: ngừng track payload trong `data/`, nhưng không xóa các blob khỏi lịch sử và không loại hai báo cáo trên.

## Cây file hiện tại và việc đã làm

Không có corpus dưới `data/` hoặc `outputs/` được track; `outputs/README.md` là chỉ mục. Pilot A/B và workbook audit nằm trong `outputs/` và bị ignore. Không đưa workbook, labels, coordinator hoặc manifest chứa ID lên Git.

Đã ngừng track đúng hai báo cáo có text thật trong `docs/annotation_reviews/multifilm_20261110/`, **giữ nguyên cả hai file local và SHA256**. `audit_report.json` vẫn ở đường dẫn local được `outputs/development/reviewed/manifest.json` pin. Đây là bỏ khỏi cây Git mới, không phải xóa dữ liệu nguồn hay dọn history.

`.gitignore` bổ sung chặn CSV/Excel/JSONL/Parquet/archive xuất nhầm ra ngoài `data/outputs`, các report annotation local, cookie/storage-state và browser profile. Chỉ mở lại CSV fixture và config `*.example.csv`; có test kiểm ignore ngoài các thư mục mặc định. `.gitignore` không ngăn được `git add -f` hoặc nội dung cá nhân chèn vào file code/Markdown: vẫn phải rà staged diff trước push.

Fixtures/code/config có URL Facebook dùng cho kiểm thử/parser không tự chứng minh có dữ liệu cá nhân. Các ví dụ trong guideline và các tài liệu ngoài hai file đã xác nhận không được coi là tự động an toàn tuyệt đối: phép đối chiếu literal dài chỉ phát hiện bản trùng trực tiếp, không phát hiện hết các đoạn paraphrase/đoạn ngắn/tên riêng. Không công bố nội dung để minh họa.

## Bề mặt GitHub khác

API GET read-only tại thời điểm kiểm tra xác nhận:

| Hạng mục | Kết quả |
|---|---:|
| Actions workflow runs | 0 |
| Actions artifacts toàn repo | 0 |
| Releases / release assets | 0 / 0 |
| Fork được API liệt kê | 0 |
| GitHub Pages (`has_pages`) | false |

Connector không hỗ trợ endpoint liệt kê global artifacts/forks; đã dùng public REST GET để xác minh thay vì suy từ 0 workflow runs. Wiki được bật (`has_wiki=true`) nhưng **chưa kiểm đầy đủ nội dung wiki**, discussion/issue attachment, cache, mirror hoặc các bản clone đã tải. Hai PR refs vẫn tồn tại. Không thể suy không có bản sao bên ngoài chỉ vì API trả 0 forks/artifacts.

Nguồn read-only: [repository API](https://api.github.com/repos/sou1406-ver/cmt-tag), [Actions artifacts](https://api.github.com/repos/sou1406-ver/cmt-tag/actions/artifacts), [workflow runs](https://api.github.com/repos/sou1406-ver/cmt-tag/actions/runs), [releases](https://api.github.com/repos/sou1406-ver/cmt-tag/releases), [forks](https://api.github.com/repos/sou1406-ver/cmt-tag/forks).

## Giới hạn credential scan

Đã dò mẫu token GitHub/OpenAI/Facebook, AWS access key ID, private-key header và cookie c_user/xs; không in match. Không thấy đường dẫn cookie/profile/secret thực được track. Binary nén, secret bị chia nhỏ/encode, nội dung đính kèm bên ngoài và secret không khớp các mẫu chưa được bảo đảm. Nếu phát hiện credential thực ở bước rà sâu, phải revoke/rotate trước; dọn Git không thay thế thu hồi credential.

## Pilot và guideline

File `SENTIMENT_GUIDELINE_V3_1.md` chính thức **chưa tìm thấy** trong repo, workspace, Downloads hoặc các attachments đã kiểm. Không tạo bản chính thức từ PROPOSED và không chuyển pilot sang APPROVED.

Pilot cũ còn nguyên 200 ID: 160 random + 40 hard, 28 bài, 3 nguồn, 98 comment + 102 reply. Hai workbook chưa có nhãn/note/issue. Đã lưu local manifest SHA, nguồn SHA, danh sách 200 ID và checksum toàn bộ file pilot để đối chiếu khi có guideline. **Không xóa hoặc regenerate pilot** khi thiếu nguồn chính thức; chưa có cohort mới để so sánh.

Code được chuẩn bị để dùng file chính thức riêng khi được cung cấp, pin SHA256 đã xác minh vào `APPROVED_GUIDELINE_SHA256` và hiển thị READY/APPROVED_FOR_PILOT nhất quán trong output mới. Chỉ có file đúng tên chưa đủ để READY; chưa pin SHA thì OFFICIAL_PENDING_VERIFICATION. Khi chỉ có PROPOSED, vẫn DRAFT. Không đổi sampling, validation nhãn, Kappa hoặc text nguồn. Có test nhánh official/proposed/unverified/hash mismatch bằng fixture, không coi fixture là guideline thật.

Chi tiết có ID rút gọn của 5 hard case và reason chỉ lưu local ở `outputs/git_privacy_audit_20261115/pilot_before.local.json`; không đưa ID vào báo cáo public. Không dùng nhãn relevance làm sentiment, không sửa 107 nhãn hoặc gán nốt 193 câu.

## Kiểm thử và thay đổi

Toàn bộ unittest: **275 pass, 0 fail, 0 skip**; log local `outputs/git_privacy_audit_20261115/unittest_final.log`. Có kiểm ignore exports ngoài data/outputs, official/proposed/SHA guard và các regression Kappa/validation đã có. Checksum toàn bộ file pilot, hai báo cáo được untrack và tập input bảo vệ raw/canonical/Gold/audit đều khớp trước/sau.

Thay đổi: `.gitignore`, `.gitattributes`, README, chỉ mục lịch sử, hai tài liệu privacy, helper guideline trong `src/annotation/sentiment_pilot.py`, phần hướng dẫn exporter và tests liên quan. Không sửa sampling, label validation hoặc công thức Kappa; không sửa crawler/cleaning. Hai báo cáo cũ chỉ bỏ Git index, không xóa local. WIP Transformer từ trước được giữ ngoài commit.

## Kết luận

**Lịch sử public vẫn chứa dữ liệu Facebook.** Ngừng track hai báo cáo và tăng ignore chỉ giảm nguy cơ commit tiếp, chưa xử lý exposure cũ. Kế hoạch history ở [GIT_HISTORY_CLEANUP_PLAN.md](GIT_HISTORY_CLEANUP_PLAN.md), chưa chạy. Khuyến nghị private trước khi dọn; đổi private cũng không thu hồi clone/fork/bản sao đã tải. Blocker giao pilot: thiếu file guideline chính thức.
