# Kế hoạch dọn Git history — CHƯA THỰC HIỆN

Ngày 15/11/2026. Repo `sou1406-ver/cmt-tag`. Đây là kế hoạch cần xác nhận riêng, không phải log các thao tác đã chạy. Người dùng chọn chưa đổi visibility; không tự chuyển private hoặc public.

## 1. Điều kiện trước khi làm

1. Xác nhận riêng phạm vi rewrite, phạm vi remote refs và việc cập nhật branch/tag. Khuyến nghị private trước, thao tác visibility cũng cần xác nhận riêng. Không coi quyền admin là đồng ý.
2. Tạm dừng push từ các thành viên, CI hoặc bot; chụp SHA remote heads/tags và PR refs ngay trước maintenance. Inventory hiện tại ở `GIT_PRIVACY_AUDIT.md` sẽ lỗi thời sau commit mới.
3. Nếu phát hiện credential thật: revoke/rotate trước. Hiện chưa phát hiện mẫu credential đã kiểm.
4. Không thao tác filter-repo trên workspace đang có WIP, raw, outputs, nhãn người hoặc model.

## 2. Backup và rollback

- Tạo mirror clone riêng bằng `git clone --mirror` ở vị trí local riêng tư; đây là **clone read-only từ remote**, không phải `git push --mirror`.
- Trước khi sửa mirror, tạo Git bundle của mọi refs đã lấy và lưu bản sao mirror nguyên trạng, refs inventory cùng SHA256. Bảo vệ backup vì nó chứa dữ liệu cần loại. Không commit/upload bundle hoặc mirror.
- Backup riêng local WIP/untracked và dữ liệu nghiên cứu nếu cần di chuyển môi trường; filter chỉ trong clone mới, không đụng các file đó.
- Kiểm tra bundle/mirror đọc được và toàn vẹn; giữ backup cho tới khi nghiệm thu. Không xóa backup.
- Rollback mặc định: giữ remote nguyên trạng nếu chưa push; bỏ clone thử nghiệm bằng quy trình riêng được duyệt, clone lại từ backup. Nếu đã push lịch sử mới, khôi phục refs cũ cũng có thể tái công khai dữ liệu và cần xác nhận riêng, không tự làm.

## 3. Phạm vi đường dẫn cần loại

Đã xác nhận 50 đường dẫn payload trong `data/` và 2 đường dẫn báo cáo ngoài `data/`. Inventory chính xác theo mốc audit nằm local tại `outputs/git_privacy_audit_20261115/history-removal-candidates.local.txt`; danh sách đường dẫn được ghi ở phụ lục bên dưới, không chứa text.

Trong clone mới, đề xuất dùng một file path policy:

```text
data/
docs/annotation_reviews/multifilm_20261110/REVIEW.md
docs/annotation_reviews/multifilm_20261110/audit_report.json
```

`data/` ở đây là xóa toàn bộ lịch sử thư mục dữ liệu khỏi **Git clone dùng rewrite**, gồm cả README/metadata/coordinator dưới đó; không xóa `G:/dlvb/cmt-tag/data` local. Nếu phát hiện đường dẫn rename/copy khác, thêm chính xác vào policy trước khi chạy. `git-filter-repo` không tự lần theo rename.

Tại mốc audit, không phát hiện payload track trong `outputs/` ngoài README chỉ mục. Không xóa mù mọi file trong `docs/`, guideline hoặc fixtures. Đã quét ngoài `data/`; hai báo cáo kể trên được xác nhận bằng literal overlap. Đoạn ngắn/paraphrase/nội dung khác chưa xác minh phải rà tiếp, không coi regex là bằng chứng toàn bộ docs sạch.

## 4. Công cụ và thử nghiệm local sau khi được duyệt

`git-filter-repo` chưa cài trong `.venv` và chưa có trên PATH. Không tự cài/nâng environment nghiên cứu. Chuẩn bị công cụ trong môi trường riêng, ghi phiên bản, kiểm tài liệu trước khi chạy.

