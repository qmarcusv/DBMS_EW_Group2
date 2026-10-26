"""Teaching narrative and rich structured content for the DBMS_Group2 Streamlit companion app.

Directly aligned with the approved V3 PDF report (report/main.pdf)
and Phase 8 verified evidence artifacts.
"""

from __future__ import annotations

# ==============================================================================
# DATASETS METADATA & EDA
# ==============================================================================
DATASETS_METADATA = {
    "corpus1": {
        "name": "Corpus 1 — Metadata Catalog (BIG_TABLE)",
        "scales": ["10K", "100K", "1M"],
        "used_in": ["UC1 (100K)", "UC2 (100K & 1M)", "UC3 (100K & 1M)", "UC5 (1M)"],
        "schema": "(ID INT, OBJECT_ID INT, DATA_OBJECT_ID INT, OWNER VARCHAR(128), OBJECT_NAME VARCHAR(128), SUBOBJECT_NAME VARCHAR(128), OBJECT_TYPE VARCHAR(23), CREATED DATETIME, LAST_DDL_TIME DATETIME, TIMESTAMP VARCHAR(19), STATUS VARCHAR(7), TEMPORARY CHAR(1), GENERATED CHAR(1), SECONDARY CHAR(1))",
        "description": "Bảng danh mục metadata của database gồm 14 cột, mô phỏng các đối tượng hệ thống (tables, indexes, views, packages...). Dữ liệu phân bố lệch rất mạnh đặc trưng của metadata thực tế.",
        "eda_highlights": [
            "Độ lệch cột OWNER: Tại 100K dòng, OWNER = 'SYS' sở hữu 71,802 dòng (71.80%), trong khi 'CTXSYS' chỉ sở hữu 398 dòng (0.40%).",
            "Độ lệch cột cờ TEMPORARY: Chỉ có 254 dòng TEMPORARY = 'Y' (0.254%) tại 100K và 2,405 dòng (0.241%) tại 1M, còn lại 99.76% là 'N'.",
            "Độ phân tán cột OBJECT_TYPE: Có 35 nhóm đối tượng khác nhau trên quy mô 1M dòng (phù hợp cho bài toán phân tích GROUP BY ở UC5)."
        ]
    },
    "corpus2": {
        "name": "Corpus 2 — English News Prose (uc4_seed_10k)",
        "scales": ["10,000 articles"],
        "used_in": ["UC4 (10K)"],
        "schema": "(DOC_ID INT, TITLE NVARCHAR(500), BODY NVARCHAR(MAX), SUBJECT VARCHAR(100), RAW_DATE VARCHAR(50), SOURCE_FILE VARCHAR(100), SOURCE_ROW INT)",
        "description": "Tập hợp 10,000 bài báo tiếng Anh (5,000 bài tin thật và 5,000 bài tin giả) được lấy mẫu tất định từ tập genesisqu/fake-real-news, phục vụ kiểm thử tìm kiếm toàn văn.",
        "eda_highlights": [
            "Độ dài trường BODY: Trung vị là 371 từ (2,213.5 ký tự); phân vị thứ 95 đạt 918 từ (5,579 ký tự), buộc phải dùng kiểu NVARCHAR(MAX) trong SQL Server.",
            "Tần suất xuất hiện từ khóa: 'election' xuất hiện trong 2,577 bài; 'climate' trong 326 bài; 'bitcoin' chỉ trong 7 bài.",
            "Tần suất cụm từ chính xác: 'white house' (1,851 bài), 'climate change' (214 bài), 'stock market' (45 bài)."
        ]
    },
    "corpus3": {
        "name": "Corpus 3 — Categorical Tag Memberships (parents_10k.jsonl)",
        "scales": ["10,000 parents / 30,471 tags"],
        "used_in": ["UC6 (10K Parents)"],
        "schema": "MongoDB: {PARENT_ID: INT, OWNER: STR, OBJECT_TYPE: STR, tags: [STR]} | SQL Server: UC6_Parent(PARENT_ID PK) và UC6_Tag(PARENT_ID, TAG)",
        "description": "Tập 10,000 đối tượng cha được sinh tất định từ BIG_TABLE 10K, mỗi đối tượng gắn từ 3 đến 5 tag phân loại (owner:<OWNER>, type:<TYPE>, temporary:<TEMP>, generated, subobject).",
        "eda_highlights": [
            "Mỗi parent có trung bình 3.05 tag: 9,631 parent có đúng 3 tag; 267 parent có 4 tag; 102 parent có 5 tag.",
            "Tag phổ biến nhất: type:TABLE (1,247 parent), owner:SYS + type:TABLE (1,125 parent).",
            "Tag hiếm: temporary:Y (51 parent), type:TABLE + temporary:Y (41 parent)."
        ]
    }
}

