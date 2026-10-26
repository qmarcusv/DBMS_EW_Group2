/*
Run this file first, then benchmark_smoke.sql in the SAME SSMS query window.
All objects below are session-local in tempdb. No persistent object is changed.
Future UC scripts can call #bench_read and #bench_action in that same session.

#bench_read contract: @WorkSql must assign @actual_rows and @fingerprint.
For ordinary row retrieval, a future UC script should materialize its exact
projection into a query-specific #result table inside @WorkSql, then assign
outputs from #result. A count-only aggregate is useful for this infrastructure
smoke test, but is not a substitute for timing a row-returning SELECT.
*/
USE [DBMS_EW_Group02];
SET NOCOUNT ON;

IF OBJECT_ID('tempdb..#bench_samples') IS NOT NULL DROP TABLE #bench_samples;
CREATE TABLE #bench_samples (
    run_id uniqueidentifier NOT NULL,
    query_id nvarchar(128) NOT NULL,
    configuration nvarchar(12) NOT NULL,
    iteration int NOT NULL,
    elapsed_ms decimal(19,3) NOT NULL,
    matched_rows bigint NOT NULL,
    fingerprint int NULL,
    correctness_status varchar(8) NOT NULL,
    measured_at_utc datetime2(7) NOT NULL
);

IF OBJECT_ID('tempdb..#bench_actions') IS NOT NULL DROP TABLE #bench_actions;
CREATE TABLE #bench_actions (
    run_id uniqueidentifier NOT NULL,
    action_kind varchar(16) NOT NULL,
    target_table sysname NOT NULL,
    elapsed_ms decimal(19,3) NOT NULL,
    affected_rows bigint NULL,
    rows_per_second decimal(20,3) NULL,
    measured_at_utc datetime2(7) NOT NULL
);

IF OBJECT_ID('tempdb..#bench_read') IS NOT NULL DROP PROCEDURE #bench_read;
IF OBJECT_ID('tempdb..#bench_storage') IS NOT NULL DROP PROCEDURE #bench_storage;
IF OBJECT_ID('tempdb..#bench_action') IS NOT NULL DROP PROCEDURE #bench_action;
GO
CREATE PROCEDURE #bench_read
    @RunId uniqueidentifier,
    @QueryId nvarchar(128),
    @Configuration nvarchar(12),
    @WorkSql nvarchar(max),
    @ExpectedRows bigint,
    @Warmups int = 2,
    @Repetitions int = 25
AS
BEGIN
    SET NOCOUNT ON;
    IF @Warmups < 0 OR @Repetitions < 1 OR @Repetitions > 1000
        THROW 50001, 'Invalid warm-up or repetition count.', 1;
    IF @WorkSql IS NULL OR LEN(@WorkSql) = 0 OR @ExpectedRows IS NULL
        THROW 50002, 'Work SQL and expected row count are required.', 1;
    IF OBJECT_ID('tempdb..#bench_samples') IS NULL
        THROW 50003, 'Run benchmark_core.sql in this session first.', 1;

    DECLARE @i int = 1, @rows bigint, @fingerprint int;
    DECLARE @start datetime2(7), @end datetime2(7), @first_fingerprint int;
    WHILE @i <= @Warmups + @Repetitions
    BEGIN
        SET @rows = NULL;
        SET @fingerprint = NULL;
        SET @start = SYSUTCDATETIME();
        EXEC sys.sp_executesql @WorkSql,
             N'@actual_rows bigint OUTPUT, @fingerprint int OUTPUT',
             @actual_rows = @rows OUTPUT, @fingerprint = @fingerprint OUTPUT;
        SET @end = SYSUTCDATETIME();
        IF @rows IS NULL
            THROW 50004, 'Work SQL did not assign @actual_rows.', 1;
        IF @i = 1 SET @first_fingerprint = @fingerprint;
        IF @i > @Warmups
            INSERT #bench_samples
                (run_id, query_id, configuration, iteration, elapsed_ms,
                 matched_rows, fingerprint, correctness_status, measured_at_utc)
            VALUES
                (@RunId, @QueryId, @Configuration, @i - @Warmups,
                 CONVERT(decimal(19,3), DATEDIFF_BIG(MICROSECOND, @start, @end) / 1000.0),
                 @rows, @fingerprint,
                 CASE WHEN @rows = @ExpectedRows
                           AND (@fingerprint = @first_fingerprint OR
                                (@fingerprint IS NULL AND @first_fingerprint IS NULL))
                      THEN 'PASS' ELSE 'FAIL' END, @end);
        SET @i += 1;
    END;
