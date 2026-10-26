/* Run after uc1_setup.sql in SSMS SQLCMD Mode, either directly or via
   uc1_run.sql. This file loads benchmark_core.sql in its own connection.
   No reference writes.
   Timed SELECTs materialize projected rows as JSON in server memory to avoid
   25x SSMS result rendering; U1d ORDER BY remains part of the SELECT plan.
   This is server materialization time, not client retrieval time. */
:on error exit
:r W:\MYSELF\HCMUT-university\Senior\HK_261\DBMS\BTL\DBMS_EW_Group2\sql\benchmark\benchmark_core.sql
GO

USE [DBMS_EW_Group02];
SET NOCOUNT ON;
IF OBJECT_ID('tempdb..#bench_samples') IS NULL OR OBJECT_ID('tempdb..#bench_actions') IS NULL
    THROW 51100, 'UC1 core did not load. Enable SQLCMD Mode and execute this entire file.', 1;
SELECT N'UC1_SESSION_AFTER_CORE' AS section, @@SPID AS session_id,
       OBJECT_ID('tempdb..#bench_samples') AS sample_table_object_id,
       OBJECT_ID('tempdb..#bench_read','P') AS read_proc_object_id;
IF OBJECT_ID(N'dbo.UC1_Bench_100K',N'U') IS NULL
    THROW 51101, 'Run uc1_setup.sql first.', 1;
IF EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.UC1_Bench_100K') AND index_id>0)
    THROW 51102, 'Read copy must start at A with no optional index.', 1;
IF (SELECT COUNT_BIG(*) FROM dbo.UC1_Bench_100K) <> 100000
    THROW 51103, 'Read copy count changed.', 1;
IF EXISTS (SELECT 1 FROM sys.tables WHERE name IN (N'UC1_Write_A_100K',N'UC1_Write_B_100K',N'UC1_Write_C_100K')
           AND schema_id=SCHEMA_ID(N'dbo') HAVING COUNT(*) <> 3)
    THROW 51104, 'Write copies missing.', 1;

DECLARE @run_id uniqueidentifier=NEWID();
DECLARE @queries TABLE (
    query_id nvarchar(4) PRIMARY KEY, predicate_sql nvarchar(300) NOT NULL,
    order_sql nvarchar(120) NOT NULL, expected_rows bigint NOT NULL,
    expected_fingerprint int NOT NULL
);
INSERT @queries VALUES
 (N'U1a',N'[OWNER]=N''SYS'' AND [OBJECT_TYPE]=N''TABLE'' AND [OBJECT_ID]=16',N'',2,
  (SELECT CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_TYPE,OBJECT_ID))
   FROM dbo.DEMO_BIG_TABLE_100K WHERE OWNER=N'SYS' AND OBJECT_TYPE=N'TABLE' AND OBJECT_ID=16)),
 (N'U1b',N'[OWNER]=N''SYS'' AND [OBJECT_TYPE]=N''TABLE''',N'',3405,
  (SELECT CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_TYPE,OBJECT_ID))
   FROM dbo.DEMO_BIG_TABLE_100K WHERE OWNER=N'SYS' AND OBJECT_TYPE=N'TABLE')),
 (N'U1c',N'[OBJECT_TYPE]=N''TABLE'' AND [OBJECT_ID]=16',N'',2,
  (SELECT CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_TYPE,OBJECT_ID))
   FROM dbo.DEMO_BIG_TABLE_100K WHERE OBJECT_TYPE=N'TABLE' AND OBJECT_ID=16)),
 (N'U1d',N'[OWNER]=N''CTXSYS''',N' ORDER BY [OBJECT_TYPE] ASC,[OBJECT_ID] ASC',398,
  (SELECT CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_TYPE,OBJECT_ID))
   FROM dbo.DEMO_BIG_TABLE_100K WHERE OWNER=N'CTXSYS'));

SELECT N'QUERY_SELECTIVITY' AS section, query_id, predicate_sql, order_sql,
       expected_rows AS matched_rows, CONVERT(decimal(12,6),expected_rows/100000.0) AS selectivity,
       expected_fingerprint