[Tài liệu chính thức git-filter-repo](https://github.com/newren/git-filter-repo/blob/main/Documentation/git-filter-repo.txt) có `--sensitive-data-removal`, `--paths-from-file`, `--invert-paths` và cảnh báo fresh clone. Sau khi được duyệt và backup hoàn tất, lệnh mẫu **chỉ trong clone mới**:

```text
git filter-repo --sensitive-data-removal --invert-paths --paths-from-file <PRIVATE_PATH_POLICY_FILE>
```

Đây chưa phải lệnh đã chạy. Không dùng `--force` để bỏ fresh-clone guard. Không giới hạn riêng `main` bằng `--refs`, vì rewrite một phần dễ giữ lịch sử cũ qua tag/branch. Bao quát mọi branch/tag được duyệt, bao gồm `before-cleanup-20261112`. Ghi commit-map và ref-map cho đối chiếu nghiên cứu.

Không chạy `git push --force`, `git push --mirror`, xóa remote refs hoặc bất kỳ cập nhật rewrite nào trong task hiện tại. Sau dry-run, phải trình diff refs/SHA cũ-mới và kết quả scan để người dùng duyệt riêng. Nếu được duyệt, thiết kế cập nhật từng ref với kiểm tra SHA/lease cụ thể; không đưa sẵn lệnh force push mù.

## 5. Kiểm chứng trước remote

- Quét mọi refs trong clone thử nghiệm, xác nhận path policy và các blob nhạy cảm không còn reachable từ refs đó. Kiểm tra cả file đổi tên và file ngoài data.
- Quét credential dạng nhận diện được và đoạn comment có bằng chứng; chỉ xuất đường dẫn/count, không text hoặc secret.
- Kiểm unit tests, imports, CLI và các link còn active. Guideline, source runtime và fixture hợp lệ không bị mất. Không regenerate raw, nhãn, Gold hay kết quả chỉ để làm checksum khớp.
- Kết quả lịch sử vốn pin commit/file cần sử dụng backup riêng tư và commit-map; không đổi nội dung manifest hoặc hash cũ để che thay đổi lịch sử. Mirror public sau dọn không phải gói đầy đủ để tái lập corpus.
- So refs remote lần cuối với bản chụp ngay trước maintenance. Nếu có push mới ngoài kế hoạch thì dừng, không ghi đè.

## 6. GitHub caches, PR refs và bản sao ngoài repo

`refs/pull/1/head` và `refs/pull/2/head` là refs GitHub quản lý; không giả định push lại main/tag sẽ loại chúng. Làm theo quy trình GitHub Support cho dữ liệu nhạy cảm, đính kèm commit-map/affected refs cần thiết, yêu cầu xử lý PR refs/cached commit views nếu áp dụng. Không tự xóa PR hoặc hứa có thể purge toàn bộ server.

Actions artifacts, runs, releases/assets và forks hiện được API trả 0; phải kiểm lại trước và sau maintenance. Wiki, issue/PR attachments, cache/search index, mirror, clone và bản tải trước chưa được chứng minh thu hồi. Chuyển private hoặc rewrite không làm biến mất các bản đó.

## 7. Hướng dẫn thành viên sau khi hoàn tất

- Gửi thông báo commit/ref mới và commit-map, thời điểm áp dụng, những đường dẫn không còn ở Git.
- Yêu cầu clone mới; không merge/pull lịch sử cũ hoặc push branch/tag cũ trở lại. Chỉ chuyển WIP cần thiết bằng patch đã rà không chứa corpus/credential; không chép nguyên `.git` cũ.
- Corpus, labels, reservation và backup chia sẻ qua kênh riêng được duyệt; không dùng GitHub public làm chỗ lưu dữ liệu.
- Giữ `.gitignore` và test bảo vệ export, rà staged diff; không dùng `git add -f` cho research payload. Không tự trở lại public sau cleanup.

## Phụ lục đường dẫn đã xác minh

Danh sách cụ thể được điền từ inventory local của mốc audit; chỉ là đường dẫn cần xử lý, không phải nội dung comment. Không công bố ID record hoặc nhãn riêng tư.

```text
data/canonical/canonical_37cf670237e3398b5c96/canonical_quality_review.xlsx
data/canonical/canonical_37cf670237e3398b5c96/comments.csv
data/canonical/canonical_37cf670237e3398b5c96/exclusions.csv
data/canonical/canonical_37cf670237e3398b5c96/manifest.json
data/canonical/canonical_37cf670237e3398b5c96/source_regions.json
data/imports/facebook_diverse_sources_20261110/comments.csv
data/imports/facebook_diverse_sources_20261110/comments.xlsx
data/imports/facebook_diverse_sources_20261110/export_manifest.json
data/imports/facebook_diverse_sources_20261110/import_config.json
data/imports/facebook_diversity_batch_20261110/comments.csv
data/imports/facebook_diversity_batch_20261110/comments.xlsx
data/imports/facebook_diversity_batch_20261110/export_manifest.json
data/imports/facebook_diversity_batch_20261110/import_config.json
data/imports/facebook_diversity_batch_20261110/source_list.csv
data/imports/facebook_fresh/comments.csv
data/imports/facebook_fresh/comments.xlsx
data/imports/facebook_fresh/export_manifest.json
data/imports/facebook_fresh/import_config.json
data/imports/facebook_group_1909400102999925/comments.csv
data/imports/facebook_group_1909400102999925/comments.xlsx
data/imports/facebook_group_1909400102999925/export_manifest.json
data/imports/facebook_group_1909400102999925/import_config.json
data/imports/facebook_group_pilot_20261110/comments.csv
data/imports/facebook_group_pilot_20261110/comments.xlsx
data/imports/facebook_group_pilot_20261110/export_manifest.json
data/imports/facebook_group_pilot_20261110/import_config.json
data/imports/facebook_high_activity_20261110/comments.csv
data/imports/facebook_high_activity_20261110/comments.xlsx
data/imports/facebook_high_activity_20261110/export_manifest.json
data/imports/facebook_high_activity_20261110/import_config.json
data/tasks/multifilm_annotation_200_20261110/annotator_a.csv
data/tasks/multifilm_annotation_200_20261110/annotator_a.xlsx
data/tasks/multifilm_annotation_200_20261110/coordinator/input_01.csv
data/tasks/multifilm_annotation_200_20261110/coordinator/input_02.csv
data/tasks/multifilm_annotation_200_20261110/coordinator/input_03.csv
data/tasks/multifilm_annotation_200_20261110/coordinator/input_04.csv
data/tasks/multifilm_annotation_200_20261110/coordinator/input_05.csv
data/tasks/multifilm_annotation_200_20261110/coordinator/input_06.csv
data/tasks/multifilm_annotation_200_20261110/coordinator/input_07.csv
data/tasks/multifilm_annotation_200_20261110/coordinator/prepare_config.json
data/tasks/multifilm_annotation_200_20261110/coordinator/random_pool_manifest.json
data/tasks/multifilm_annotation_200_20261110/coordinator/selection_manifest.json
data/tasks/multifilm_annotation_200_20261110/coordinator/task.json
data/tasks/multifilm_annotation_200_20261110/coordinator/validation_report.json
data/tasks/source_quality_pilot_20261110/annotator_a.csv
data/tasks/source_quality_pilot_20261110/annotator_b.csv
data/tasks/source_quality_pilot_20261110/coordinator/input.csv
data/tasks/source_quality_pilot_20261110/coordinator/prepare_config.json
data/tasks/source_quality_pilot_20261110/coordinator/selection_manifest.json
data/tasks/source_quality_pilot_20261110/coordinator/task.json
docs/annotation_reviews/multifilm_20261110/REVIEW.md
docs/annotation_reviews/multifilm_20261110/audit_report.json
```