END;
GO
CREATE PROCEDURE #bench_storage @TableName sysname
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @oid int = OBJECT_ID(N'dbo.' + QUOTENAME(@TableName), N'U');
    IF @oid IS NULL THROW 50005, 'dbo table missing or not visible.', 1;

    -- used_page_count includes in-row, LOB and row-overflow pages; 8 KiB/page.
    -- index_id 0 is the HEAP base, 1 clustered base, >1 secondary indexes.
    SELECT N'INDEX_STORAGE' AS section, OBJECT_SCHEMA_NAME(i.object_id) AS schema_name,
           @TableName AS table_name, i.index_id, i.name AS index_name,
           i.type_desc, i.has_filter, i.filter_definition,
           COALESCE(SUM(ps.row_count), 0) AS approximate_rows,
           COALESCE(SUM(ps.used_page_count), 0) AS used_pages,
           COALESCE(SUM(ps.reserved_page_count), 0) AS reserved_pages,
           COALESCE(SUM(ps.used_page_count), 0) * CONVERT(bigint,8192) AS used_bytes,
           COALESCE(SUM(ps.reserved_page_count), 0) * CONVERT(bigint,8192) AS reserved_bytes
    FROM sys.indexes AS i
    LEFT JOIN sys.dm_db_partition_stats AS ps
      ON ps.object_id = i.object_id AND ps.index_id = i.index_id
    WHERE i.object_id = @oid
    GROUP BY i.object_id, i.index_id, i.name, i.type_desc,
             i.has_filter, i.filter_definition
    ORDER BY i.index_id;

    SELECT N'INDEX_COLUMN' AS section, @TableName AS table_name,
           i.name AS index_name, ic.key_ordinal, ic.is_included_column,
           ic.is_descending_key, c.name AS column_name
    FROM sys.indexes AS i
    JOIN sys.index_columns AS ic ON ic.object_id = i.object_id
                                 AND ic.index_id = i.index_id
    JOIN sys.columns AS c ON c.object_id = ic.object_id
                          AND c.column_id = ic.column_id
    WHERE i.object_id = @oid
    ORDER BY i.index_id, ic.index_column_id;
END;
GO
CREATE PROCEDURE #bench_action
    @RunId uniqueidentifier,
    @ActionKind varchar(16),
    @TargetTable sysname,
    @ActionSql nvarchar(max)
AS
BEGIN
    SET NOCOUNT ON;
    IF @ActionKind NOT IN ('INDEX_BUILD','INSERT','UPDATE')
        THROW 50006, 'Unsupported action kind.', 1;
    IF @TargetTable NOT LIKE N'UC[1-6][_]%'
       AND @TargetTable NOT LIKE N'BENCH[_]%'
        THROW 50007, 'Write target must be a named disposable UC/BENCH table.', 1;
    IF OBJECT_ID(N'dbo.' + QUOTENAME(@TargetTable), N'U') IS NULL
        THROW 50008, 'Disposable target table missing.', 1;
    IF @ActionSql IS NULL OR LEN(@ActionSql) = 0
        THROW 50009, 'Action SQL is required.', 1;
    -- Trusted UC scripts supply inspected SQL text. This guard validates the
    -- declared target; it cannot parse arbitrary SQL to prove every write target.
    DECLARE @start datetime2(7) = SYSUTCDATETIME(), @end datetime2(7);
    DECLARE @affected bigint = NULL, @elapsed_ms decimal(19,3);
    EXEC sys.sp_executesql @ActionSql,
         N'@affected_rows bigint OUTPUT', @affected_rows = @affected OUTPUT;
    SET @end = SYSUTCDATETIME();
    SET @elapsed_ms = CONVERT(decimal(19,3), DATEDIFF_BIG(MICROSECOND, @start, @end) / 1000.0);
    INSERT #bench_actions
        (run_id, action_kind, target_table, elapsed_ms, affected_rows,
         rows_per_second, measured_at_utc)
    VALUES
        (@RunId, @ActionKind, @TargetTable, @elapsed_ms, @affected,
         CASE WHEN @ActionKind = 'INSERT' AND @affected IS NOT NULL AND @elapsed_ms > 0
              THEN CONVERT(decimal(20,3), @affected * 1000.0 / @elapsed_ms)
              ELSE NULL END, @end);
END;
GO
SELECT N'CORE_READY' AS section, DB_NAME() AS database_name,
       @@SPID AS session_id,
       OBJECT_ID('tempdb..#bench_samples') AS sample_table_object_id,
       N'Run the smoke or UC benchmark in this exact query window and connection.' AS note;
