# DBMS_EW_Group2 — nghiên cứu cấu trúc và thiết kế index

Đồ án CO3021 của Nhóm 02, HCMUT, nghiên cứu cách chọn index theo **câu truy vấn thực tế** trên SQL Server 2025 và MongoDB 7.0. Sáu use case xem đồng thời lợi ích đọc, execution plan, dung lượng, thời gian tạo index và chi phí ghi. UC5 chỉ có SQL Server; UC6 so sánh cách biểu diễn tag bằng mảng MongoDB và bảng con SQL.

## Bắt đầu từ đâu?

| Muốn làm gì                                        | Mở tài liệu                                                                                                                      |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Đọc kết luận và biểu đồ chính                      | [Báo cáo PDF](DBMS_Group2_report.pdf), [presentation PDF](Group02_EW_Presentation.pdf) hoặc [báo cáo Markdown](reports/FINAL_RESEARCH_REPORT.md) |
| Xem biểu đồ, plan và dữ liệu tương tác             | [Web demo](demo/README.md); lệnh chạy nhanh ở dưới                                                                               |
| Tự chạy lại benchmark bằng SSMS và MongoDB Compass | [TODO benchmark GUI](TODO_BENCHMARK_GUI.md)                                                                                      |
| Tìm số liệu gốc, plan, bản chạy được chấp nhận     | [Chỉ mục kết quả](results/README.md) và [đánh giá Phase 8](reports/PHASE8_EVIDENCE_REVIEW.md)                                    |
| Xem thiết kế và phương pháp                        | [Chương phương pháp](report/source/chapters/03-methodology.tex); các báo cáo UC và kết quả thực đo là nguồn cho trạng thái hoàn thành |

## Sáu use case

| UC                   | Câu hỏi                                                             | Index / cấu trúc chính                                    | Báo cáo chi tiết                                  |
| -------------------- | ------------------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------- |
| 1 · Compound         | Thứ tự key, prefix và sort ảnh hưởng đường truy cập thế nào?        | SQL nonclustered rowstore; Mongo compound index           | [Phase 3](reports/PHASE3_UC1_COMPOUND.md)         |
| 2 · Filtered/partial | Chỉ index nhóm `TEMPORARY='Y'` giúp gì và tốn gì?                   | SQL filtered index; Mongo partial index                   | [Phase 4](reports/PHASE4_UC2_FILTERED_PARTIAL.md) |
| 3 · Covering         | Index có trả đủ cột mà không đọc lại bản ghi không?                 | SQL `INCLUDE`; Mongo indexed projection                   | [Phase 5](reports/PHASE5_UC3_COVERING.md)         |
| 4 · Full-text        | Tìm từ/cụm từ trong văn bản khác tìm chuỗi con ra sao?              | SQL Full-Text Search; Mongo text index                    | [UC4](reports/UC4_FULL_TEXT_BENCHMARK.md)         |
| 5 · Columnstore      | Lưu theo cột có lợi cho tổng hợp và bất lợi cho point lookup không? | SQL clustered columnstore so với rowstore                 | [Phase 6](reports/PHASE6_UC5_COLUMNSTORE.md)      |
| 6 · Multikey         | Tìm một/hai tag trong mảng so với bảng quan hệ ra sao?              | Mongo multikey; SQL index `(TAG,PARENT_ID)` trên bảng con | [Phase 7](reports/PHASE7_UC6_MULTIKEY.md)         |

**Quy tắc diễn giải:** A là baseline, B là index thông thường khi có đối chứng phù hợp, C là thiết kế đang kiểm tra. So sánh latency **trong cùng DBMS, cùng query và cùng scale**: SQL đo thời gian materialize kết quả trên server, Mongo đo lúc tiêu thụ hết cursor ở client. UC4 `LIKE`/regex và full-text/text có thể trả **khác tập ID**, nên không tự động gọi chênh lệch thời gian là speedup cùng kết quả. Các số `0.000 ms` nằm dưới giới hạn độ phân giải của timer. Xem [đánh giá evidence](reports/PHASE8_EVIDENCE_REVIEW.md) trước khi trích số.

## Xem web demo

Web là bản trình bày tương tác của **PDF và bằng chứng đã được chấp nhận**; mở web không chạy truy vấn benchmark mới. Từ thư mục gốc, với Python 3.13 trên Windows PowerShell:

```powershell
py -3.13 -m venv demo/.venv
& .\demo\.venv\Scripts\python.exe -m pip install -r demo/requirements.txt
& .\demo\.venv\Scripts\python.exe -m streamlit run demo/app.py
```

Mở địa chỉ do Streamlit in ra (thông thường `http://localhost:8501`). App đọc các file `results/phase8/`, các transcript được chọn và danh mục plan; nó dừng với lỗi rõ ràng nếu thiếu nguồn đo, hash nguồn đổi hoặc thiếu plan. Không cần kết nối DB để **xem** demo. Xem [hướng dẫn web](demo/README.md) để biết các màn hình.