# ==============================================================================
# SIX COMPREHENSIVE USE CASES
# ==============================================================================
STORIES = {
    "uc1": {
        "title": "UC1 · Compound B-Tree Index",
        "full_title": "UC1: Multi-Column Lookups and Sorting → Compound B-Tree Index",
        "scale": "100K bản ghi Catalog metadata",
        "workload_type": "OLTP / Metadata Catalog Filtering & Sorting",
        "index_target": "Compound B-Tree Index (OWNER, OBJECT_TYPE, OBJECT_ID)",
        "index_category": "B-Tree Design Technique (Thứ tự khóa đa cột & Triệt tiêu toán tử Sort)",
        "source": "Báo cáo V3: Chương 2.1, Chương 4.1 và Chương 5 | reports/PHASE3_UC1_COMPOUND.md",
        "problem_statement": """Trong các hệ thống quản lý danh mục (metadata catalog), người dùng hầu như không bao giờ chỉ tìm kiếm theo một cột đơn lẻ. Thay vào đó, ứng dụng thường xuyên lọc theo tổ hợp nhiều cột (ví dụ: tìm tất cả bảng thuộc về user SYS có OBJECT_ID cụ thể), hoặc yêu cầu hiển thị danh sách đối tượng của một chủ sở hữu đã được sắp xếp sẵn theo loại đối tượng và mã định danh.

Nếu chỉ tạo chỉ mục đơn cột thông thường trên (OWNER), khi truy vấn một người dùng chiếm phần lớn dữ liệu (chẳng hạn OWNER = 'SYS' chiếm tới 71.8% dữ liệu), DBMS vẫn phải duyệt qua hàng chục nghìn con trỏ index và sau đó tốn thêm bộ nhớ/CPU để sắp xếp kết quả. Ngược lại, Compound B-Tree gom nhiều cột vào chung một cây chỉ mục duy nhất để giải quyết cả hai bài toán này.""",
        "why_fits": """Một Compound B-Tree sắp xếp các khóa theo thứ tự từ điển (lexicographical order) giống như một cuốn danh bạ điện thoại được xếp theo Họ → Tên đệm → Tên. Nhờ đó, các bản ghi có cùng OWNER sẽ được gom lại cạnh nhau; trong cùng một OWNER, các bản ghi được xếp thứ tự theo OBJECT_TYPE; và trong cùng OBJECT_TYPE, chúng được xếp theo OBJECT_ID.

Cấu trúc này cho phép:
1. Seek trực tiếp tới dải hẹp nhất khi truy vấn cung cấp các cột đầu tiên (U1a, U1b).
2. Đọc trực tiếp các trang lá theo đúng thứ tự mà KHÔNG cần tốn toán tử sắp xếp riêng biệt (Sort Elimination trong U1d).""",
        "theoretical_tradeoff": """- Quy tắc tiền tố trái (Left-prefix rule): Nếu câu truy vấn không cung cấp cột đầu tiên OWNER (U1c), các giá trị OBJECT_TYPE = 'TABLE' sẽ nằm rải rác ở khắp mọi nhánh của cây B-tree, khiến DBMS không thể thực hiện một lần seek liên tục mà buộc phải scan toàn bộ index hoặc scan bảng.
- Đánh đổi lưu trữ và bảo trì: Mỗi entry trong index phải lưu cả 3 cột thay vì 1 cột, làm kích thước index tăng gần gấp đôi và làm chậm tốc độ ghi mỗi khi bất kỳ cột nào trong bộ ba bị thay đổi.""",
        "configs": {
            "A": {
                "name": "Baseline A (Heap / No Secondary Index)",
                "sql": "Bảng Heap (không có chỉ mục phụ). Truy vấn bắt buộc quét toàn bộ bảng (Table Scan).",
                "mongo": "Collection chỉ có chỉ mục mặc định {_id_: 1}. Truy vấn dùng COLLSCAN."
            },
            "B": {
                "name": "Config B (Conventional Single-Key Index)",
                "sql": "CREATE NONCLUSTERED INDEX IX_UC1_B_Owner ON DEMO_BIG_TABLE_100K(OWNER);",
                "mongo": "db.big_table_100k.createIndex({OWNER: 1});"
            },
            "C": {
                "name": "Config C (Target Compound B-Tree Index)",
                "sql": "CREATE NONCLUSTERED INDEX IX_UC1_C_Compound ON DEMO_BIG_TABLE_100K(OWNER, OBJECT_TYPE, OBJECT_ID);",
                "mongo": "db.big_table_100k.createIndex({OWNER: 1, OBJECT_TYPE: 1, OBJECT_ID: 1});"
            }
        },
        "query_architecture_note": "📌 Lưu ý phương pháp luận: UC1 thiết kế 4 câu truy vấn RIÊNG BIỆT (U1a, U1b, U1c, U1d) có chủ đích, nhằm cô lập và kiểm chứng từng tính chất của Compound B-Tree theo lý thuyết chứ KHÔNG dùng chung một câu query!",
        "queries": {
            "U1a": {
                "code": "U1a",
                "name": "Full-key Equality (Lọc chính xác cả 3 cột)",
                "purpose": "Kiểm tra khả năng seek tối đa khi cung cấp đầy đủ cả 3 cột khóa có trong index. Kết quả trả về rất hẹp (chỉ 2 dòng).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Khảo sát trường hợp lý tưởng nhất của Compound Index.",
                "matched_rows": 2,
                "sql": "SELECT ID, OWNER, OBJECT_TYPE, OBJECT_ID\nFROM DEMO_BIG_TABLE_100K\nWHERE OWNER = N'SYS'\n  AND OBJECT_TYPE = N'TABLE'\n  AND OBJECT_ID = 16;",
                "mongo": "db.big_table_100k.find(\n  {OWNER: 'SYS', OBJECT_TYPE: 'TABLE', OBJECT_ID: 16},\n  {_id: 0, ID: 1, OWNER: 1, OBJECT_TYPE: 1, OBJECT_ID: 1}\n)",
                "expected": "Compound C seek thẳng tới 2 bản ghi. Single-Key B phải duyệt toàn bộ 71,802 dòng SYS rồi mới lọc tiếp.",
                "finding": "MongoDB C đạt 2.34 ms (nhanh hơn A 103x, nhanh hơn B 198x!). Trong MongoDB, Config B bị chậm hơn A gần 2x (462.8 ms vs 241.0 ms) do duyệt 71,802 key và FETCH 71,802 docs ngẫu nhiên từ đĩa/RAM. SQL Server C giảm từ 2,730 trang đọc xuống còn đúng 5 trang (nhanh hơn 3.42x)."
            },
            "U1b": {
                "code": "U1b",
                "name": "Two-column Prefix (Lọc 2 cột tiền tố đầu)",
                "purpose": "Kiểm tra quy tắc tiền tố trái (Left-prefix rule) khi lọc trên 2 cột (OWNER, OBJECT_TYPE). Kết quả trả về 3,405 dòng.",
                "is_shared": "Truy vấn RIÊNG BIỆT: Khảo sát hành vi của query optimizer khi số dòng khớp khá lớn.",
                "matched_rows": 3405,
                "sql": "SELECT ID, OWNER, OBJECT_TYPE, OBJECT_ID\nFROM DEMO_BIG_TABLE_100K\nWHERE OWNER = N'SYS'\n  AND OBJECT_TYPE = N'TABLE';",
                "mongo": "db.big_table_100k.find(\n  {OWNER: 'SYS', OBJECT_TYPE: 'TABLE'},\n  {_id: 0, ID: 1, OWNER: 1, OBJECT_TYPE: 1, OBJECT_ID: 1}\n)",
                "expected": "Index C seek được dải tiền tố SYS + TABLE. Tuy nhiên số dòng khớp (3,405) có thể khiến optimizer cân nhắc chi phí lookup.",
                "finding": "Hiện tượng suy giảm thực tế: Trên SQL Server, Config C vẫn chọn Table Scan 2,730 trang (p50 = 98.0 ms, p95 = 673.3 ms) vì thực hiện 3,405 lần RID Lookup ngẫu nhiên về bảng heap đắt hơn quét tuần tự! Trong khi đó MongoDB C dùng IXSCAN + FETCH và nhanh hơn A 6.44x (39.31 ms vs 253.16 ms)."
            },
            "U1c": {
                "code": "U1c",
                "name": "Missing Leading Column (Bỏ sót cột khóa đầu tiên)",
                "purpose": "Kiểm tra hành vi khi truy vấn vi phạm quy tắc tiền tố trái: lọc theo OBJECT_TYPE và OBJECT_ID nhưng KHÔNG có OWNER.",
                "is_shared": "Truy vấn RIÊNG BIỆT: Chứng minh giới hạn vật lý của cây B-tree khi thiếu cột dẫn đầu.",
                "matched_rows": 2,
                "sql": "SELECT ID, OWNER, OBJECT_TYPE, OBJECT_ID\nFROM DEMO_BIG_TABLE_100K\nWHERE OBJECT_TYPE = N'TABLE'\n  AND OBJECT_ID = 16;",
                "mongo": "db.big_table_100k.find(\n  {OBJECT_TYPE: 'TABLE', OBJECT_ID: 16},\n  {_id: 0, ID: 1, OWNER: 1, OBJECT_TYPE: 1, OBJECT_ID: 1}\n)",
                "expected": "Không thể thực hiện B-tree Seek trên C. Cả hai hệ thống buộc phải quét toàn bộ cây index hoặc quét bảng.",
                "finding": "Cả hai hệ thống đều không seek được: MongoDB C quay về COLLSCAN toàn bộ 100K doc (232.18 ms, tương đương A). SQL Server C thông minh hơn khi quét toàn bộ 657 trang lá của chính index C (Index Scan) thay vì quét 2,730 trang bảng gốc, hoàn thành trong 20.04 ms (nhanh hơn A 1.85x)."
            },
            "U1d": {
                "code": "U1d",
                "name": "Prefix Filter + Matching Sort (Lọc tiền tố + Sắp xếp trùng khóa)",
                "purpose": "Kiểm chứng khả năng TRIỆT TIÊU TOÁN TỬ SẮP XẾP (Sort Elimination) khi thứ tự ORDER BY trùng khớp thứ tự các cột tiếp theo trong B-Tree.",
                "is_shared": "Truy vấn RIÊNG BIỆT: Khảo sát lợi ích loại bỏ giai đoạn Sort trên 398 dòng kết quả.",
                "matched_rows": 398,
                "sql": "SELECT ID, OWNER, OBJECT_TYPE, OBJECT_ID\nFROM DEMO_BIG_TABLE_100K\nWHERE OWNER = N'CTXSYS'\nORDER BY OBJECT_TYPE ASC, OBJECT_ID ASC;",
                "mongo": "db.big_table_100k.find(\n  {OWNER: 'CTXSYS'},\n  {_id: 0, ID: 1, OWNER: 1, OBJECT_TYPE: 1, OBJECT_ID: 1}\n).sort({OBJECT_TYPE: 1, OBJECT_ID: 1})",
                "expected": "Config B phải seek rồi chạy toán tử Sort tốn CPU. Config C đọc các trang lá đã xếp sẵn thứ tự và không cần Sort.",
                "finding": "Triệt tiêu toán tử Sort thành công: Cả B và C đều seek được 398 dòng của CTXSYS, nhưng Config B phải chạy toán tử Sort (SQL) hoặc blocking SORT stage (Mongo). Config C loại bỏ hoàn toàn Sort operator, giảm p95 SQL từ 56.56 ms xuống 29.11 ms và giảm Mongo p50 từ 236.43 ms (A) xuống 7.97 ms (C)."
            }
        },
        "default_query": "U1a",
        "mermaid_diagram": """flowchart LR
  subgraph Compound_Tree ["Cấu trúc lá Compound B-Tree (OWNER, TYPE, ID)"]
    K1["'CTXSYS', 'INDEX', 19"] --> K2["'CTXSYS', 'TABLE', 12"]
    K2 --> K3["'SYS', 'INDEX', 8"]
    K3 --> K4["'SYS', 'TABLE', 16"]
  end
  Q1["U1a: OWNER='SYS' AND TYPE='TABLE' AND ID=16"] -->|B-tree Seek trực tiếp| K4
  Q2["U1d: OWNER='CTXSYS' ORDER BY TYPE, ID"] -->|Seek CTXSYS + đọc theo thứ tự lá| K1
  Q3["U1c: Thiếu OWNER (chỉ có TYPE='TABLE')"] -.->|Không thể Seek liên tục vì TABLE nằm rải rác| Compound_Tree
""",
        "plan_analysis": """1. Hiện tượng suy giảm của Single-Key B trên dữ liệu lệch: Do OWNER='SYS' chiếm 71.8% dữ liệu, MongoDB B duyệt 71,802 key và FETCH 71,802 docs ngẫu nhiên khiến latency tăng vọt lên 462.8 ms (chậm gấp đôi so với quét toàn bộ 100K doc tuần tự của A). Compound C khắc phục triệt để bằng cách thu hẹp dải seek xuống đúng 2 doc.
2. Vì sao SQL Server bỏ qua C trên U1b: Khi số dòng khớp lên tới 3,405 dòng, SQL Server ước lượng chi phí 3,405 lần nhảy RID Lookup ngẫu nhiên về bảng Heap đắt hơn việc quét tuần tự 2,730 trang dữ liệu. Do đó optimizer tự động chọn Table Scan.
3. Sort Elimination: Actual Execution Plan của C trên U1d không chứa toán tử Sort, giúp ổn định đuôi độ trễ (p95).""",
        "tradeoffs_measured": """- Dung lượng Index: SQL Server C (5.19 MB) lớn hơn B (2.64 MB) tới +96.5%. MongoDB C (0.90 MB) lớn hơn B (0.48 MB) tới +87.8%.
- Tốc độ ghi (Batch INSERT): Trên MongoDB, tốc độ nạp dữ liệu giảm 33.5% (từ 39,368 dòng/s ở A xuống 26,191 dòng/s ở C).
- Thời gian dựng index: 1,969 ms (SQL) và 931 ms (Mongo).""",
        "verdict": "NÊN DÙNG Compound B-Tree khi câu truy vấn thường xuyên lọc theo các cột đầu tiên của khóa hoặc có mệnh đề ORDER BY trùng khớp thứ tự các cột phụ. TRÁNH DÙNG khi truy vấn bỏ sót cột khóa đầu tiên (U1c) hoặc tiền tố khớp hàng ngàn dòng mà không có các cột được phủ (U1b)."
    },

    "uc2": {
        "title": "UC2 · Filtered & Partial Index",
        "full_title": "UC2: Skewed Active-Flag Queries → Filtered and Partial Indexes",
        "scale": "100K và 1M bản ghi Catalog metadata",
        "workload_type": "High-Skew Status Flag Queries (Active Dashboard vs Batch Archive)",
        "index_target": "Filtered Index (SQL Server) / Partial Index (MongoDB) trên TEMPORARY = 'Y'",
        "index_category": "B-Tree Design Technique (Chỉ mục có điều kiện vị từ trên dữ liệu phân bố lệch)",
        "source": "Báo cáo V3: Chương 2.2, Chương 4.2 và Chương 5 | reports/PHASE4_UC2_FILTERED_PARTIAL.md",
        "problem_statement": """Trong các bảng nghiệp vụ thực tế, có những cột trạng thái bị phân bố lệch cực đoan: ví dụ trạng thái đơn hàng (99.8% đã hoàn thành, chỉ 0.2% đang xử lý) hoặc cờ đối tượng (TEMPORARY = 'N' chiếm 99.76%, còn TEMPORARY = 'Y' chỉ chiếm 0.24%).

Các màn hình dashboard ứng dụng liên tục truy vấn tập con đang hoạt động ('Y'), trong khi các tác vụ tổng hợp theo lô hiếm hoi mới quét dòng 'N'. Nếu xây dựng một chỉ mục đầy đủ (Full Index) trên toàn bộ bảng, chúng ta sẽ lãng phí hơn 99% không gian lưu trữ cho các bản ghi 'N' mà ứng dụng thời gian thực không bao giờ chạm tới.""",
        "why_fits": """Filtered Index (SQL Server) và Partial Index (MongoDB) cho phép gắn kèm một mệnh đề lọc lúc khai báo chỉ mục:
- SQL Server: WHERE TEMPORARY = N'Y'
- MongoDB: partialFilterExpression: {TEMPORARY: "Y"}

Nhờ đó, cây B-tree chỉ nạp duy nhất 2,405 dòng 'Y' (ở quy mô 1M) thay vì nạp toàn bộ 1,000,000 dòng. Index trở nên siêu nhỏ, vừa vặn hoàn toàn trong CPU L1/L2 cache, đọc cực ít trang và hoàn toàn không tốn công bảo trì khi thêm/sửa 997,595 dòng 'N' còn lại.""",
        "theoretical_tradeoff": """- Không thể phục vụ truy vấn ngoài tập: Nếu một câu truy vấn hỏi TEMPORARY = 'N', chỉ mục C hoàn toàn vô dụng vì không chứa dữ liệu của 'N', buộc hệ thống phải quét toàn bộ bảng.
- Giới hạn với câu lệnh dùng tham số (Parameterized Queries) trong SQL Server: Nếu viết WHERE TEMPORARY = @p, bộ tối ưu hóa phải tạo một kế hoạch thực thi dùng chung cho mọi giá trị của @p (kể cả khi @p = 'N'). Do đó, SQL Server buộc phải chọn Table Scan trừ khi câu truy vấn dùng hằng số hoặc có OPTION (RECOMPILE).""",
        "configs": {
            "A": {
                "name": "Baseline A (Heap / No Index)",
                "sql": "Bảng Heap không có index phụ. Quét toàn bảng (Table Scan).",
                "mongo": "Collection chỉ có {_id_: 1}. Dùng COLLSCAN."
            },
            "B": {
                "name": "Config B (Conventional Full Composite Index)",
                "sql": "CREATE NONCLUSTERED INDEX IX_UC2_B_Full ON Table(OBJECT_TYPE, OBJECT_ID) INCLUDE(TEMPORARY); (Chứa toàn bộ 1M dòng)",
                "mongo": "db.collection.createIndex({OBJECT_TYPE: 1, OBJECT_ID: 1, TEMPORARY: 1}); (Chứa toàn bộ 1M doc)"
            },
            "C": {
                "name": "Config C (Target Filtered / Partial Index)",
                "sql": "CREATE NONCLUSTERED INDEX IX_UC2_C_Filtered ON Table(OBJECT_TYPE, OBJECT_ID) INCLUDE(TEMPORARY) WHERE TEMPORARY = N'Y';",
                "mongo": "db.collection.createIndex({OBJECT_TYPE: 1, OBJECT_ID: 1, TEMPORARY: 1}, {partialFilterExpression: {TEMPORARY: 'Y'}});"
            }
        },
        "query_architecture_note": "📌 Lưu ý phương pháp luận: UC2 thiết kế 2 câu truy vấn đối xứng (Inside-Subset 'Y' và Outside-Subset 'N') cùng một bài kiểm tra tham số (@p) để chứng minh ưu thế vượt trội trên tập con và giới hạn hoàn toàn khi nằm ngoài vị từ lọc!",
        "queries": {
            "Y": {
                "code": "Y",
                "name": "Inside-Subset Query (Truy vấn tập con hiếm 'Y')",
                "purpose": "Kiểm tra hiệu năng khi truy vấn đúng vào tập con được chỉ mục lọc bảo vệ (TEMPORARY = 'Y'). Khớp 82 dòng (100K) / 615 dòng (1M).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Kiểm chứng tốc độ của Filtered Index trên tập dữ liệu mục tiêu.",
                "matched_rows": 615,
                "sql": "SELECT OBJECT_TYPE, OBJECT_ID, TEMPORARY\nFROM DEMO_BIG_TABLE_1000K\nWHERE TEMPORARY = N'Y'\n  AND OBJECT_TYPE = N'TABLE'\n  AND OBJECT_ID BETWEEN 1 AND 10000;",
                "mongo": "db.big_table_1000k.find({\n  TEMPORARY: 'Y',\n  OBJECT_TYPE: 'TABLE',\n  OBJECT_ID: {$gte: 1, $lte: 10000}\n}, {_id: 0, OBJECT_TYPE: 1, OBJECT_ID: 1, TEMPORARY: 1})",
                "expected": "Config C nhanh vượt trội cả A và B vì cây B-tree cực nhỏ (chỉ chứa 2,405 dòng thay vì 1M dòng).",
                "finding": "Hiệu năng ấn tượng: Tại 1M, SQL Server C hoàn thành trong 5.99 ms (nhanh gấp 15.4x so với A, 1.50x so với B), chỉ đọc 6 trang index (so với 81 trang của B và 28,032 trang của A). MongoDB C đạt 6.13 ms (nhanh gấp 395x so với A, 2.80x so với B), chỉ duyệt 616 keys (so với 1,670 keys của B)."
            },
            "N": {
                "code": "N",
                "name": "Outside-Subset Query (Truy vấn tập con ngoài phạm vi 'N')",
                "purpose": "Kiểm tra hành vi khi truy vấn rơi vào phần còn lại không được index (TEMPORARY = 'N'). Khớp 2,108 dòng (100K) / 15,810 dòng (1M).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Chứng minh hiện tượng fallback về toàn bảng khi dữ liệu không có trong index.",
                "matched_rows": 15810,
                "sql": "SELECT OBJECT_TYPE, OBJECT_ID, TEMPORARY\nFROM DEMO_BIG_TABLE_1000K\nWHERE TEMPORARY = N'N'\n  AND OBJECT_TYPE = N'TABLE'\n  AND OBJECT_ID BETWEEN 1 AND 10000;",
                "mongo": "db.big_table_1000k.find({\n  TEMPORARY: 'N',\n  OBJECT_TYPE: 'TABLE',\n  OBJECT_ID: {$gte: 1, $lte: 10000}\n}, {_id: 0, OBJECT_TYPE: 1, OBJECT_ID: 1, TEMPORARY: 1})",
                "expected": "Do C không có dòng 'N', cả hai DBMS bắt buộc phải từ chối C và quay về Table Scan / COLLSCAN.",
                "finding": "Fallback hoàn toàn về Scan: Cả hai DBMS phát hiện C không chứa bản ghi nào thỏa mãn, nên quay về quét toàn bộ 1 triệu bản ghi! SQL Server C mất 349.62 ms đọc 28,032 trang (chậm hơn B tới 0.84x); MongoDB C mất 2,438.73 ms quét 1M doc (chậm hơn B tới 0.03x vì B hoàn thành trong 69.45 ms)."
            }
        },
        "default_query": "Y",
        "mermaid_diagram": """flowchart LR
  BaseTable["Bảng gốc (1,000,000 dòng)"]
  BaseTable -->|997,595 dòng 'N' 99.76%| Ignored["Bỏ qua không index"]
  BaseTable -->|2,405 dòng 'Y' 0.24%| FilteredTree["Filtered B-Tree C (Siêu nhỏ: 0.13 MB)"]

  Q_Y["Query: WHERE TEMPORARY = 'Y'"] -->|Seek trực tiếp (6 trang)| FilteredTree
  Q_N["Query: WHERE TEMPORARY = 'N'"] -.->|Không có trong index C!| Fallback["Bắt buộc Table Scan (28,032 trang)"]
""",
        "plan_analysis": """1. Lý do C đánh bại B trên truy vấn 'Y': Cây B-tree C chỉ chứa 2,405 bản ghi, chiều cao cây thấp hơn và số trang lá ít hơn rất nhiều so với cây B chứa 1,000,000 bản ghi. Do đó, việc tìm kiếm dải khóa và đọc trang lá trong C tốn ít I/O hơn hẳn.
2. Thử nghiệm tham số @p (Parameterized Probe): Khi chạy thử trên SQL Server với câu lệnh DECLARE @p NVARCHAR(1) = 'Y'; SELECT ... WHERE TEMPORARY = @p, SQL Server ngay lập tức chọn Table Scan trên Config C! Lý do là bộ đệm kế hoạch (plan cache) không thể giả định @p sẽ luôn luôn là 'Y' trong các lần gọi tiếp theo.""",
        "tradeoffs_measured": """- Tiết kiệm dung lượng kinh ngạc: Tại quy mô 1M dòng, Index C giảm dung lượng từ 43.74 MB xuống 0.13 MB trên SQL Server (-99.71%) và từ 11.95 MB xuống 0.05 MB trên MongoDB (-99.57%).
- Thời gian tạo index siêu nhanh: Dựng chỉ mục C nhanh gấp 3.4x đến 9.7x so với Full Index B (179.3 ms vs 1,741.4 ms ở SQL; 2,947 ms vs 9,967 ms ở Mongo).
- Tốc độ ghi nhỏ lẻ: Thao tác chèn 20 dòng mới dạng 'N' (chiếm 99.8%) không phải cập nhật index C, giúp giảm thiểu overhead ghi.""",
        "verdict": "NÊN DÙNG Filtered / Partial Index khi ứng dụng liên tục truy vấn một tập con dữ liệu nhỏ, dự đoán được và có độ chọn lọc cực cao (như các đơn hàng chưa xử lý, người dùng active). TUYỆT ĐỐI KHÔNG DÙNG để thay thế hoàn toàn full index nếu người dùng vẫn cần tìm kiếm nhanh trên 99% các bản ghi còn lại ('N'), và trong SQL Server cần dùng hằng số hoặc OPTION (RECOMPILE)."
    },

    "uc3": {
        "title": "UC3 · Covering Index",
        "full_title": "UC3: Range Projections → Covering Index (INCLUDE vs. Compound Keys)",
        "scale": "100K và 1M bản ghi Catalog metadata",
        "workload_type": "Multi-Column Range Projections across Selectivity Tiers",
        "index_target": "Covering Index (SQL Server INCLUDE / MongoDB Compound Covered Projection)",
        "index_category": "B-Tree Design Technique (Lưu trữ cột phụ tải trực tiếp tại trang lá)",
        "source": "Báo cáo V3: Chương 2.3, Chương 4.3 và Chương 5 | reports/PHASE5_UC3_COVERING.md",
        "problem_statement": """Các ứng dụng nghiệp vụ thực tế không bao giờ chỉ lấy mỗi cột nằm trong mệnh đề WHERE; thông thường màn hình cần hiển thị thêm 4-5 cột mô tả khác (ví dụ: lấy ID, OWNER, OBJECT_NAME, OBJECT_TYPE khi người dùng tra cứu theo dải OBJECT_ID).

Nếu chỉ tạo một chỉ mục hẹp thông thường (Narrow Index) trên (OBJECT_ID), DBMS có thể dùng B-tree seek để tìm ra các con trỏ dòng, nhưng sau đó phải thực hiện hàng ngàn bước nhảy ngẫu nhiên quay về bảng dữ liệu gốc (gọi là RID Lookup trong SQL Server hoặc FETCH trong MongoDB) để bốc các cột còn lại. Khi số lượng dòng khớp tăng lên hàng trăm hoặc hàng ngàn, chi phí nhảy ngẫu nhiên này trở nên vô cùng đắt đỏ, thậm chí chậm hơn quét tuần tự toàn bảng.""",
        "why_fits": """Covering Index giải quyết triệt để vấn đề này bằng cách đưa toàn bộ các cột mà câu truy vấn cần trực tiếp vào chỉ mục:
- SQL Server (Mệnh đề INCLUDE): CREATE NONCLUSTERED INDEX ... ON Table(OBJECT_ID) INCLUDE (ID, OWNER, OBJECT_NAME, OBJECT_TYPE). Bốn cột phụ chỉ được lưu tại trang lá (Leaf pages), giữ cho các node nhánh (Branch nodes) nhỏ gọn để seek nhanh.
- MongoDB (Compound Covering Keys): Vì MongoDB không có cú pháp INCLUDE, toàn bộ 5 trường phải được khai báo trong index key: {OBJECT_ID: 1, ID: 1, OWNER: 1, OBJECT_NAME: 1, OBJECT_TYPE: 1} và câu query bắt buộc phải loại trừ _id ({_id: 0}).

Nhờ đó, DBMS trả lời câu truy vấn 100% từ các trang lá của chỉ mục mà KHÔNG cần chạm vào bảng dữ liệu gốc một lần nào (0 RID Lookup; totalDocsExamined = 0).""",
        "theoretical_tradeoff": """- Phình to kích thước chỉ mục nghiêm trọng: Việc nhân bản 4 cột dữ liệu rộng vào trong index khiến kích thước index phình to từ 6x đến hơn 10x so với index hẹp thông thường.
- Chi phí bảo trì khi cập nhật: Bất kỳ thao tác UPDATE nào thay đổi giá trị của các cột trong INCLUDE đều phải cập nhật lại cây chỉ mục, và tốc độ INSERT cũng giảm do mỗi lần ghi phải nạp thêm lượng dữ liệu payload lớn hơn.""",
        "configs": {
            "A": {
                "name": "Baseline A (Heap / No Index)",
                "sql": "Bảng Heap không có index phụ. Quét toàn bảng (Table Scan).",
                "mongo": "Collection chỉ có {_id_: 1}. Dùng COLLSCAN."
            },
            "B": {
                "name": "Config B (Conventional Narrow Index)",
                "sql": "CREATE NONCLUSTERED INDEX IX_UC3_B_Narrow ON Table(OBJECT_ID); (Chỉ đánh chỉ mục trên 1 cột lọc)",
                "mongo": "db.collection.createIndex({OBJECT_ID: 1}); (Chỉ đánh chỉ mục trên OBJECT_ID)"
            },
            "C": {
                "name": "Config C (Target Covering Index)",
                "sql": "CREATE NONCLUSTERED INDEX IX_UC3_C_Covering ON Table(OBJECT_ID) INCLUDE (ID, OWNER, OBJECT_NAME, OBJECT_TYPE);",
                "mongo": "db.collection.createIndex({OBJECT_ID: 1, ID: 1, OWNER: 1, OBJECT_NAME: 1, OBJECT_TYPE: 1}); (Query cần kèm {_id: 0})"
            }
        },
        "query_architecture_note": "📌 Lưu ý phương pháp luận: UC3 thiết kế 3 tầng độ chọn lọc riêng biệt (Point: 1 dòng, Small: dải hẹp, Medium: dải trung bình) để tìm ra 'điểm bùng nổ' (tipping point) nơi Covering Index thực sự phát huy tác dụng so với Narrow Index!",
        "queries": {
            "POINT": {
                "code": "POINT",
                "name": "Point Lookup (Truy vấn điểm 1 dòng)",
                "purpose": "Kiểm tra xem khi chỉ tìm đúng 1 dòng (OBJECT_ID = 16 AND ID = 1), Covering Index có nhanh hơn Narrow Index rõ rệt hay không.",
                "is_shared": "Truy vấn RIÊNG BIỆT: Đo lường ở độ chọn lọc cao nhất (1 dòng).",
                "matched_rows": 1,
                "sql": "SELECT ID, OWNER, OBJECT_NAME, OBJECT_TYPE\nFROM DEMO_BIG_TABLE_100K\nWHERE OBJECT_ID = 16 AND ID = 1;",
                "mongo": "db.big_table_100k.find(\n  {OBJECT_ID: 16, ID: 1},\n  {_id: 0, ID: 1, OWNER: 1, OBJECT_NAME: 1, OBJECT_TYPE: 1}\n)",
                "expected": "Cả B và C đều cực nhanh (<3.5 ms). Covering C không mang lại lợi ích rõ rệt trên truy vấn điểm vì 1 lần lookup ngẫu nhiên tốn rất ít thời gian.",
                "finding": "Không có sự khác biệt đáng kể: Ở SQL Server, cả B và C đều hoàn thành trong dưới 1 ms (ghi nhận 0.00 ms trên timer batch). Ở MongoDB 100K, B đạt 2.68 ms còn C đạt 2.59 ms (chênh lệch không đáng kể). Việc phủ index ở đây hoàn toàn lãng phí tài nguyên."
            },
            "SMALL": {
                "code": "SMALL",
                "name": "Small Range (Truy vấn dải nhỏ 60 - 98 dòng)",
                "purpose": "Khảo sát dải hẹp: OBJECT_ID BETWEEN 1 AND 50 (100K, 98 dòng) hoặc BETWEEN 1 AND 5 (1M, 60 dòng).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Đo lường khi số dòng khớp từ vài chục đến dưới 100.",
                "matched_rows": 60,
                "sql": "SELECT ID, OWNER, OBJECT_NAME, OBJECT_TYPE\nFROM DEMO_BIG_TABLE_1000K\nWHERE OBJECT_ID BETWEEN 1 AND 5;",
                "mongo": "db.big_table_1000k.find(\n  {OBJECT_ID: {$gte: 1, $lte: 5}},\n  {_id: 0, ID: 1, OWNER: 1, OBJECT_NAME: 1, OBJECT_TYPE: 1}\n)",
                "expected": "Do số lượng dòng ít và dữ liệu nằm sẵn trong buffer pool, chi phí lookup của B vẫn rất thấp. C có thể ngang ngửa hoặc thậm chí chậm hơn B do khóa compound rộng.",
                "finding": "Hiện tượng thực nghiệm thú vị: Tại MongoDB 100K (98 doc), C (4.40 ms) thực tế chậm hơn B (2.83 ms) vì việc giải mã khóa compound 5 trường chứa nhiều chuỗi ký tự tốn CPU hơn việc bốc 98 doc từ RAM cache! Tại 1M (60 doc), B và C hòa nhau ở mức 3.5 ms."
            },
            "MEDIUM": {
                "code": "MEDIUM",
                "name": "Medium Range (Truy vấn dải trung bình 1,694 - 2,775 dòng)",
                "purpose": "Khảo sát điểm bùng nổ (tipping point): BETWEEN 1 AND 1000 (100K, 1,694 dòng) hoặc BETWEEN 1 AND 200 (1M, 2,775 dòng).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Nơi loại bỏ RID Lookup / FETCH phát huy giá trị lớn nhất.",
                "matched_rows": 2775,
                "sql": "SELECT ID, OWNER, OBJECT_NAME, OBJECT_TYPE\nFROM DEMO_BIG_TABLE_1000K\nWHERE OBJECT_ID BETWEEN 1 AND 200;",
                "mongo": "db.big_table_1000k.find(\n  {OBJECT_ID: {$gte: 1, $lte: 200}},\n  {_id: 0, ID: 1, OWNER: 1, OBJECT_NAME: 1, OBJECT_TYPE: 1}\n)",
                "expected": "Narrow B sụp đổ hiệu năng do hàng ngàn lần lookup ngẫu nhiên. Covering C duy trì tốc độ đọc vượt trội vì chỉ quét tuần tự các trang lá index.",
                "finding": "Điểm bùng nổ của Covering Index: Tại 100K, SQL Server B thấy 1,694 lần RID Lookup quá đắt nên bỏ cuộc, quay về Table Scan 2,730 trang (52.22 ms). Trong khi đó Covering C chỉ đọc đúng 29 trang lá (22.63 ms, nhanh gấp 2.31x). Tại 1M (2,775 dòng), SQL Server giảm đọc từ 2,785 trang xuống 49 trang (nhanh hơn 1.54x), còn MongoDB triệt tiêu hoàn toàn việc đọc bảng gốc (totalDocsExamined = 0, đạt 20.12 ms so với 2579.4 ms của A — nhanh hơn 128.2x)."
            }
        },
        "default_query": "MEDIUM",
        "mermaid_diagram": """flowchart LR
  subgraph Narrow_B ["Narrow Index B (Chỉ có OBJECT_ID)"]
    LeafB["Trang lá: [OBJECT_ID | Row Pointer]"]
    LeafB -->|1,694 lần nhảy ngẫu nhiên đắt đỏ| TableHeap["Bảng gốc (RID Lookup / FETCH)"]
    TableHeap --> ResultB["Trả kết quả 4 cột"]
  end
  subgraph Covering_C ["Covering Index C (INCLUDE / Compound)"]
    LeafC["Trang lá: [OBJECT_ID | ID, OWNER, NAME, TYPE]"]
    LeafC -->|Đọc thẳng từ trang lá (0 base lookups)| ResultC["Trả kết quả 4 cột"]
  end
""",
        "plan_analysis": """Trong toàn bộ 12 actual plans của Config C (6 ở SQL Server, 6 ở MongoDB), các thao tác nhảy về bảng dữ liệu gốc bị triệt tiêu 100%:
- SQL Server: Plan chỉ xuất hiện toán tử Index Seek thuần túy, hoàn toàn biến mất toán tử RID Lookup.
- MongoDB: Plan xuất hiện stage PROJECTION_COVERED và chỉ số totalDocsExamined = 0.
Tại 100K Medium, việc optimizer SQL Server từ chối Narrow Index B để chạy Table Scan là một minh chứng hoàn hảo trong sách giáo khoa về ngưỡng chi phí ngẫu nhiên vs tuần tự.""",
        "tradeoffs_measured": """- Phình to kích thước cực lớn: Việc nạp thêm 4 cột payload khiến dung lượng index ở 1M tăng từ 21.46 MB lên 127.42 MB trong SQL Server (gấp 5.94x) và từ 6.39 MB lên 66.85 MB trong MongoDB (gấp 10.47x)!
- Tác động tới tốc độ ghi: Tại 1M dòng SQL Server, thông lượng batch INSERT giảm 14.7% (từ 6,129 dòng/s ở A xuống 5,230 dòng/s ở C).""",
        "verdict": "CHỈ NÊN DÙNG Covering Index cho các truy vấn khoảng (range queries) có tần suất gọi cao và trả về từ hàng trăm đến hàng ngàn dòng, nơi việc loại bỏ RID Lookup/FETCH ngẫu nhiên thực sự đem lại bước nhảy vọt về I/O. TUYỆT ĐỐI KHÔNG mở rộng index bằng các cột phụ cho các truy vấn điểm hoặc dải siêu nhỏ, vì index hẹp đã rất nhanh (<3.5 ms) mà không làm tốn thêm 6x–10x dung lượng đĩa và RAM."
    },

    "uc4": {
        "title": "UC4 · Full-Text & Text Search",
        "full_title": "UC4: Natural-Language Search over Prose → Full-Text and Text Indexes",
        "scale": "10,000 bài báo tiếng Anh (uc4_seed_10k)",
        "workload_type": "Prose Search / Inverted Linguistic Token Catalog",
        "index_target": "Full-Text Index (SQL Server) / Text Index (MongoDB)",
        "index_category": "Alternative Physical Structure (Chỉ mục đảo phân rã token, loại stop-words và stemming)",
        "source": "Báo cáo V3: Chương 2.4, Chương 4.4 và Chương 5 | reports/UC4_FULL_TEXT_BENCHMARK.md",
        "problem_statement": """Cây B-Tree thông thường chỉ sắp xếp chuỗi bắt đầu từ ký tự đầu tiên. Khi người dùng cần tìm kiếm một từ khóa hoặc cụm từ nằm sâu bên trong đoạn văn bản dài (như bài báo, phần mô tả sản phẩm hay bài đánh giá), B-Tree thông thường hoàn toàn vô dụng.

Nếu không có chỉ mục chuyên dụng, hệ thống buộc phải quét tuần tự từng ký tự của toàn bộ 10,000 bài báo bằng toán tử LIKE '%term%' (trong SQL) hoặc biểu thức chính quy $regex (trong MongoDB), khiến mỗi câu truy vấn tiêu tốn từ hàng trăm mili-giây đến vài giây CPU.""",
        "why_fits": """Full-Text Index (SQL Server) và Text Index (MongoDB) sử dụng cấu trúc Chỉ mục đảo (Inverted Index):
1. Bộ tách từ (Word Breaker): Tách văn bản thành các từ riêng lẻ dựa trên ranh giới ngôn ngữ.
2. Bộ lọc Stop-words: Loại bỏ các từ quá phổ biến nhưng vô nghĩa (như 'the', 'is', 'and').
3. Bộ phân tích gốc từ (Stemmer): Đưa các từ biến thể về dạng gốc (ví dụ: 'elections', 'elected' → 'elect').
4. Danh sách Posting List: Lưu trữ danh sách DOC_ID chứa mỗi token.

Khi tìm kiếm một từ, DBMS chỉ cần tra cứu danh sách posting list tương ứng trong vài mili-giây thay vì đọc hàng triệu ký tự văn bản.""",
        "theoretical_tradeoff": """- Khác biệt về mặt ngữ nghĩa (Semantic Difference): LIKE '%term%' là phép so khớp chuỗi con ký tự thuần túy (substring match), nó sẽ khớp cả các từ ghép như 're-election'. Trong khi đó, Full-Text tìm kiếm theo từ ngôn ngữ hoàn chỉnh (linguistic token match). Do đó, baseline và target index KHÔNG phải lúc nào cũng trả về cùng một tập kết quả ID!
- Đánh đổi kiến trúc ghi: Bất đồng bộ (Async) vs Đồng bộ (Sync):
  * SQL Server cập nhật full-text catalog trong background (CHANGE_TRACKING = AUTO), giúp tốc độ ghi không bị nghẽn nhưng dữ liệu mới ghi sẽ bị trễ vài giây mới tìm thấy được (Freshness Lag).
  * MongoDB cập nhật text index đồng bộ (Synchronous) ngay trong transaction ghi, giúp tìm thấy dữ liệu ngay tức thì nhưng làm sụt giảm nghiêm trọng thông lượng INSERT.""",
        "configs": {
            "A": {
                "name": "Baseline A (Substring / Regex Scan)",
                "sql": "Chỉ có khóa chính (DOC_ID). Truy vấn dùng WHERE BODY LIKE N'%term%'.",
                "mongo": "Chỉ có {_id_: 1, DOC_ID: 1}. Truy vấn dùng {BODY: {$regex: 'term', $options: 'i'}}."
            },
            "C": {
                "name": "Config C (Target Inverted Full-Text / Text Index)",
                "sql": "FULLTEXT CATALOG + FULLTEXT INDEX ON Table(BODY LANGUAGE 1033) WITH CHANGE_TRACKING = AUTO; Truy vấn dùng CONTAINS(BODY, '\"term\"', LANGUAGE 1033).",
                "mongo": "db.collection.createIndex({BODY: 'text'}, {default_language: 'english'}); Truy vấn dùng {$text: {$search: 'term'}}."
            }
        },
        "query_architecture_note": "📌 Lưu ý phương pháp luận: UC4 thiết kế 6 truy vấn gồm 3 từ đơn (Single Keywords) và 3 cụm từ (Exact Phrases) có độ chọn lọc khác nhau. Đặc biệt, ta phải kiểm tra tính tương đương của tập DOC_ID (Same ID Set) trước khi tính toán bất kỳ tỉ lệ tăng tốc (Speedup) nào!",
        "queries": {
            "K_HIGH": {
                "code": "K_HIGH",
                "name": "Single Keyword: election (Tần suất cao)",
                "purpose": "Khảo sát từ đơn phổ biến (khớp hàng ngàn bài báo) để xem thuật toán tách từ và gốc từ hoạt động thế nào.",
                "is_shared": "Truy vấn RIÊNG BIỆT: Minh họa rõ rệt nhất sự khác biệt ngữ nghĩa giữa LIKE và Full-text.",
                "matched_rows": 2577,
                "sql": "SELECT DOC_ID FROM DEMO_UC4_NEWS_10K WHERE CONTAINS(BODY, '\"election\"', LANGUAGE 1033);",
                "mongo": "db.uc4_news_10k.find({$text: {$search: 'election'}}, {_id: 0, DOC_ID: 1})",
                "expected": "Do thuật toán stemming, kết quả của C sẽ khác với kết quả của A (không cùng tập ID).",
                "finding": "Khác tập DOC_ID: Trong SQL Server, A trả 2,577 dòng còn C trả 2,311 dòng (266 dòng của A là chuỗi con như 're-election' mà C không tính). Trong MongoDB, Snowball stemmer đưa 'election' về 'elect', nên C trả tới 3,083 doc (nhiều hơn A 538 doc chứa 'elect', 'elected'). Do khác tập ID, ta không gọi sự giảm latency từ 3.29s xuống 21ms (SQL) là cùng kết quả speedup!"
            },
            "K_MED": {
                "code": "K_MED",
                "name": "Single Keyword: climate (Tần suất trung bình)",
                "purpose": "Khảo sát từ đơn có tần suất trung bình (vài trăm bài báo).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Đo lường tốc độ tìm kiếm từ đơn tiêu chuẩn.",
                "matched_rows": 326,
                "sql": "SELECT DOC_ID FROM DEMO_UC4_NEWS_10K WHERE CONTAINS(BODY, '\"climate\"', LANGUAGE 1033);",
                "mongo": "db.uc4_news_10k.find({$text: {$search: 'climate'}}, {_id: 0, DOC_ID: 1})",
                "expected": "Tìm kiếm nhanh gấp hàng chục đến hàng trăm lần so với quét chuỗi.",
                "finding": "MongoDB cùng tập 326 ID (Speedup 46.82x): MongoDB A mất 299.96 ms quét regex, trong khi C chỉ mất 6.41 ms tra cứu posting list (duyệt đúng 326 keys). SQL Server C giảm từ 3,983.5 ms xuống 17.40 ms (nhưng khác 2 ID do từ ghép trong tiếng Anh)."
            },
            "K_LOW": {
                "code": "K_LOW",
                "name": "Single Keyword: bitcoin (Tần suất thấp / Hiếm)",
                "purpose": "Khảo sát từ đơn hiếm (chỉ xuất hiện trong vài bài báo).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Đo lường hiệu quả tối đa trên từ khóa hiếm.",
                "matched_rows": 7,
                "sql": "SELECT DOC_ID FROM DEMO_UC4_NEWS_10K WHERE CONTAINS(BODY, '\"bitcoin\"', LANGUAGE 1033);",
                "mongo": "db.uc4_news_10k.find({$text: {$search: 'bitcoin'}}, {_id: 0, DOC_ID: 1})",
                "expected": "Tốc độ vượt trội vì posting list chỉ chứa 7 document.",
                "finding": "MongoDB cùng tập 7 ID (Speedup 107.75x): MongoDB A mất 197.50 ms, C chỉ mất 1.83 ms duyệt đúng 7 keys! SQL Server C giảm từ 3,987.0 ms xuống 14.86 ms (khác 1 ID ở A do nằm trong đường link URL không có khoảng trắng)."
            },
            "P_HIGH": {
                "code": "P_HIGH",
                "name": "Exact Phrase: \"white house\" (Cụm từ phổ biến)",
                "purpose": "Kiểm tra khả năng tìm kiếm cụm từ chính xác (Exact Phrase Match) có tần suất cao (1,851 bài).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Khảo sát chi phí phối hợp nhiều posting list cho cụm từ.",
                "matched_rows": 1851,
                "sql": "SELECT DOC_ID FROM DEMO_UC4_NEWS_10K WHERE CONTAINS(BODY, '\"white house\"', LANGUAGE 1033);",
                "mongo": "db.uc4_news_10k.find({$text: {$search: '\"white house\"'}}, {_id: 0, DOC_ID: 1})",
                "expected": "Tìm kiếm cụm từ tốn thời gian hơn từ đơn vì phải kiểm tra vị trí đứng cạnh nhau của các từ.",
                "finding": "MongoDB cùng tập 1,851 ID (Speedup 3.30x): Do text index của MongoDB chỉ lưu từng token đơn lẻ chứ không lưu cụm từ, MongoDB phải quét posting list của cả 'white' và 'house' (4,297 keys) rồi kiểm tra thứ tự từ, hoàn thành trong 42.58 ms (so với 140.53 ms của regex). SQL Server C hoàn thành trong 22.55 ms (so với 3,439.6 ms của LIKE)."
            },
            "P_MED": {
                "code": "P_MED",
                "name": "Exact Phrase: \"climate change\" (Cụm từ trung bình)",
                "purpose": "Kiểm tra tìm kiếm cụm từ trung bình (214 bài báo).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Đo lường cụm từ 2 token phổ biến.",
                "matched_rows": 214,
                "sql": "SELECT DOC_ID FROM DEMO_UC4_NEWS_10K WHERE CONTAINS(BODY, '\"climate change\"', LANGUAGE 1033);",
                "mongo": "db.uc4_news_10k.find({$text: {$search: '\"climate change\"'}}, {_id: 0, DOC_ID: 1})",
                "expected": "Nhanh hơn đáng kể so với quét chuỗi con.",
                "finding": "MongoDB cùng tập 214 ID (Speedup 5.50x): MongoDB A mất 288.39 ms, C mất 52.39 ms (quét 3,522 keys và nạp 2,922 docs ứng viên trong TEXT_MATCH). SQL Server C hoàn thành trong 16.63 ms (so với 4,042.0 ms của LIKE)."
            },
            "P_LOW": {
                "code": "P_LOW",
                "name": "Exact Phrase: \"stock market\" (Cụm từ ít)",
                "purpose": "Kiểm tra tìm kiếm cụm từ hiếm (45 bài báo).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Đo lường cụm từ có độ chọn lọc cao.",
                "matched_rows": 45,
                "sql": "SELECT DOC_ID FROM DEMO_UC4_NEWS_10K WHERE CONTAINS(BODY, '\"stock market\"', LANGUAGE 1033);",
                "mongo": "db.uc4_news_10k.find({$text: {$search: '\"stock market\"'}}, {_id: 0, DOC_ID: 1})",
                "expected": "Cắt giảm thời gian xuống mức mili-giây.",
                "finding": "MongoDB cùng tập 45 ID (Speedup 16.42x): MongoDB A mất 419.56 ms, C chỉ mất 25.55 ms (quét 1,197 keys và 1,105 docs). SQL Server C giảm từ 4,060.1 ms xuống 14.13 ms."
            }
        },
        "default_query": "K_MED",
        "mermaid_diagram": """flowchart LR
  subgraph Inverted_Index ["Cơ chế Chỉ mục đảo (Inverted Full-Text Index)"]
    Article["Văn bản bài báo"] --> WordBreaker["Word Breaker (Tách từ)"]
    WordBreaker --> Stopwords["Lọc Stopwords (the, is, and)"]
    Stopwords --> Stemmer["Stemmer (elections → elect)"]
    Stemmer --> PostingList["Posting Lists:
'climate' ↦ [Doc 12, Doc 89, ...]
'bitcoin' ↦ [Doc 412, Doc 1809, ...]"]
  end
  Q["CONTAINS / $text query"] -->|Tra cứu trực tiếp posting list| PostingList
""",
        "plan_analysis": """1. Vì sao SQL Server giảm từ 4 giây xuống ~15-20 ms: LIKE N'%term%' buộc SQL Server phải duyệt qua toàn bộ 7,960 trang dữ liệu (khoảng 63 MB) và so khớp từng ký tự trong chuỗi NVARCHAR(MAX). Ngược lại, CONTAINS sử dụng toán tử FulltextMatch đọc trực tiếp từ catalog và chỉ nạp đúng 69 trang dữ liệu gốc.
2. Vì sao Phrase Query trong MongoDB chậm hơn Single Word: MongoDB text index lưu trữ ở cấp độ từ đơn. Khi tìm cụm từ 'climate change', MongoDB phải dùng stage TEXT_MATCH bốc toàn bộ các tài liệu chứa cả hai từ 'climate' và 'change' (2,922 docs) lên bộ nhớ rồi kiểm tra khoảng cách vị trí giữa hai từ, khiến latency cao hơn từ đơn.""",
        "tradeoffs_measured": """ĐÂY LÀ SỰ ĐÁNH ĐỔI KIẾN TRÚC RÕ RỆT NHẤT TOÀN BỘ NGHIÊN CỨU:
- SQL Server (Kiến trúc Bất đồng bộ - Asynchronous):
  * DDL trả về ngay lập tức (63 ms), sau đó tiến trình nền mất 15,203 ms để nạp catalog.
  * Tốc độ UPDATE không bị ảnh hưởng (3.00 ms vs 2.99 ms) và INSERT chỉ giảm 26.5% (4,574 → 3,362 dòng/s).
  * NHƯNG phải trả giá bằng độ trễ dữ liệu: Một bài viết vừa được cập nhật phải mất tới 5,795.4 ms (5.80 giây, tương đương 93 lần poll) mới tìm thấy được qua CONTAINS!
- MongoDB (Kiến trúc Đồng bộ - Synchronous):
  * Dữ liệu mới ghi tìm thấy ngay lập tức sau 21.3 ms (ngay lần poll đầu tiên).
  * NHƯNG thông lượng INSERT bị SỤP ĐỔ TỚI 95.3% (từ 2,538 dòng/s xuống chỉ còn 119 dòng/s, p95 batch nhảy lên 704.9 ms) và độ trễ UPDATE tăng gấp 3 lần (từ 38.71 ms lên 115.47 ms) do phải phân tích token đồng bộ trong mỗi lần ghi!""",
        "verdict": "NÊN DÙNG Full-Text / Text Index cho các bài toán tìm kiếm từ và cụm từ ngôn ngữ tự nhiên trên văn bản dài nơi các phép quét chuỗi LIKE mất hàng giây. TUYỆT ĐỐI TRÁNH DÙNG khi yêu cầu bắt buộc phải so khớp chính xác từng ký tự con tùy ý (như mã vạch, URL, chuỗi regex phức tạp), và phải cân nhắc giữa độ trễ hiển thị 5.8 giây của SQL Server hoặc hình phạt sụt giảm 95% thông lượng ghi của MongoDB."
    },

    "uc5": {
        "title": "UC5 · Clustered Columnstore Index",
        "full_title": "UC5: Analytical Aggregation → Clustered Columnstore Index (SQL Server)",
        "scale": "1,000,000 bản ghi Catalog metadata (Chỉ thực hiện trên SQL Server 2025)",
        "workload_type": "Analytical GROUP BY Aggregation vs. Unindexed Single-Row Scan",
        "index_target": "Clustered Columnstore Index (CCI)",
        "index_category": "Alternative Physical Structure (Tổ chức lưu trữ vật lý dạng cột nén theo rowgroup)",
        "source": "Báo cáo V3: Chương 2.5, Chương 4.5 và Chương 5 | reports/PHASE6_UC5_COLUMNSTORE.md",
        "problem_statement": """Trong các kho dữ liệu (Data Warehouse) hoặc hệ thống báo cáo phân tích (OLAP), các câu truy vấn thường quét qua hàng triệu bản ghi để tính toán tổng hợp (GROUP BY, SUM, COUNT) trên chỉ 1 hoặc 2 cột.

Trong bảng lưu trữ dạng hàng truyền thống (Rowstore Heap), toàn bộ 14 cột của mỗi dòng được xếp nằm cạnh nhau trên các trang dữ liệu 8 KB. Để tổng hợp dữ liệu của 2 cột OBJECT_TYPE và OBJECT_ID trên 1,000,000 dòng, SQL Server buộc phải đọc toàn bộ 219 MB dữ liệu (28,032 trang) vào bộ đệm, gây lãng phí băng thông đĩa và RAM khủng khiếp cho 12 cột không được dùng đến.""",
        "why_fits": """Clustered Columnstore Index (CCI) thay đổi hoàn toàn cách tổ chức vật lý của bảng:
1. Chia bảng thành các nhóm dòng (Rowgroups) với tối đa 1,048,576 dòng mỗi nhóm.
2. Trong mỗi rowgroup, dữ liệu được tách riêng theo từng cột thành các Column Segments độc lập.
3. Vì các giá trị trong một cột lặp lại rất nhiều lần, dữ liệu được nén sâu bằng từ điển (Dictionary) và Run-length Encoding.
4. Chế độ xử lý theo lô (Batch Mode): CPU xử lý một mảng khoảng 900 dòng cùng lúc bằng các lệnh vector hóa thay vì xử lý từng dòng đơn lẻ (Row Mode).

Khi chạy truy vấn GROUP BY, SQL Server chỉ đọc đúng 2 column segment cần thiết (bỏ qua 12 cột còn lại) và tính toán trực tiếp trên dữ liệu nén trong Batch Mode.""",
        "theoretical_tradeoff": """- Khó khăn trong việc ghi nhỏ lẻ (Trickle Writes): Do các column segment đã nén không thể sửa đổi tại chỗ, các thao tác chèn nhỏ (<102,400 dòng) buộc phải ghi vào một cây B-tree dạng hàng tạm thời gọi là OPEN Delta Rowgroup.
- Cập nhật dòng: Thao tác UPDATE không sửa trực tiếp mà phải đánh dấu dòng cũ vào Delete Bitmap và chèn phiên bản dòng mới vào Delta Store, làm tăng chi phí quản lý và phân mảnh dữ liệu.""",
        "configs": {
            "B": {
                "name": "Config B (Rowstore Heap — 14 Columns)",
                "sql": "Bảng lưu trữ dạng hàng truyền thống 14 cột, không có clustered index (219.00 MB, 28,032 trang)."
            },
            "C": {
                "name": "Config C (Clustered Columnstore Index — CCI)",
                "sql": "CREATE CLUSTERED COLUMNSTORE INDEX CCI_DEMO_BIG_TABLE_1000K ON Table; (9.46 MB, 1,211 trang)."
            }
        },
        "query_architecture_note": "📌 Lưu ý phương pháp luận: UC5 là bài toán nghiên cứu cấu trúc vật lý trên SQL Server 2025 gồm 2 câu truy vấn: AGG (tổng hợp phân tích) và POINT (quét tìm dòng khi KHÔNG CÓ B-tree index trên ID để làm rõ sắc thái giữa scan nén và seek)!",
        "queries": {
            "AGG": {
                "code": "AGG",
                "name": "Analytical Aggregation (GROUP BY 1 triệu dòng)",
                "purpose": "Kiểm tra năng lực loại bỏ cột (Column Elimination) và tốc độ xử lý Batch Mode trên 1,000,000 bản ghi ra 35 nhóm.",
                "is_shared": "Truy vấn RIÊNG BIỆT: Bài toán phân tích tổng hợp đặc trưng của Columnstore.",
                "matched_rows": 35,
                "sql": "SELECT OBJECT_TYPE, COUNT_BIG(*) AS n, SUM(COALESCE(OBJECT_ID, 0)) AS s\nFROM DEMO_BIG_TABLE_1000K\nGROUP BY OBJECT_TYPE;",
                "mongo": "N/A (Nghiên cứu cấu trúc vật lý chuyên sâu trên SQL Server)",
                "expected": "CCI C chỉ đọc 2 cột cần thiết, xử lý Batch Mode nhanh gấp 2-4 lần Rowstore Heap B.",
                "finding": "Nhanh gấp 2.90 lần: Rowstore Heap B mất 123.20 ms và phải đọc toàn bộ 28,032 trang (219 MB) ở Row Mode. Clustered Columnstore C chỉ mất 42.44 ms và chỉ đọc đúng 1,105 trang LOB (chứa 2 column segment nén) ở chế độ Batch Mode!"
            },
            "POINT": {
                "code": "POINT",
                "name": "Unindexed Point Scan (Quét tìm dòng ID = 1 không có B-tree)",
                "purpose": "Khảo sát hành vi của Columnstore khi tìm kiếm 1 dòng duy nhất trên bảng KHÔNG CÓ B-tree index.",
                "is_shared": "Truy vấn RIÊNG BIỆT: Làm rõ sự khác biệt giữa quét segment nén và B-tree Seek thực sự.",
                "matched_rows": 1,
                "sql": "SELECT ID, OWNER, OBJECT_NAME, OBJECT_TYPE\nFROM DEMO_BIG_TABLE_1000K\nWHERE ID = 1;",
                "mongo": "N/A (Nghiên cứu cấu trúc vật lý chuyên sâu trên SQL Server)",
                "expected": "Do cả B và C đều không có index trên ID, cả hai đều phải quét toàn bảng. Tuy nhiên quét dữ liệu nén trong C sẽ nhanh hơn Heap B.",
                "finding": "Sắc thái quan trọng về phương pháp luận: Columnstore C hoàn thành trong 3.63 ms (đọc 776 trang LOB), nhanh gấp 24.49 lần so với Heap B (88.81 ms, đọc 28,032 trang). ĐÂY VẪN LÀ PHÉP QUÉT TOÀN BỘ (Scan), KHÔNG PHẢI B-tree Seek! Nếu so với một B-tree index thực sự trên ID (hoàn thành trong <1 ms và chỉ đọc 2-3 trang như ở UC3), quét Columnstore vẫn tốn tài nguyên CPU hơn nhiều."
            }
        },
        "default_query": "AGG",
        "mermaid_diagram": """flowchart LR
  subgraph Rowstore_B ["Rowstore Heap B (219.00 MB)"]
    R1["Trang 1: [Dòng 1: Cột 1..14][Dòng 2: Cột 1..14]..."]
    R2["Trang 28,032: Toàn bộ 14 cột đều phải nạp vào RAM"]
    R1 --> R2 --> AggB["Quét 28,032 trang ở Row Mode (123.2 ms)"]
  end
  subgraph Columnstore_C ["Clustered Columnstore C (9.46 MB — Nén 23.15 : 1)"]
    C_Type["Segment Cột OBJECT_TYPE (Nén từ điển)"]
    C_ID["Segment Cột OBJECT_ID (Nén run-length)"]
    C_Skip["12 Segment cột khác: HOÀN TOÀN BỎ QUA"]
    C_Type & C_ID --> AggC["Đọc 1,105 trang LOB ở Batch Mode (42.4 ms)"]
  end
""",
        "plan_analysis": """1. Loại bỏ cột và chế độ Batch Mode: Actual execution plan của C cho thấy toán tử Columnstore Index Scan đọc dữ liệu ở ActualExecutionMode = 'Batch'. Nhờ vector hóa, CPU thực hiện tổng hợp 1M dòng chỉ trong 42.44 ms.
2. Cơ chế Delete Bitmap và Delta Rowgroup: Sau khi thực hiện 10 batch ghi (mỗi batch 20 dòng INSERT và 20 dòng UPDATE), truy vấn sys.dm_db_column_store_row_group_physical_stats cho thấy: Rowgroup 0 (COMPRESSED) vẫn giữ 1,000,000 dòng nhưng có đúng 200 dòng bị đánh dấu xóa trong Delete Bitmap; một Rowgroup 1 mới (trạng thái OPEN) được tạo ra dạng delta store chứa đúng 400 dòng chưa nén.""",
        "tradeoffs_measured": """- Tỉ lệ nén vật lý phi thường: Nén bảng 1,000,000 dòng từ 219.00 MB xuống còn 9.46 MB — ĐẠT TỈ LỆ NÉN 23.15 : 1 (tiết kiệm tới 95.68% không gian đĩa!).
- Thời gian build lâu: Mất 22,294.9 ms (22.29 giây) để nén toàn bộ 1 triệu dòng vào các column segment.
- Tốc độ chèn dữ liệu nhỏ lẻ bị giảm một nửa: Do các dòng chèn nhỏ phải qua Delta Store, thông lượng batch INSERT giảm 49.9% (từ 13,265 dòng/s ở Heap xuống 6,642 dòng/s ở CCI).""",
        "verdict": "NÊN DÙNG Clustered Columnstore Index cho các kho dữ liệu, bảng tổng hợp báo cáo OLAP hoặc bảng lưu trữ lịch sử có dung lượng lớn, nơi việc tiết kiệm 95% đĩa và tăng tốc GROUP BY bằng Batch Mode là ưu tiên số 1. TRÁNH DÙNG cho các bảng giao dịch OLTP có tần suất ghi/cập nhật nhỏ lẻ liên tục, và luôn tạo kèm Nonclustered B-tree nếu cần tra cứu điểm dưới 1 mili-giây."
    },

    "uc6": {
        "title": "UC6 · Multikey vs. Normalized Child Index",
        "full_title": "UC6: Multi-Tag Membership → Multikey vs. Normalized Child Index",
        "scale": "10,000 Parent / 30,471 Tag memberships (Trung bình 3.05 tag/parent)",
        "workload_type": "Multi-Valued Categorical Tag Membership Queries (Single Tag & Conjunctive Tags)",
        "index_target": "MongoDB Multikey Index ({tags: 1}) vs. SQL Server Inverted Secondary Child Index (TAG, PARENT_ID)",
        "index_category": "B-Tree Design Technique (Đánh chỉ mục mảng đa trị trong NoSQL vs. Bảng con chuẩn hóa trong RDBMS)",
        "source": "Báo cáo V3: Chương 2.6, Chương 4.6 và Chương 5 | reports/PHASE7_UC6_MULTIKEY.md",
        "problem_statement": """Các ứng dụng hiện đại thường xuyên gắn nhiều nhãn phân loại (tags) vào một đối tượng (ví dụ: một đối tượng trong catalog có thể mang đồng thời các tag như owner:SYS, type:TABLE, temporary:Y). Hệ thống cần hỗ trợ truy vấn tìm các đối tượng chứa một tag duy nhất hoặc kết hợp đồng thời cả hai tag (tag1 AND tag2).

Cơ sở dữ liệu tài liệu (MongoDB) và quan hệ (SQL Server) mô hình hóa bài toán này hoàn toàn khác nhau:
- MongoDB nhúng trực tiếp mảng chuỗi tags: ['owner:SYS', 'type:TABLE', 'temporary:Y'] vào document của cha.
- SQL Server tuân thủ chuẩn 1NF bằng cách tách thành bảng con UC6_Tag(PARENT_ID, TAG) với khóa chính là (PARENT_ID, TAG).""",
        "why_fits": """Để hỗ trợ truy vấn theo tag mà không phải quét toàn bộ bảng:
- MongoDB (Multikey Index {tags: 1}): Khi tạo index trên một trường mảng, MongoDB tự động sinh một B-tree index entry cho TỪNG PHẦN TỬ RIÊNG BIỆT trong mảng của document, tất cả đều trỏ về cùng document ID.
- SQL Server (Normalized Secondary Child Index): Vì khóa chính của bảng con là (PARENT_ID, TAG) có PARENT_ID đứng đầu, việc tìm theo TAG vẫn phải quét toàn bộ bảng con. Do đó, ta tạo thêm một secondary index đảo ngược thứ tự khóa: (TAG, PARENT_ID).

Cả hai giải pháp đều biến việc quét toàn bộ dữ liệu thành một lần B-tree seek trực tiếp theo tên tag.""",
        "theoretical_tradeoff": """- Xử lý truy vấn 2 tag ($all) trong Multikey Index: Một index entry trong multikey B-tree chỉ chứa DUY NHẤT MỘT giá trị tag. Khi truy vấn tìm document có cả 2 tag, MongoDB dùng index để seek tag có độ chọn lọc cao hơn, sau đó bắt buộc phải FETCH các candidate document đó lên bộ nhớ để kiểm tra xem tag thứ hai có nằm trong mảng hay không.
- Chi phí ghi nhân bản: Nếu mỗi document có 3 đến 5 tag, việc chèn 1 document mới đồng nghĩa với việc phải chèn 3 đến 5 index entries vào cây B-tree, làm tăng chi phí ghi và phân mảnh bộ nhớ.""",
        "configs": {
            "A": {
                "name": "Baseline A (Unindexed Tag Lookups)",
                "sql": "Bảng con UC6_Tag chỉ có PK(PARENT_ID, TAG). Tìm theo TAG phải quét toàn bộ 30,471 dòng.",
                "mongo": "Collection chỉ có unique {_id_: 1, PARENT_ID: 1} và không có index trên tags. Quét toàn bộ 10,000 doc."
            },
            "C": {
                "name": "Config C (Target Multikey / Inverted Child Index)",
                "sql": "CREATE NONCLUSTERED INDEX IX_UC6_Tag_C_TagParent ON UC6_Tag(TAG, PARENT_ID);",
                "mongo": "db.collection.createIndex({tags: 1}); (Multikey Index tự động phân rã mảng)"
            }
        },
        "query_architecture_note": "📌 Lưu ý phương pháp luận: UC6 thiết kế 4 câu truy vấn gồm 2 truy vấn tag đơn (phổ biến vs hiếm) và 2 truy vấn tag kép conjunctive (phổ biến vs hiếm) để đánh giá khả năng seek và chi phí FETCH candidate documents!",
        "queries": {
            "ONE_TABLE": {
                "code": "ONE_TABLE",
                "name": "Single Tag: type:TABLE (Tag đơn phổ biến)",
                "purpose": "Khảo sát tìm kiếm theo 1 tag duy nhất có độ chọn lọc vừa phải (1,247 parent).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Đo lường khả năng seek tag đơn phổ biến.",
                "matched_rows": 1247,
                "sql": "SELECT PARENT_ID\nFROM UC6_Tag\nWHERE TAG = N'type:TABLE';",
                "mongo": "db.uc6_mongo_c.find(\n  {tags: 'type:TABLE'},\n  {_id: 0, PARENT_ID: 1}\n)",
                "expected": "Index C seek trực tiếp đến dải tag mà không cần quét toàn bộ bảng con / collection.",
                "finding": "Tăng tốc rõ rệt: SQL Server C giảm từ 150 trang đọc (PK Scan) xuống còn 8 trang (Index Seek), hoàn thành trong 4.00 ms (nhanh hơn A 3.28x). MongoDB C duyệt đúng 1,247 keys và docs qua IXSCAN + FETCH, hoàn thành trong 11.58 ms (nhanh hơn A 1.56x)."
            },
            "TWO_SYS_TABLE": {
                "code": "TWO_SYS_TABLE",
                "name": "Two Tags: owner:SYS + type:TABLE (Tag kép phổ biến)",
                "purpose": "Khảo sát truy vấn kết hợp 2 tag đồng thời có tần suất cao (1,125 parent).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Đo lường cơ chế giao cắt (intersection/fetch) trên 2 tag phổ biến.",
                "matched_rows": 1125,
                "sql": "SELECT PARENT_ID\nFROM UC6_Tag\nWHERE TAG IN (N'owner:SYS', N'type:TABLE')\nGROUP BY PARENT_ID\nHAVING COUNT(DISTINCT TAG) = 2;",
                "mongo": "db.uc6_mongo_c.find(\n  {tags: {$all: ['owner:SYS', 'type:TABLE']}},\n  {_id: 0, PARENT_ID: 1}\n)",
                "expected": "SQL Server seek cả 2 tag rồi gom nhóm. MongoDB seek tag thứ nhất rồi nạp doc kiểm tra tag thứ hai.",
                "finding": "Cơ chế thực thi thực tế: SQL Server C đọc 41 trang (nhanh hơn A 1.42x, 11.69 ms vs 16.66 ms). MongoDB C dùng index seek 1,247 keys của tag 'type:TABLE' rồi FETCH 1,247 doc lên để lọc tag 'owner:SYS', hoàn thành trong 13.07 ms (nhanh hơn A 1.66x)."
            },
            "ONE_TEMP_Y": {
                "code": "ONE_TEMP_Y",
                "name": "Single Tag: temporary:Y (Tag đơn hiếm)",
                "purpose": "Khảo sát tìm kiếm theo 1 tag đơn cực kỳ chọn lọc (chỉ có 51 parent).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Đo lường hiệu năng seek tối đa trên tag hiếm.",
                "matched_rows": 51,
                "sql": "SELECT PARENT_ID\nFROM UC6_Tag\nWHERE TAG = N'temporary:Y';",
                "mongo": "db.uc6_mongo_c.find(\n  {tags: 'temporary:Y'},\n  {_id: 0, PARENT_ID: 1}\n)",
                "expected": "Hiệu năng bùng nổ do chỉ phải bốc 51 bản ghi.",
                "finding": "Tốc độ cực nhanh: SQL Server C chỉ đọc đúng 2 trang index (ghi nhận 0.00 ms trên timer batch, p95 giảm từ 11.21 ms xuống 1.01 ms). MongoDB C chỉ duyệt đúng 51 keys và 51 docs, hoàn thành trong 2.84 ms (nhanh gấp 9.94x so với A mất 28.24 ms)."
            },
            "TWO_TABLE_TEMP_Y": {
                "code": "TWO_TABLE_TEMP_Y",
                "name": "Two Tags: type:TABLE + temporary:Y (Tag kép hiếm)",
                "purpose": "Khảo sát truy vấn kết hợp 2 tag trong đó có 1 tag cực hiếm (41 parent).",
                "is_shared": "Truy vấn RIÊNG BIỆT: Thể hiện tối đa sức mạnh của chiến lược seek tag chọn lọc nhất.",
                "matched_rows": 41,
                "sql": "SELECT PARENT_ID\nFROM UC6_Tag\nWHERE TAG IN (N'type:TABLE', N'temporary:Y')\nGROUP BY PARENT_ID\nHAVING COUNT(DISTINCT TAG) = 2;",
                "mongo": "db.uc6_mongo_c.find(\n  {tags: {$all: ['type:TABLE', 'temporary:Y']}},\n  {_id: 0, PARENT_ID: 1}\n)",
                "expected": "MongoDB chọn seek tag hiếm 'temporary:Y' (51 doc) thay vì tag phổ biến (1,247 doc), sau đó chỉ phải fetch 51 doc để lọc ra 41 kết quả.",
                "finding": "Chiến lược thông minh của MongoDB Optimizer (Speedup 13.85x): MongoDB explain cho thấy hệ thống chọn seek index trên tag hiếm 'temporary:Y' (chỉ bốc 51 keys), sau đó FETCH 51 doc và kiểm tra xem có tag 'type:TABLE' hay không để trả ra 41 parent! Thời gian giảm từ 28.53 ms xuống 2.06 ms. SQL Server C đọc 10 trang, đạt 2.01 ms (nhanh hơn A 5.39x)."
            }
        },
        "default_query": "TWO_TABLE_TEMP_Y",
        "mermaid_diagram": """flowchart LR
  subgraph MongoDB_Multikey ["MongoDB Multikey Index ({tags: 1})"]
    Doc127["Document 127: tags = ['owner:SYS', 'type:TABLE', 'temporary:Y']"]
    Doc127 --> E1["Index Entry 1: 'owner:SYS' ↦ Doc 127"]
    Doc127 --> E2["Index Entry 2: 'type:TABLE' ↦ Doc 127"]
    Doc127 --> E3["Index Entry 3: 'temporary:Y' ↦ Doc 127"]
  end
  Q_All["Truy vấn $all: ['type:TABLE', 'temporary:Y']"] -->|1. Seek tag hiếm| E3
  E3 -->|2. FETCH 51 doc ứng viên| MemoryFilter["3. Kiểm tra 'type:TABLE' trong mảng ↦ Trả 41 kết quả"]
""",
        "plan_analysis": """1. Chiến lược tối ưu truy vấn 2 tag trong MongoDB: Explain plan của TWO_TABLE_TEMP_Y chứng minh rõ ràng: MongoDB không quét toàn bộ 10,000 document, cũng không quét dải 1,247 key của tag 'type:TABLE'. Nó chọn seek tag 'temporary:Y' với 51 keys, sau đó FETCH đúng 51 candidate document để lọc tag còn lại trong bộ nhớ.
2. SQL Server 1NF Execution: Với truy vấn GROUP BY ... HAVING COUNT(DISTINCT TAG)=2, SQL Server thực hiện Index Seek trên secondary index để lấy toàn bộ các dòng của cả 2 tag, sau đó dùng Stream Aggregate gom theo PARENT_ID.""",
        "tradeoffs_measured": """- Chi phí phình to index do nhân bản entry: Vì mỗi document có trung bình 3.05 tag, Multikey Index phải lưu 30,471 entry cho 10,000 document (dung lượng 0.17 MB). Secondary index trên SQL Server chiếm 1.30 MB.
- Ảnh hưởng tốc độ ghi:
  * Trên MongoDB, thông lượng batch INSERT giảm 29.3% (từ 7,451 parent/s xuống 5,272 parent/s).
  * Thao tác gắn thêm tag mới ($addToSet) tăng độ trễ 33.0% (từ 27.06 ms lên 36.00 ms mỗi batch 20 parent).""",
        "verdict": "NÊN DÙNG Multikey Index trong MongoDB hoặc secondary index đảo (TAG, PARENT_ID) trên bảng con quan hệ khi ứng dụng thường xuyên lọc theo tag hoặc mảng, đặc biệt khi có ít nhất một tag có độ chọn lọc cao (speedup đạt từ 3.3x đến 13.9x). CẦN KIỂM SOÁT độ dài mảng vì mỗi phần tử thêm vào mảng sẽ nhân số lượng B-tree entry cần bảo trì trên mỗi thao tác ghi."
    }
}

