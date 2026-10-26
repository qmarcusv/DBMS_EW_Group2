/*
Run benchmark_core.sql first in this SAME SSMS query window, then this file.
Read-only 10K infrastructure smoke. Results to Text/File is convenient.
The timed work is a COUNT plus checksum aggregate; it fully scans qualifying
rows but does not measure ordinary row transfer to a client.
*/
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
IF OBJECT_ID('tempdb..#bench_samples') IS NULL
    THROW 50100, 'Core is not loaded in this connection. SSMS query tabs use separate sessions: run core, then smoke in the same query window.', 1;
IF OBJECT_ID(N'dbo.DEMO_BIG_TABLE_10K', N'U') IS NULL
    THROW 50101, 'Verified 10K source table is missing.', 1;

DECLARE @run_id uniqueidentifier = NEWID();
DECLARE @work_sql nvarchar(max) = N'
SELECT @actual_rows = COUNT_BIG(*),
       @fingerprint = CHECKSUM_AGG(BINARY_CHECKSUM([ID],[OBJECT_ID],[OBJECT_NAME]))
FROM dbo.DEMO_BIG_TABLE_10K;';

EXEC #bench_read @RunId = @run_id,
     @QueryId = N'P2_SMOKE_FULL_10K', @Configuration = N'SMOKE',
     @WorkSql = @work_sql, @ExpectedRows = 10000,
     @Warmups = 2, @Repetitions = 7;

SELECT N'RAW_SAMPLE' AS section, run_id, query_id, configuration,
       iteration, elapsed_ms, matched_rows, fingerprint,
       correctness_status, measured_at_utc
FROM #bench_samples WHERE run_id = @run_id
ORDER BY iteration;

;WITH distributions AS (
    SELECT run_id, query_id, configuration,
           COUNT(*) OVER (PARTITION BY run_id,query_id,configuration) AS repetition_count,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY elapsed_ms)
             OVER (PARTITION BY run_id,query_id,configuration) AS median_ms,
           PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY elapsed_ms)
             OVER (PARTITION BY run_id,query_id,configuration) AS p95_ms,
           MIN(matched_rows) OVER (PARTITION BY run_id,query_id,configuration) AS min_rows,
           MAX(matched_rows) OVER (PARTITION BY run_id,query_id,configuration) AS max_rows,
           MIN(fingerprint) OVER (PARTITION BY run_id,query_id,configuration) AS min_fingerprint,
           MAX(fingerprint) OVER (PARTITION BY run_id,query_id,configuration) AS max_fingerprint,
           MAX(measured_at_utc) OVER (PARTITION BY run_id,query_id,configuration) AS sample_timestamp_utc,
           SUM(CASE WHEN correctness_status = 'FAIL' THEN 1 ELSE 0 END)
             OVER (PARTITION BY run_id,query_id,configuration) AS failed_samples
    FROM #bench_samples WHERE run_id = @run_id
)
SELECT DISTINCT N'BENCHMARK_SUMMARY' AS section, run_id,
       sample_timestamp_utc AS timestamp_utc, N'PHASE2' AS phase,
       N'SMOKE' AS use_case, N'SQL_SERVER' AS dbms,
       CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion')) AS server_version,
       N'dbo.DEMO_BIG_TABLE_10K' AS dataset, 10000 AS dataset_row_count,
       query_id, configuration, 2 AS warmup_count, repetition_count,
       N'SYSUTCDATETIME/DATEDIFF_BIG; server T-SQL batch' AS timing_method,
       CONVERT(decimal(19,3), median_ms) AS query_median_ms,
       CONVERT(decimal(19,3), p95_ms) AS query_p95_ms,
       min_rows AS returned_rows, min_fingerprint AS fingerprint,
       CASE WHEN failed_samples = 0 AND min_rows = max_rows
                      AND min_fingerprint = max_fingerprint
            THEN 'PASS' ELSE 'FAIL' END AS correctness_status,
       CAST(NULL AS bigint) AS logical_reads,
       CAST(NULL AS bigint) AS total_keys_examined,
       CAST(NULL AS bigint) AS total_docs_examined,
       CAST(NULL AS bigint) AS index_storage_bytes,
       CAST(NULL AS decimal(19,3)) AS index_build_ms,
       CAST(NULL AS decimal(20,3)) AS insert_rows_per_second,
       CAST(NULL AS decimal(19,3)) AS update_median_ms,
       N'See separate diagnostic result and Messages; export .sqlplan' AS query_plan_reference
FROM distributions;

EXEC #bench_storage @TableName = N'DEMO_BIG_TABLE_10K';

/* Separate diagnostic execution: IO/CPU messages and actual XML plan.
   Do not include its elapsed time in the RAW_SAMPLE distribution.
   In SSMS, turn OFF toolbar "Include Actual Execution Plan" when using
   SET STATISTICS XML, and save the XML result as a .sqlplan file. */
SELECT N'DIAGNOSTIC_START' AS section, @run_id AS run_id,
       N'Next SELECT has SET STATISTICS IO/TIME/XML; not timed as a raw sample.' AS note;
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
SET STATISTICS XML ON;
SELECT COUNT_BIG(*) AS matched_rows,
       CHECKSUM_AGG(BINARY_CHECKSUM([ID],[OBJECT_ID],[OBJECT_NAME])) AS fingerprint
FROM dbo.DEMO_BIG_TABLE_10K;
SET STATISTICS XML OFF;
SET STATISTICS TIME OFF;
SET STATISTICS IO OFF;
SELECT N'DIAGNOSTIC_END' AS section, @run_id AS run_id;