Repository GitHub giữ code, hai PDF nộp bài, báo cáo Markdown, dữ liệu mẫu nhỏ và toàn bộ accepted evidence mà web cần. `.gitignore` loại môi trường ảo, file build và các file nguồn/CSV quá lớn (`big table export.sql`, `BIG_TABLE_1000K.csv`, `BIG_TABLE_15000K.csv`, `True.csv`, `Fake.csv`). Những file này vẫn ở máy cục bộ; cần bộ dữ liệu đầy đủ hoặc ZIP nộp bài để nạp lại database và chạy lại toàn bộ thí nghiệm từ đầu. Web dùng accepted evidence nên không cần các file lớn đó để xem kết quả.

## Dữ liệu và bằng chứng

| Nguồn                              | Vai trò                                                                                   | Dấu vết                                                                                                                          |
| ---------------------------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Oracle `BIG_TABLE` xuất ra CSV     | Metadata catalog cho UC1–UC3 và UC5; UC6 dùng 10K dòng để tạo tag theo quy tắc            | [Phase 1 audit](reports/PHASE1_DATA_AUDIT.md), [bản ghi DATA_READY 10K](local_data/derived/BIG_TABLE_10K.DATA_READY_RECORD.json) |
| News prose 10K dòng                | Corpus riêng cho UC4; chọn xác định từ hai CSV nguồn, không gán nhãn đúng/sai từ tên file | [UC4 manifest](local_data/derived/uc4/manifest.json), [provenance nguồn](local_data/source/fake_real_news/PROVENANCE.json)       |
| 10K parent / 30,471 tag membership | Corpus UC6 suy ra từ các trường metadata, không phải nhãn chủ đề thủ công                 | [UC6 manifest](local_data/derived/uc6/manifest.json)                                                                             |

Kết quả chính ở `results/uc1/` … `results/uc6/`: `accepted/` chứa transcript dùng cho kết luận; `plans/` chứa actual plan; `archive/` lưu bản lỗi hoặc bị thay thế. [Results README](results/README.md) chỉ rõ file được dùng cho từng UC, bao gồm SQL UC2 v4 và UC5 v2. [Phase 8 review](reports/PHASE8_EVIDENCE_REVIEW.md) đã kiểm lại **128 read cells, 104 write cells và 136 plan files** từ artifacts; đây là kiểm toán kết quả đã có, không phải một lần benchmark mới. Phase 2 smoke vẫn có giới hạn được ghi trong báo cáo của nó.

## Chạy lại thí nghiệm

1. Đọc [TODO benchmark GUI](TODO_BENCHMARK_GUI.md) để kiểm tra database/source, bản sao thí nghiệm, thứ tự setup → run → diagnostics → cleanup và cách lưu output.
2. Chạy SQL bằng **SSMS**. UC1 cần bật _Query → SQLCMD Mode_ trong SSMS để xử lý `:r`; không cần mở `sqlcmd.exe` cho quy trình thông thường.
3. Dùng **MongoDB Compass kết nối server thật** để xem collection, tạo index và xem Explain. Giao diện không tái tạo được protocol 2 warmup + 25 mẫu, full cursor và batch write; chỉ khi cần tái lập các metric đó mới dùng script `mongosh --file` theo TODO.
4. Giữ kết quả chạy mới dưới **tên file mới** và xác minh `RUN_COMPLETE PASS`, tập kết quả và plan trước khi thêm vào `accepted/`. Không ghi đè accepted evidence.

Các script SQL nằm trong `sql/uc*_*/`, script Mongo trong `mongo/uc*_*/`, và helper đo trong `sql/benchmark/`, `mongo/benchmark/`. Chúng tạo bản sao thí nghiệm; hãy đọc file setup/cleanup tương ứng trước khi chạy trên database của mình.

## Cấu trúc thư mục

| Thư mục          | Nội dung                                                            |
| ---------------- | ------------------------------------------------------------------- |
| `analysis/`      | Tạo/kiểm corpus UC4–UC6 và rà soát evidence Phase 8                 |
| `local_data/`    | Dữ liệu mẫu, CSV/JSONL nhỏ, manifest và provenance; file lớn bị loại khỏi Git |
| `sql/`, `mongo/` | Script kiểm tra dữ liệu và benchmark theo use case                  |
| `results/`       | Transcript, actual plans, manifest, bản audit và archive            |
| `reports/`       | Báo cáo từng phase/UC và bản tổng hợp Markdown                      |
| `report/`        | Nguồn LaTeX; PDF nộp bài ở [report](DBMS_Group2_report.pdf) và [presentation](Group02_EW_Presentation.pdf) tại thư mục gốc |
| `demo/`          | Ứng dụng Streamlit đọc report và accepted evidence                  |

Muốn dựng lại PDF, làm theo [report/README.md](report/README.md). Việc dựng report tạo file trình bày từ kết quả có sẵn; không kết nối SQL Server hoặc MongoDB.