FROM @queries ORDER BY query_id;
SELECT N'RUN_CONTEXT' AS section,@run_id AS run_id,@@SPID AS session_id,
       CONVERT(nvarchar(128),SERVERPROPERTY('ProductVersion')) AS server_version,
       N'100K read copy; 2 warmups + 25 samples; JSON materialization; no plan instrumentation in timed loop' AS protocol;

DECLARE @configuration char(1),@query_id nvarchar(4),@predicate nvarchar(300),
        @order nvarchar(120),@expected bigint,@expected_fp int,@work nvarchar(max);
DECLARE configuration_cursor CURSOR LOCAL FAST_FORWARD FOR
    SELECT config FROM (VALUES('A'),('B'),('C')) AS v(config);
OPEN configuration_cursor;
FETCH NEXT FROM configuration_cursor INTO @configuration;
WHILE @@FETCH_STATUS=0
BEGIN
    IF @configuration='B'
    BEGIN
        EXEC #bench_action @RunId=@run_id,@ActionKind='INDEX_BUILD',
             @TargetTable=N'UC1_Bench_100K',
             @ActionSql=N'CREATE INDEX IX_UC1_Owner ON dbo.UC1_Bench_100K ([OWNER]);';
        SELECT TOP(1) N'INDEX_BUILD' AS section,@configuration AS configuration,
               elapsed_ms AS index_build_ms, measured_at_utc
        FROM #bench_actions WHERE run_id=@run_id AND action_kind='INDEX_BUILD'
        ORDER BY measured_at_utc DESC;
    END;
    IF @configuration='C'
    BEGIN
        DROP INDEX IX_UC1_Owner ON dbo.UC1_Bench_100K;
        EXEC #bench_action @RunId=@run_id,@ActionKind='INDEX_BUILD',
             @TargetTable=N'UC1_Bench_100K',
             @ActionSql=N'CREATE INDEX IX_UC1_OwnerTypeObjectId ON dbo.UC1_Bench_100K ([OWNER],[OBJECT_TYPE],[OBJECT_ID]);';
        SELECT TOP(1) N'INDEX_BUILD' AS section,@configuration AS configuration,
               elapsed_ms AS index_build_ms, measured_at_utc
        FROM #bench_actions WHERE run_id=@run_id AND action_kind='INDEX_BUILD'
        ORDER BY measured_at_utc DESC;
    END;
    SELECT N'CONFIGURATION' AS section,@configuration AS configuration,
           COUNT(*) AS optional_index_count
    FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.UC1_Bench_100K') AND index_id>0;
    EXEC #bench_storage @TableName=N'UC1_Bench_100K';

    DECLARE query_cursor CURSOR LOCAL FAST_FORWARD FOR
        SELECT query_id,predicate_sql,order_sql,expected_rows,expected_fingerprint
        FROM @queries ORDER BY query_id;
    OPEN query_cursor;
    FETCH NEXT FROM query_cursor INTO @query_id,@predicate,@order,@expected,@expected_fp;
    WHILE @@FETCH_STATUS=0
    BEGIN
        SET @work=N'DECLARE @payload nvarchar(max);
SELECT @payload=(SELECT [ID],[OWNER],[OBJECT_TYPE],[OBJECT_ID]
 FROM dbo.UC1_Bench_100K WHERE '+@predicate+@order+N' FOR JSON PATH);
SELECT @actual_rows=COUNT_BIG(*),
       @fingerprint=CHECKSUM_AGG(BINARY_CHECKSUM([ID],[OWNER],[OBJECT_TYPE],[OBJECT_ID]))
FROM OPENJSON(@payload) WITH (
 [ID] bigint ''$.ID'', [OWNER] nvarchar(128) ''$.OWNER'',
 [OBJECT_TYPE] nvarchar(64) ''$.OBJECT_TYPE'', [OBJECT_ID] bigint ''$.OBJECT_ID'');';
        EXEC #bench_read @RunId=@run_id,@QueryId=@query_id,@Configuration=@configuration,
             @WorkSql=@work,@ExpectedRows=@expected,@Warmups=2,@Repetitions=25;
        IF EXISTS (SELECT 1 FROM #bench_samples WHERE run_id=@run_id
                   AND query_id=@query_id AND configuration=@configuration
                   AND (correctness_status<>'PASS' OR fingerprint<>@expected_fp))
            THROW 51105, 'Timed results differ from source count/fingerprint.', 1;
        FETCH NEXT FROM query_cursor INTO @query_id,@predicate,@order,@expected,@expected_fp;
    END;
    CLOSE query_cursor;
    DEALLOCATE query_cursor;
    IF (SELECT COUNT_BIG(*) FROM dbo.UC1_Bench_100K)<>100000
        THROW 51106, 'Read copy row count changed.', 1;
    FETCH NEXT FROM configuration_cursor INTO @configuration;
