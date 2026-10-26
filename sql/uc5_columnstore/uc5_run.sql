/* Phase 6 replacement / UC5. SQL Server only. Run as one SSMS or sqlcmd file.
   B=heap rowstore, C=clustered columnstore; A=N/A. Both are independent
   1M-row copies of the same source, with no optional secondary indexes.
   Timed SELECT results fully consumed by server-side JSON materialization.
   Saves raw output; cleanup is separate. No benchmark_core session needed. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
SET XACT_ABORT ON;
DECLARE @run uniqueidentifier=NEWID(),@source sysname=N'dbo.DEMO_BIG_TABLE_1000K',
 @config char(1),@table sysname,@sql nvarchar(max),@kind varchar(8),
 @start datetime2(7),@ms decimal(19,3),@n bigint,@expected bigint,
 @fp int,@expected_fp int,@expected_agg bigint,@fp_agg int,@i int,@bytes bigint;
DECLARE @raw TABLE(config char(1),query_id varchar(8),iteration int,
 elapsed_ms decimal(19,3),matched_rows bigint,fingerprint int);
DECLARE @writes TABLE(config char(1),kind varchar(8),iteration int,
 elapsed_ms decimal(19,3),affected bigint);
DECLARE @build TABLE(config char(1),elapsed_ms decimal(19,3));
SELECT TOP(0) * INTO #uc5_insert FROM dbo.DEMO_BIG_TABLE_1000K;
CREATE TABLE #uc5_update(ID bigint PRIMARY KEY,batch int NOT NULL);
IF (SELECT COUNT_BIG(*) FROM dbo.DEMO_BIG_TABLE_1000K)<>1000000
 THROW 55000,'UC5 source count changed.',1;
IF EXISTS(SELECT 1 FROM sys.tables WHERE schema_id=SCHEMA_ID(N'dbo') AND name LIKE N'UC5[_]%')
 THROW 55001,'UC5 disposable tables already exist; save evidence then cleanup.',1;
SELECT N'RUN_CONTEXT' section,@run run_id,@@SPID session_id,DB_NAME() database_name,
 N'B=heap rowstore; C=clustered columnstore; 2 warmups + 25 repetitions' design;

/* Prepare both copies before indexing or timing. */
SELECT * INTO dbo.UC5_Rowstore FROM dbo.DEMO_BIG_TABLE_1000K;
SELECT * INTO dbo.UC5_Columnstore FROM dbo.DEMO_BIG_TABLE_1000K;
IF (SELECT COUNT_BIG(*) FROM dbo.UC5_Rowstore)<>1000000 OR
   (SELECT COUNT_BIG(*) FROM dbo.UC5_Columnstore)<>1000000
 THROW 55002,'UC5 copy parity failed.',1;
SELECT N'COPY_READY' section,N'B' config,N'UC5_Rowstore' table_name,COUNT_BIG(*) rows FROM dbo.UC5_Rowstore
UNION ALL SELECT N'COPY_READY',N'C',N'UC5_Columnstore',COUNT_BIG(*) FROM dbo.UC5_Columnstore;
SET @start=SYSUTCDATETIME();
CREATE CLUSTERED COLUMNSTORE INDEX CCI_UC5 ON dbo.UC5_Columnstore;
SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
INSERT @build VALUES('C',@ms);

/* Exact result checks: group count + numeric sum, and complete point projection. */
SELECT @expected=COUNT_BIG(*),@expected_fp=CHECKSUM_AGG(BINARY_CHECKSUM(OBJECT_TYPE,n,s))
FROM (SELECT OBJECT_TYPE,COUNT_BIG(*) n,SUM(COALESCE(OBJECT_ID,CONVERT(bigint,0))) s
      FROM dbo.DEMO_BIG_TABLE_1000K GROUP BY OBJECT_TYPE) x;
SET @expected_agg=@expected;SET @fp_agg=@expected_fp;
SELECT N'QUERY_EXPECTED' section,N'AGG' query_id,@expected matched_rows,@expected_fp fingerprint;

