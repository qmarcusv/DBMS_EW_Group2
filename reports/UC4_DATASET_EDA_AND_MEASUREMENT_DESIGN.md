# UC4 — EDA corpus tin tức và thiết kế phép đo FTS

**Trạng thái (2026-10-25):** EDA và thiết kế workload dưới đây là bản trước khi triển khai. UC4 10K đã được tạo và đo sau đó; xem [báo cáo kết quả](UC4_FULL_TEXT_BENCHMARK.md) và [output](../results/uc4/accepted/). Các số tần suất trong tài liệu này vẫn là ước lượng EDA, không thay cho kết quả FTS thực tế. Phase 6 UC5 không đổi tên hay ghi đè.

## 1. Nguồn và một record là gì

Corpus là bản ghim tại commit `9cca94a438905a40883b71c3b5f91c9673b6eec9` của [genesisqu/fake-real-news](https://huggingface.co/datasets/genesisqu/fake-real-news). Hai CSV gốc [Fake.csv](../local_data/source/fake_real_news/Fake.csv) và [True.csv](../local_data/source/fake_real_news/True.csv) được giữ nguyên byte; [PROVENANCE.json](../local_data/source/fake_real_news/PROVENANCE.json) ghi URL, commit, SHA-256 và kích thước. Trang repository ghi nhãn giấy phép `bsd`; đó là metadata của repository, không phải kiểm tra quyền của từng bài báo.

Mỗi **record CSV** là một bài tin với bốn trường:

| Cột gốc | Ý nghĩa đo UC4 | EDA / cách lưu dự kiến |
|---|---|---|
| `title` | Tiêu đề để nhận diện bài, chưa nằm trong trường FTS chính | Không rỗng; dài tối đa 286 ký tự. SQL dự kiến `NVARCHAR(512)`. |
| `text` | Nội dung bài; trường sẽ lập full-text/text index | 631 dòng rỗng hoặc chỉ khoảng trắng; nội dung không rỗng dài tối đa 51.794 ký tự. SQL cần `NVARCHAR(MAX)`. |
| `subject` | Nhóm do nguồn cung cấp, dùng mô tả corpus; không dùng làm điều kiện chính của FTS | Tám giá trị trên hai file, dài tối đa 15 ký tự; các nhóm của Fake/True không trùng tên. |
| `date` | Chuỗi ngày gốc để lưu provenance, không tham gia truy vấn FTS | 10 dòng Fake không khớp bốn dạng ngày EDA nhận diện; dài tối đa 149 ký tự. Lưu `RAW_DATE` dạng text, chưa ép sang `datetime`. |

CSV **không có ID gốc và không có cột nhãn**. Tên file cung cấp nhãn `Fake`/`True` theo nguồn; nhãn này không được dùng để khẳng định tính đúng/sai của từng bài. Khi tạo bản benchmark, gán `SOURCE_FILE`, `SOURCE_ROW` (số record CSV bắt đầu từ 1) và `DOC_ID` ổn định: Fake `DOC_ID = SOURCE_ROW`, True `DOC_ID = 23481 + SOURCE_ROW`. Cùng một record phải có đúng `DOC_ID`, `TITLE`, `BODY` ở SQL và Mongo. Giữ `SUBJECT`, `RAW_DATE`, nhãn nguồn như metadata; index FTS **chỉ trên `BODY`** để phép đo không âm thầm đổi sang title+body.

Schema dự kiến: SQL `DOC_ID BIGINT NOT NULL` với unique key, `TITLE NVARCHAR(512)`, `BODY NVARCHAR(MAX)`, `SUBJECT NVARCHAR(64)`, `RAW_DATE NVARCHAR(160)`, `SOURCE_FILE`, `SOURCE_ROW`. Mongo có các field tương ứng, `DOC_ID` là khóa logic đối chiếu; `_id` mặc định vẫn tồn tại. Đây là thiết kế dự kiến, **chưa phải schema đã triển khai**.

## 2. EDA trên file thực tế

EDA đọc CSV bằng `csv.DictReader`, không sửa nguồn. [Script tái lập](../analysis/uc4_eda.py) và [JSON kết quả](../results/uc4/eda/summary.json) chứa thuật toán/chỉ số đầy đủ. `text` được đếm theo ký tự Unicode; số từ dùng regex `[a-z]+(?:'[a-z]+)?`, vì vậy **không đồng nhất với tokenizer của hai DBMS**.

| Chỉ số | Fake.csv | True.csv | Cả hai |
|---|---:|---:|---:|
| Record gốc | 23.481 | 21.417 | 44.898 |
| `text` không rỗng | 22.851 | 21.416 | 44.267 |
| `text` rỗng/toàn khoảng trắng | 630 | 1 | 631 |
| `text` không rỗng dưới 50 từ EDA | 1.231 | 333 | 1.564 |
| Median độ dài `text`, ký tự | 2.200 | 2.222 | — |
| Median số từ trong `text` | 377 | 361 | — |
| Tiêu đề dài hơn 256 ký tự | 6 | 0 | 6 |
| Ngày không parse được theo bốn format EDA | 10 | 0 | 10 |

Trên 44.267 bài có `text` không rỗng, có **5.623 dòng dư do trùng `text` đúng byte**; không có văn bản đúng byte xuất hiện ở cả hai file. Tiêu đề sau `strip().casefold()` có 6.171 dòng trùng dư, nhưng trùng tiêu đề không đủ để kết luận trùng bài. Các bản trùng text vẫn được giữ trong pilot chính để phản ánh corpus gốc; nếu làm phép đo nhạy cảm sau này, có thể tạo một biến thể bỏ trùng và ghi quy tắc riêng. Không trộn hai biến thể trong cùng bảng kết quả.

Phân bố `subject`: Fake gồm `News` 9.050, `politics` 6.841, `left-news` 4.459, `Government News` 1.570, `US_News` 783, `Middle-east` 778; True gồm `politicsNews` 11.272 và `worldnews` 10.145. Vì tên `subject` lệch theo file, không dùng `subject` để kết luận tác dụng index FTS hoặc làm bộ lọc “cân bằng” giữa hai nhãn. Nội dung chủ yếu là tin tức chính trị, **không phải abstract khoa học**; kết luận UC4 phải được giới hạn cho corpus này.

### Tập pilot 10K cố định

Đề xuất lấy **5.000 record `text` không rỗng từ mỗi file** theo 5.000 giá trị SHA-256 nhỏ nhất của chuỗi `Fake.csv:<SOURCE_ROW>` hoặc `True.csv:<SOURCE_ROW>`. Giữ thứ tự nguồn/row khi gán ID. Quy tắc này cố định theo file gốc đã ghim, không phụ thuộc `random` seed hay thứ tự tải. Nó không bỏ trùng text. EDA trên đúng tập đề xuất cho thấy median **371 từ / 2.213,5 ký tự**, p95 **918 từ / 5.579 ký tự**, và **270 dòng trùng text dư**. Đây mới là tập *đề xuất*; chưa có CSV/DB 10K được xuất hoặc nạp.

Toàn nguồn có 44.898 record, tối đa **44.267 record không rỗng** theo quy tắc hiện tại. Do đó **không thể đo mốc 100K chỉ với dataset này**. Sau pilot 10K, mốc mở rộng hợp lệ là 44.267 record; muốn 100K cần thêm nguồn khác và một manifest mới.

## 3. Chọn query từ EDA, chưa phải kết quả FTS

Số dưới đây là **document frequency trên tập pilot đề xuất**, đếm một bài một lần bằng regex tiếng Anh đơn giản, không phải kết quả `CONTAINS`/`$text`. Query cuối phải được kiểm tra lại sau khi nạp DB và lập index. Các từ `Reuters` hoặc nhãn `Fake`/`True` không được dùng làm query chính vì có thể phản ánh dấu nguồn thay vì chủ đề bài viết.

| ID | Loại | Chuỗi tìm kiếm | Bài khớp theo EDA / 10K | Mục đích |
|---|---|---:|---:|---|
| K_HIGH | Từ khóa | `election` | 2.312 (23,12%) | Nhiều kết quả; kiểm tra lúc index không nhất thiết rẻ hơn scan. |
| K_MED | Từ khóa | `climate` | 324 (3,24%) | Query từ khóa chính có chọn lọc trung bình. |
| K_LOW | Từ khóa | `bitcoin` | 6 (0,06%) | Query hiếm; timer có thể nhiễu, cần đọc p95 và plan. |
| P_HIGH | Cụm từ | `"white house"` | 1.849 (18,49%) | Cụm từ phổ biến. |
| P_MED | Cụm từ | `"climate change"` | 214 (2,14%) | Query cụm từ chính. |
| P_LOW | Cụm từ | `"stock market"` | 37 (0,37%) | Cụm từ ít gặp. |

Các query tối thiểu của Master Plan là **một keyword và một phrase**; K_MED và P_MED đáp ứng điều đó. K_HIGH/P_HIGH và K_LOW/P_LOW giúp thấy ảnh hưởng selectivity. Pilot nên xác nhận số `DOC_ID` khớp, kết quả word breaker và kế hoạch truy vấn trước khi khóa danh sách query. Không ép kế hoạch sử dụng index.

## 4. Baseline A và index C sẽ đo như thế nào

Tạo hai bản sao **cùng 10K record, cùng `DOC_ID`/`BODY`** trên mỗi DBMS. Chỉ sửa các bản sao UC4, không thêm cột vào BIG_TABLE 14 cột hay dùng kết quả UC1–UC3 làm baseline. `B = N/A`: không có B-tree thông thường tương đương về ngữ nghĩa với token/phrase FTS.

| Thành phần | A: không có FTS/text index | C: có FTS/text index |
|---|---|---|
| SQL Server | Unique key trên `DOC_ID` vẫn tồn tại; `BODY LIKE N'%climate%'` và `BODY LIKE N'%climate change%'` là **substring baseline**. | Full-text catalog riêng; index `BODY LANGUAGE 1033`, unique key `DOC_ID`, stoplist/change tracking được ghi rõ. Dùng `CONTAINS(BODY, '"climate"')` và `CONTAINS(BODY, '"climate change"')`. Chờ population xong trước khi đo. |
| MongoDB 7.0 | `_id_` mặc định vẫn tồn tại; tìm `BODY` bằng regex không neo đầu (`/climate/i`, `/climate change/i`) là **substring baseline**. | Một text index `{BODY:'text'}` với `default_language:'english'`; dùng `$text: {$search:'climate'}` và `$text: {$search:'"climate change"'}`. |

Từ/cụm từ ở bảng trên thay vào các mẫu đó, giữ đúng projection `DOC_ID` và cùng điều kiện trong mỗi engine/configuration. Baseline A và C **không được mặc định coi là trả cùng tập ID**: substring có thể khớp giữa từ hoặc từ dài hơn; SQL/Mongo FTS dùng word breaker, stopword và stemming khác nhau. Với mỗi query, lưu count và danh sách/hash `DOC_ID` đã sort cho A/C và hai engine. Chỉ tính A→C speedup như một phép so sánh cùng ngữ nghĩa **nếu tập ID thực tế khớp**; nếu khác, báo cáo riêng độ trễ/độ đúng theo ngữ nghĩa từng phương pháp. SQL `CONTAINS` tìm từ/cụm; Mongo `$text` không có cú pháp wildcard tiền tố tương ứng, và nhiều term không trích dẫn mặc định là OR trong Mongo. [SQL query syntax](https://learn.microsoft.com/en-us/sql/relational-databases/search/query-with-full-text-search), [MongoDB 7.0 `$text`](https://www.mongodb.com/docs/v7.0/reference/operator/query/text/).

Khi thực hiện benchmark: chụp snapshot nguồn và hash subset; kiểm tra 10K IDs/text giống nhau giữa SQL/Mongo; chạy 2 warmup và khoảng 25 lần đo mỗi query/config; tiêu thụ hết kết quả trong timer; lưu raw, median/p95, matched IDs, SQL IO/CPU và actual XML plan, Mongo `executionStats`/keys/docs examined. Chụp plan ngoài vòng timing. Đo **index build riêng** trên bản sao đã nạp đủ; SQL báo thời gian tạo catalog/index và **population completion** tách riêng, Mongo báo `createIndex` và byte index. Từ các bản sao ghi độc lập có hoặc không index, đo INSERT và UPDATE `BODY` bằng cùng những văn bản thật, chuẩn bị payload/ID ngoài timer; ghi thời gian cho tới khi dữ liệu mới thực sự tìm được. SQL cần unique non-null key cho full-text index và phải kiểm tra trạng thái population; điều này được mô tả trong [hướng dẫn SQL Server](https://learn.microsoft.com/en-us/sql/relational-databases/search/create-and-manage-full-text-indexes?view=sql-server-ver17) và [population](https://learn.microsoft.com/en-us/sql/relational-databases/search/populate-full-text-indexes?view=sql-server-ver15).

**Giới hạn diễn giải:** SQL timer dạng T-SQL batch và Mongo timer mongosh tiêu thụ cursor có biên khác nhau; chỉ tính tỷ lệ cải thiện *trong cùng DBMS*. Văn bản dài và trùng lặp ảnh hưởng index size/build/write, nên ghi chúng cùng kết quả. Không suy diễn về arXiv abstract hoặc corpus 100K từ kết quả tin tức này.

## 5. Điểm chốt trước khi triển khai UC4

1. Chốt tập 10K theo quy tắc trên; xuất một artifact chung cho hai DBMS, kèm SHA-256, ánh xạ `DOC_ID`/`SOURCE_ROW`, count và phân bố. File gốc luôn giữ nguyên.
2. Kiểm tra lần nữa SQL Full-Text component/quyền (Phase 1 từng thấy cài đặt sẵn) và quyền tạo text index Mongo trên bản sao UC4. Ghi phiên bản DBMS.
3. Chạy query pilot để ghi ID kết quả thực của A/C và SQL/Mongo. Chỉ sau đó khóa query, index options và phương pháp tổng hợp trước vòng đo chính.
4. Lưu output vào `results/uc4/accepted/`, plan vào `results/uc4/plans/`, lần lỗi vào `results/uc4/archive/`, cập nhật `results/README.md` và báo cáo cuối. Không ghi đè Phase 6 UC5.