END;
CLOSE configuration_cursor;
DEALLOCATE configuration_cursor;

SELECT N'READ_RAW' AS section,run_id,configuration,query_id,iteration,
       elapsed_ms,matched_rows,fingerprint,correctness_status,measured_at_utc
FROM #bench_samples WHERE run_id=@run_id ORDER BY configuration,query_id,iteration;
;WITH q AS (
 SELECT run_id,configuration,query_id,
        COUNT(*) OVER(PARTITION BY configuration,query_id) AS repetitions,
        PERCENTILE_CONT(.5) WITHIN GROUP(ORDER BY elapsed_ms)
          OVER(PARTITION BY configuration,query_id) AS median_ms,
        PERCENTILE_CONT(.95) WITHIN GROUP(ORDER BY elapsed_ms)
          OVER(PARTITION BY configuration,query_id) AS p95_ms,
        MIN(matched_rows) OVER(PARTITION BY configuration,query_id) AS matched_rows,
        MIN(fingerprint) OVER(PARTITION BY configuration,query_id) AS fingerprint
 FROM #bench_samples WHERE run_id=@run_id
)
SELECT DISTINCT N'READ_SUMMARY' AS section,run_id,configuration,query_id,repetitions,
       CONVERT(decimal(19,3),median_ms) AS median_ms,
       CONVERT(decimal(19,3),p95_ms) AS p95_ms,matched_rows,fingerprint
FROM q ORDER BY configuration,query_id;

/* Independent write copies. Their index builds are setup, not read-copy
   build measurements. Identical 1000-row source batch and 20-step progression
   in A/B/C. No writes occur on dbo.DEMO_BIG_TABLE_100K. */