DECLARE configs CURSOR LOCAL FAST_FORWARD FOR SELECT v.c FROM (VALUES('B'),('C'))v(c);
OPEN configs;FETCH NEXT FROM configs INTO @config;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @table=CASE WHEN @config='B' THEN N'UC5_Rowstore' ELSE N'UC5_Columnstore' END;
 SELECT N'STORAGE' section,@config config,ix.name index_name,ix.type_desc,
   SUM(ps.row_count) approximate_rows,
   SUM(ps.used_page_count)*CONVERT(bigint,8192) used_bytes,
   SUM(ps.reserved_page_count)*CONVERT(bigint,8192) reserved_bytes
 FROM sys.indexes ix JOIN sys.dm_db_partition_stats ps ON ps.object_id=ix.object_id AND ps.index_id=ix.index_id
 WHERE ix.object_id=OBJECT_ID(N'dbo.'+@table)
 GROUP BY ix.name,ix.type_desc;

 SET @sql=N'DECLARE @payload nvarchar(max);
 SELECT @payload=(SELECT OBJECT_TYPE,COUNT_BIG(*) n,SUM(COALESCE(OBJECT_ID,CONVERT(bigint,0))) s
 FROM dbo.'+QUOTENAME(@table)+N' GROUP BY OBJECT_TYPE FOR JSON PATH);
 SELECT @cnt=COUNT_BIG(*),@hash=CHECKSUM_AGG(BINARY_CHECKSUM(OBJECT_TYPE,n,s))
 FROM OPENJSON(@payload) WITH (OBJECT_TYPE nvarchar(64) ''$.OBJECT_TYPE'',n bigint ''$.n'',s bigint ''$.s'')';
 SET @i=1;
 WHILE @i<=27
 BEGIN
  SET @start=SYSUTCDATETIME();
  EXEC sys.sp_executesql @sql,N'@cnt bigint OUTPUT,@hash int OUTPUT',@cnt=@n OUTPUT,@hash=@fp OUTPUT;
  SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
  IF @n<>@expected_agg OR ISNULL(@fp,0)<>ISNULL(@fp_agg,0)
   THROW 55003,'UC5 aggregation result parity failed.',1;
  IF @i>2 INSERT @raw VALUES(@config,'AGG',@i-2,@ms,@n,@fp);
  SET @i+=1;
 END;

 SET @sql=N'SELECT @cnt=COUNT_BIG(*),@hash=CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_NAME,OBJECT_TYPE))
 FROM '+@source+N' WHERE ID=1';
 EXEC sys.sp_executesql @sql,N'@cnt bigint OUTPUT,@hash int OUTPUT',@cnt=@expected OUTPUT,@hash=@expected_fp OUTPUT;
 IF @expected<>1 THROW 55004,'UC5 point sample no longer unique.',1;
 SET @sql=N'DECLARE @payload nvarchar(max);SELECT @payload=(SELECT ID,OWNER,OBJECT_NAME,OBJECT_TYPE
 FROM dbo.'+QUOTENAME(@table)+N' WHERE ID=1 FOR JSON PATH);
 SELECT @cnt=COUNT_BIG(*),@hash=CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_NAME,OBJECT_TYPE))
 FROM OPENJSON(@payload) WITH (ID bigint ''$.ID'',OWNER nvarchar(128) ''$.OWNER'',
 OBJECT_NAME nvarchar(256) ''$.OBJECT_NAME'',OBJECT_TYPE nvarchar(64) ''$.OBJECT_TYPE'')';
 SET @i=1;
 WHILE @i<=27
 BEGIN
  SET @start=SYSUTCDATETIME();
  EXEC sys.sp_executesql @sql,N'@cnt bigint OUTPUT,@hash int OUTPUT',@cnt=@n OUTPUT,@hash=@fp OUTPUT;
  SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
  IF @n<>@expected OR ISNULL(@fp,0)<>ISNULL(@expected_fp,0)
   THROW 55005,'UC5 point result parity failed.',1;
  IF @i>2 INSERT @raw VALUES(@config,'POINT',@i-2,@ms,@n,@fp);
  SET @i+=1;
 END;
 FETCH NEXT FROM configs INTO @config;
END;
CLOSE configs;DEALLOCATE configs;

/* Capture initial rowgroup state before small incremental writes. */
SELECT N'ROWGROUP_BEFORE' section,state_desc,COUNT(*) groups,SUM(total_rows) total_rows,
 SUM(deleted_rows) deleted_rows
FROM sys.dm_db_column_store_row_group_physical_stats
WHERE object_id=OBJECT_ID(N'dbo.UC5_Columnstore')
GROUP BY state_desc;