# ==============================================================================
# MASTER DECISION MATRIX (Chương 5, Bảng 5.1 trong PDF V3)
# ==============================================================================
DECISIONS_TABLE = [
    {
        "index": "UC1: Compound B-Tree Index",
        "target_config": "INDEX(OWNER, OBJECT_TYPE, OBJECT_ID)",
        "benefit": "U1a: 3.42× (SQL), 103× (Mongo); U1d: Triệt tiêu toán tử Sort (3.61× / 29.7×).",
        "when_to_use": "Truy vấn lọc theo nhiều cột luôn bao gồm cột đầu tiên của khóa, hoặc có ORDER BY khớp chính xác thứ tự các cột phụ.",
        "when_to_avoid": "Truy vấn bỏ sót cột khóa đầu tiên (U1c), hoặc tiền tố khớp hàng ngàn dòng mà không có các cột được phủ (U1b).",
        "key_tradeoff": "Index lớn hơn từ +88% đến +96% so với index đơn cột; thông lượng INSERT trên MongoDB giảm 33.5%."
    },
    {
        "index": "UC2: Filtered / Partial Index",
        "target_config": "Filtered (WHERE TEMP='Y') / Partial ({TEMP: 'Y'})",
        "benefit": "Inside 'Y': 15.4×–30.6× (SQL), 107×–395× (Mongo) so với A; 1.5×–3.9× so với B.",
        "when_to_use": "Bảng dữ liệu phân bố lệch mạnh nơi ứng dụng liên tục lọc theo một giá trị hiếm đã biết trước (0.24% dòng hoạt động).",
        "when_to_avoid": "Truy vấn trên các giá trị ngoài tập ('N') hoặc truy vấn dùng tham số SQL (@p) chưa biết trước lúc biên dịch.",
        "key_tradeoff": "Tiết kiệm 98.4%–99.7% dung lượng lưu trữ index và build nhanh gấp 3.4×–9.7× so với full index."
    },
    {
        "index": "UC3: Covering Index",
        "target_config": "INCLUDE(ID, OWNER, NAME, TYPE) / Compound Covering",
        "benefit": "Medium range: 2.31× (SQL 100K), 1.54× (SQL 1M), 1.19× (Mongo 1M) so với B; triệt tiêu 100% lookup bảng gốc.",
        "when_to_use": "Các truy vấn khoảng (range) tần suất cao trả về nhiều cột, nơi chi phí RID Lookup hoặc FETCH ngẫu nhiên làm nghẽn I/O.",
        "when_to_avoid": "Truy vấn điểm (1 dòng) hoặc dải cực nhỏ nơi index hẹp đã hoàn thành trong ≤ 3.5 ms.",
        "key_tradeoff": "Dung lượng index tại 1M phình to gấp 5.94× (SQL, 127.4 MB) và 10.47× (Mongo, 66.9 MB)."
    },
    {
        "index": "UC4: Full-Text / Text Index",
        "target_config": "Full-Text (AUTO) / Text Index (BODY)",
        "benefit": "SQL: Giảm từ 3.3–4.1s xuống 14–23 ms; Mongo: Nhanh hơn 3.3×–107.8× trên các truy vấn cùng tập ID.",
        "when_to_use": "Tìm kiếm từ và cụm từ ngôn ngữ tự nhiên bên trong các đoạn văn bản dài (bài báo, mô tả, bình luận).",
        "when_to_avoid": "Yêu cầu bắt buộc so khớp chính xác từng chuỗi con (mã code, URL) hoặc bảng có tần suất ghi văn bản cực lớn trong MongoDB.",
        "key_tradeoff": "SQL: Độ trễ hiển thị dữ liệu mới lên tới 5.80 giây (asynchronous). Mongo: Thông lượng INSERT sụp đổ -95.3% (synchronous)."
    },
    {
        "index": "UC5: Clustered Columnstore",
        "target_config": "CLUSTERED COLUMNSTORE INDEX (SQL Server 1M)",
        "benefit": "AGG: Nhanh hơn 2.90× nhờ Batch Mode; Dung lượng giảm từ 219.0 MB xuống 9.46 MB (Tỉ lệ nén 23.15 : 1).",
        "when_to_use": "Truy vấn quét tổng hợp GROUP BY trên ít cột trong kho dữ liệu, bảng báo cáo phân tích hoặc bảng lưu trữ lịch sử.",
        "when_to_avoid": "Hệ thống giao dịch OLTP có tần suất ghi/sửa nhỏ lẻ liên tục, hoặc cần tìm kiếm điểm dưới mili-giây mà không có B-tree.",
        "key_tradeoff": "Thời gian build mất 22.3 giây; thông lượng INSERT nhỏ lẻ giảm -49.9% (dữ liệu phải đi qua delta store)."
    },
    {
        "index": "UC6: Multikey / Child Index",
        "target_config": "Multikey {tags: 1} / Secondary (TAG, PARENT_ID)",
        "benefit": "Tag chọn lọc: Nhanh hơn 3.3×–5.4× (SQL) và 9.9×–13.9× (Mongo) so với không có index.",
        "when_to_use": "Lọc đối tượng theo các phần tử trong mảng (tags) hoặc dòng trong bảng con quan hệ theo tên tag.",
        "when_to_avoid": "Mảng không giới hạn với hàng chục đến hàng trăm phần tử trên mỗi document trong các collection ghi nhiều.",
        "key_tradeoff": "Lưu 3.05× index entries cho mỗi parent; thông lượng INSERT trên Mongo giảm -29.3% và $addToSet tăng +33.0% độ trễ."
    }
]