SELECT TOP(1000) * INTO #uc1_insert_batch
FROM dbo.DEMO_BIG_TABLE_100K ORDER BY ID;
IF (SELECT COUNT(*) FROM #uc1_insert_batch)<>1000 THROW 51107,'Insert batch incomplete.',1;
DECLARE @write_table sysname,@qualified nvarchar(300),@batch int,@sql nvarchar(max);
DECLARE write_cursor CURSOR LOCAL FAST_FORWARD FOR
 SELECT config,table_name FROM (VALUES
  ('A',N'UC1_Write_A_100K'),('B',N'UC1_Write_B_100K'),('C',N'UC1_Write_C_100K'))
 AS v(config,table_name);
OPEN write_cursor;
FETCH NEXT FROM write_cursor INTO @configuration,@write_table;
WHILE @@FETCH_STATUS=0
BEGIN
    SET @qualified=N'dbo.'+QUOTENAME(@write_table);
    IF (SELECT SUM(row_count) FROM sys.dm_db_partition_stats
        WHERE object_id=OBJECT_ID(@qualified) AND index_id=0)<>100000
        THROW 51108,'Write copy missing or already mutated.',1;
    IF @configuration='B'
        CREATE INDEX IX_UC1_Owner ON dbo.UC1_Write_B_100K ([OWNER]);
    IF @configuration='C'
        CREATE INDEX IX_UC1_OwnerTypeObjectId ON dbo.UC1_Write_C_100K ([OWNER],[OBJECT_TYPE],[OBJECT_ID]);
    SET @batch=0;
    WHILE @batch<20
    BEGIN
        SET @sql=N'INSERT INTO '+@qualified+N'
 ([ID],[OWNER],[OBJECT_NAME],[SUBOBJECT_NAME],[OBJECT_ID],[DATA_OBJECT_ID],
  [OBJECT_TYPE],[CREATED],[LAST_DDL_TIME],[TIMESTAMP],[STATUS],[TEMPORARY],
  [GENERATED],[SECONDARY])
 SELECT [ID]+'+CONVERT(nvarchar(20),1000000+@batch*1000)+N',
  [OWNER],[OBJECT_NAME],[SUBOBJECT_NAME],[OBJECT_ID],[DATA_OBJECT_ID],
  [OBJECT_TYPE],[CREATED],[LAST_DDL_TIME],[TIMESTAMP],[STATUS],[TEMPORARY],
  [GENERATED],[SECONDARY] FROM #uc1_insert_batch;
 SET @affected_rows=@@ROWCOUNT;';
        EXEC #bench_action @RunId=@run_id,@ActionKind='INSERT',
             @TargetTable=@write_table,@ActionSql=@sql;
        SET @batch+=1;
    END;
    IF EXISTS(SELECT 1 FROM #bench_actions WHERE run_id=@run_id AND
              target_table=@write_table AND action_kind='INSERT' AND affected_rows<>1000)
        THROW 51109,'INSERT batch affected unexpected rows.',1;
    SET @batch=0;
    WHILE @batch<20
    BEGIN
        SET @sql=N'UPDATE '+@qualified+N' SET [OWNER]=N''UC1_UPDATED''
 WHERE [ID] BETWEEN '+CONVERT(nvarchar(20),@batch*1000+1)+N' AND '
 +CONVERT(nvarchar(20),(@batch+1)*1000)+N';
 SET @affected_rows=@@ROWCOUNT;';
        EXEC #bench_action @RunId=@run_id,@ActionKind='UPDATE',
             @TargetTable=@write_table,@ActionSql=@sql;
        SET @batch+=1;
    END;
    IF EXISTS(SELECT 1 FROM #bench_actions WHERE run_id=@run_id AND
              target_table=@write_table AND action_kind='UPDATE' AND affected_rows<>1000)
        THROW 51110,'UPDATE batch affected unexpected rows.',1;
    FETCH NEXT FROM write_cursor INTO @configuration,@write_table;
END;
CLOSE write_cursor;
DEALLOCATE write_cursor;

SELECT N'WRITE_RAW' AS section,run_id,action_kind,target_table,
       ROW_NUMBER() OVER(PARTITION BY action_kind,target_table ORDER BY measured_at_utc) AS batch,
       elapsed_ms,affected_rows,rows_per_second,measured_at_utc
FROM #bench_actions WHERE run_id=@run_id AND action_kind IN('INSERT','UPDATE')
ORDER BY target_table,action_kind,batch;
;WITH w AS (
 SELECT target_table,action_kind,elapsed_ms,affected_rows,
        PERCENTILE_CONT(.5) WITHIN GROUP(ORDER BY elapsed_ms)
          OVER(PARTITION BY target_table,action_kind) AS median_ms,
        PERCENTILE_CONT(.95) WITHIN GROUP(ORDER BY elapsed_ms)
          OVER(PARTITION BY target_table,action_kind) AS p95_ms
 FROM #bench_actions WHERE run_id=@run_id AND action_kind IN('INSERT','UPDATE')
)
SELECT N'WRITE_SUMMARY' AS section,target_table,action_kind,
       COUNT(*) AS batches,SUM(affected_rows) AS affected_rows,
       SUM(elapsed_ms) AS total_elapsed_ms,
       CONVERT(decimal(19,3),MAX(median_ms)) AS median_ms,
       CONVERT(decimal(19,3),MAX(p95_ms)) AS p95_ms,
       CASE WHEN action_kind='INSERT' AND SUM(elapsed_ms)>0
            THEN CONVERT(decimal(20,3),SUM(affected_rows)*1000.0/SUM(elapsed_ms))
            ELSE NULL END AS rows_per_second
FROM w GROUP BY target_table,action_kind ORDER BY target_table,action_kind;

SELECT N'FINAL_COUNTS' AS section,
 (SELECT COUNT_BIG(*) FROM dbo.DEMO_BIG_TABLE_100K) AS source_rows,
 (SELECT COUNT_BIG(*) FROM dbo.UC1_Bench_100K) AS read_copy_rows,
 (SELECT COUNT_BIG(*) FROM dbo.UC1_Write_A_100K) AS write_a_rows,
 (SELECT COUNT_BIG(*) FROM dbo.UC1_Write_B_100K) AS write_b_rows,
 (SELECT COUNT_BIG(*) FROM dbo.UC1_Write_C_100K) AS write_c_rows;
SELECT N'RUN_COMPLETE' AS section,@run_id AS run_id,N'PASS' AS status;