INSERT #uc5_insert SELECT TOP(20) * FROM dbo.DEMO_BIG_TABLE_1000K ORDER BY ID;
WITH picked AS (SELECT TOP(200) ID FROM dbo.DEMO_BIG_TABLE_1000K ORDER BY ID DESC)
INSERT #uc5_update SELECT ID,CONVERT(int,(ROW_NUMBER() OVER(ORDER BY ID)-1)/20+1) FROM picked;
IF (SELECT COUNT(*) FROM #uc5_insert)<>20 OR (SELECT COUNT(*) FROM #uc5_update)<>200
 THROW 55006,'UC5 write samples missing.',1;

DECLARE configs CURSOR LOCAL FAST_FORWARD FOR SELECT v.c FROM (VALUES('B'),('C'))v(c);
OPEN configs;FETCH NEXT FROM configs INTO @config;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @table=CASE WHEN @config='B' THEN N'UC5_Rowstore' ELSE N'UC5_Columnstore' END;
 SET @i=1;
 WHILE @i<=10
 BEGIN
  /* Identical logical rows; no uniqueness constraint on either copy. */
  SET @sql=N'INSERT dbo.'+QUOTENAME(@table)+N' SELECT * FROM #uc5_insert; SELECT @cnt=@@ROWCOUNT';
  SET @start=SYSUTCDATETIME();EXEC sys.sp_executesql @sql,N'@cnt bigint OUTPUT',@cnt=@n OUTPUT;
  SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
  IF @n<>20 THROW 55007,'UC5 INSERT row count mismatch.',1;
  INSERT @writes VALUES(@config,'INSERT',@i,@ms,@n);
  SET @sql=N'UPDATE t SET OBJECT_NAME=CONCAT(t.OBJECT_NAME,N''_UC5'') FROM dbo.'+QUOTENAME(@table)+
   N' t JOIN #uc5_update u ON t.ID=u.ID WHERE u.batch='+CONVERT(nvarchar(10),@i)+N';SELECT @cnt=@@ROWCOUNT';
  SET @start=SYSUTCDATETIME();EXEC sys.sp_executesql @sql,N'@cnt bigint OUTPUT',@cnt=@n OUTPUT;
  SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
  IF @n<>20 THROW 55008,'UC5 UPDATE row count mismatch.',1;
  INSERT @writes VALUES(@config,'UPDATE',@i,@ms,@n);
  SET @i+=1;
 END;
 SET @sql=N'SELECT @cnt=COUNT_BIG(*) FROM dbo.'+QUOTENAME(@table);
 EXEC sys.sp_executesql @sql,N'@cnt bigint OUTPUT',@cnt=@n OUTPUT;
 IF @n<>1000200 THROW 55009,'UC5 final copy count wrong.',1;
 SELECT N'WRITE_FINAL' section,@config config,@n rows;
 FETCH NEXT FROM configs INTO @config;
END;
CLOSE configs;DEALLOCATE configs;
SELECT N'ROWGROUP_AFTER' section,state_desc,COUNT(*) groups,SUM(total_rows) total_rows,
 SUM(deleted_rows) deleted_rows
FROM sys.dm_db_column_store_row_group_physical_stats
WHERE object_id=OBJECT_ID(N'dbo.UC5_Columnstore')
GROUP BY state_desc;
SELECT N'READ_RAW' section,* FROM @raw ORDER BY config,query_id,iteration;
SELECT DISTINCT N'READ_SUMMARY' section,config,query_id,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY config,query_id) p50_ms,
 PERCENTILE_CONT(0.95) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY config,query_id) p95_ms,
 MAX(matched_rows) OVER(PARTITION BY config,query_id) matched_rows FROM @raw;
SELECT N'INDEX_BUILD' section,* FROM @build;
SELECT N'WRITE_RAW' section,* FROM @writes ORDER BY config,kind,iteration;
SELECT DISTINCT N'WRITE_SUMMARY' section,config,kind,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY config,kind) p50_ms,
 PERCENTILE_CONT(0.95) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY config,kind) p95_ms,
 SUM(affected) OVER(PARTITION BY config,kind)*1000.0/
 NULLIF(SUM(elapsed_ms) OVER(PARTITION BY config,kind),0) rows_per_second FROM @writes;
SELECT N'RUN_COMPLETE' section,@run run_id,N'PASS' status;
