# Schema dữ liệu v1.0 — Phase B

`src/data/schema.py` là validator thực thi, dùng cùng chuẩn cho CSV/JSON.
Schema không suy diễn sentiment bằng keyword.

| Nhóm | Field / quy tắc |
|---|---|
| Identity | `id`, `schema_version`, `source_dataset`, `post_namespace` |
| Text | `text_raw` nguyên văn; `text` NFC + whitespace; SHA-256 raw và normalized casefold |
| Metadata | `comment_id`, `post_id`, `post_url`, `parent_comment_id`, `collected_at`, `movie_id`, `license`, `privacy`: string hoặc null |
| Lineage | `provenance`: input path, SHA-256, row number, role; không coi row number là ID nền tảng |
| Quality | KEEP/EXCLUDE, mảng reasons, `duplicate_of`, `label_conflict` |
| Human | `annotations.human`: lịch sử event, latest event quyết định; revision chưa xác nhận thu hồi gold cũ |
| Machine | `annotations.machine`: lịch sử đề xuất, không ghi đè nhãn người |

Event có `label_source=human/machine`, `status=LABELED/REVIEW/EXCLUDE`.
`label` chỉ được POS, NEG, NEU khi LABELED; REVIEW/EXCLUDE bắt buộc null.
REVIEW cần `REV_MIXED / REV_SARCASM / REV_TARGET / REV_CONTEXT / REV_OTHER`.
Có thể giữ `reason/evidence` tự do khi cần ở phase annotation.

Human gold cần `confirmed=true`, `annotator_id`, `decided_at` ISO có timezone,
`guideline_version`, `evidence_mode=blind/assisted`. Gold đánh giá chỉ nhận blind.
Legacy human column không có các chứng cứ này vẫn giữ label trong event
nhưng `confirmed=false`, `needs_review=true`. Không tự điền ngày xác nhận.

Machine cần `model_id`, `model_version`, `score` hữu hạn hoặc null,
`score_kind`, `is_pseudo`, `needs_review`. `confirmed` luôn false.
`is_pseudo=true` còn cần sentiment + score + `audit_id`. Validator chỉ kiểm tra
reference audit có mặt; Phase E phải xác minh nội dung audit thực nghiệm trước
khi cho vào training. Hiện không có pseudo-label training.

`append_decision` sao chép và thêm event; `gold_label` chỉ đọc quyết định người
được xác nhận. `validate_record` xác minh text/hash và schema. Conflict giữa
human labels trên exact duplicates làm gold bị chặn tới khi phân xử.

Manifest chứa mỗi ID đúng một lần, group ID, split và eligibility annotation.
Quality rejects có split null; exact duplicates vẫn theo cùng split nhóm,
nhưng không eligible. Near candidates giữ cả hai eligible, gom cùng split.
`validate_manifest` dựng lại components để bắt trường hợp manifest bị tách
post/trùng, thiếu dòng hoặc sửa eligibility.

`require_gold=True` yêu cầu gold human cho mọi mẫu eligible, blind ở dev/test,
manifest khóa và không giao nhóm holdout với `used_ids` đã train/tune.
Chưa có workflow khóa gold ở Phase B; không tự sửa `locked_gold` để lách kiểm tra.
Lịch sử dùng dữ liệu phải được các phase train/tune sau này ghi đầy đủ.

`verify_prepared` kiểm tra checksum report/artifacts/raw snapshot, version,
đối soát số dòng và manifest trước khi sử dụng. Checksum phát hiện sai lệch
so với run đã lưu, không thay thế Git/version control hoặc quyền truy cập file.