# ==============================================================================
# METHODOLOGICAL PITFALLS (Bốn cạm bẫy dễ kết luận sai)
# ==============================================================================
PITFALLS = [
    {
        "title": "1. Có index chưa chắc đã chạy nhanh hơn không có index (Index Scan vs Table Scan)",
        "detail": "Trong UC1 trên MongoDB, việc đánh chỉ mục đơn cột trên OWNER = 'SYS' (chiếm 71.8% dữ liệu) khiến truy vấn mất 462.8 ms — chậm gần gấp đôi so với quét toàn bộ collection không có index (241.0 ms)! Nguyên nhân là do MongoDB phải duyệt qua 71,802 key trong B-tree rồi thực hiện 71,802 lần FETCH ngẫu nhiên từ bộ đệm, đắt hơn rất nhiều so với quét tuần tự."
    },
    {
        "title": "2. Thời gian chạy thấp chưa chắc đã là 'Speedup' cùng kết quả (Semantic Parity Trap)",
        "detail": "Trong UC4, toàn bộ 6 truy vấn trên SQL Server giữa LIKE và CONTAINS đều trả về các tập DOC_ID khác nhau do thuật toán tách từ và loại bỏ từ vô nghĩa. Nếu báo cáo tốc độ 17.4 ms so với 3,983.5 ms là 'tăng tốc 228 lần' thì hoàn toàn sai lệch về mặt khoa học, vì hai câu truy vấn trả lời hai câu hỏi khác nhau về mặt ngữ nghĩa."
    },
    {
        "title": "3. Quét Columnstore nhanh hơn không có nghĩa là thay thế được B-Tree Seek",
        "detail": "Trong UC5, truy vấn WHERE ID = 1 trên Columnstore hoàn thành trong 3.63 ms so với 88.81 ms trên Heap. Sự cải thiện này là do quét column segment nén trong Batch Mode nhanh hơn quét trang Heap thô, chứ Columnstore KHÔNG thực hiện seek. Một B-tree index thực sự trên ID chỉ mất <1 ms và đọc 2-3 trang."
    },
    {
        "title": "4. Ngưỡng độ phân giải timer dưới mili-giây (0.00 ms Timer Floor)",
        "detail": "Trên SQL Server ở các truy vấn cực nhanh (UC3 Point, UC3 1M Small, UC6 ONE_TEMP_Y), T-SQL batch timer ghi nhận median = 0.00 ms. Đây là giới hạn độ phân giải của hàm đo (~1 ms). Báo cáo khoa học không được lấy số khác chia cho 0 để ra 'vô cực lần', mà phải đánh giá thông qua số trang đọc vật lý (logical page reads) và phân vị p95."
    }
]
