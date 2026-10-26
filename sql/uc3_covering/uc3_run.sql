/* Phase 5 / UC3. Run this entire T-SQL file in SSMS or sqlcmd.
   Creates only dbo.UC3_* disposable copies; source tables are read only.
   Save output before running uc3_cleanup.sql. No session-local core required.
   Timed read materializes the complete projection as JSON in server memory;
   diagnostics execute the plain SELECT separately. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @run uniqueidentifier=NEWID(),@scale varchar(5),@source sysname,@read sysname,
 @write sysname,@config char(1),@query varchar(8),@lo bigint,@hi bigint,
 @sql nvarchar(max),@start datetime2(7),@ms decimal(19,3),@n bigint,@expected bigint,
 @fp int,@expected_fp int,@i int,@rows bigint,@bytes bigint;
DECLARE @raw TABLE(scale varchar(5),config char(1),query_id varchar(8),iteration int,
 elapsed_ms decimal(19,3),matched_rows bigint,fingerprint int);
DECLARE @writes TABLE(scale varchar(5),config char(1),kind varchar(8),iteration int,
 elapsed_ms decimal(19,3),affected bigint);
DECLARE @build TABLE(scale varchar(5),config char(1),elapsed_ms decimal(19,3),used_bytes bigint);
CREATE TABLE #uc3_insert(ID bigint,OWNER nvarchar(128),OBJECT_NAME nvarchar(256),
 OBJECT_TYPE nvarchar(64),OBJECT_ID bigint);
CREATE TABLE #uc3_update(ID bigint PRIMARY KEY,batch int NOT NULL);

IF (SELECT COUNT_BIG(*) FROM dbo.DEMO_BIG_TABLE_100K)<>100000 OR
   (SELECT COUNT_BIG(*) FROM dbo.DEMO_BIG_TABLE_1000K)<>1000000
 THROW 53000,'UC3 source row count changed.',1;
IF EXISTS(SELECT 1 FROM sys.tables WHERE schema_id=SCHEMA_ID(N'dbo') AND name LIKE N'UC3[_]%')
 THROW 53001,'UC3 disposable tables exist; save evidence before cleanup.',1;
SELECT N'RUN_CONTEXT' section,@run run_id,@@SPID session_id,DB_NAME() database_name,
 N'T-SQL batch elapsed, JSON materialization of full projection, 2 warmups, 25 samples' timing_boundary;

DECLARE scales CURSOR LOCAL FAST_FORWARD FOR SELECT v.scale FROM (VALUES('100K'),('1000K'))v(scale);
OPEN scales; FETCH NEXT FROM scales INTO @scale;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @source=CASE WHEN @scale='100K' THEN N'dbo.DEMO_BIG_TABLE_100K' ELSE N'dbo.DEMO_BIG_TABLE_1000K' END;
 SET @rows=CASE WHEN @scale='100K' THEN 100000 ELSE 1000000 END;
 SET @read=N'UC3_Bench_'+@scale;
 SET @sql=N'SELECT * INTO dbo.'+QUOTENAME(@read)+N' FROM '+@source;
 EXEC sys.sp_executesql @sql;
 SET @sql=N'SELECT @out=COUNT_BIG(*) FROM dbo.'+QUOTENAME(@read);
 EXEC sys.sp_executesql @sql,N'@out bigint OUTPUT',@out=@n OUTPUT;
 IF @n<>@rows THROW 53002,'UC3 read copy row count mismatch.',1;
 SELECT N'COPY_READY' section,@scale scale,@read table_name,@n rows;

 /* Workloads: point (OBJECT_ID=16 AND ID=1); range bounds differ by scale. */
 DECLARE configs CURSOR LOCAL FAST_FORWARD FOR SELECT v.c FROM (VALUES('A'),('B'),('C'))v(c);
 OPEN configs;FETCH NEXT FROM configs INTO @config;
 WHILE @@FETCH_STATUS=0
 BEGIN
  IF @config IN ('B','C')
  BEGIN
   IF @config='C'
   BEGIN
    SET @sql=N'DROP INDEX IX_UC3_Key ON dbo.'+QUOTENAME(@read);
    EXEC sys.sp_executesql @sql;
    SET @sql=N'CREATE INDEX IX_UC3_Cover ON dbo.'+QUOTENAME(@read)+
     N' (OBJECT_ID) INCLUDE (ID,OWNER,OBJECT_NAME,OBJECT_TYPE)';
   END
   ELSE SET @sql=N'CREATE INDEX IX_UC3_Key ON dbo.'+QUOTENAME(@read)+N' (OBJECT_ID)';
   SET @start=SYSUTCDATETIME(); EXEC sys.sp_executesql @sql;
   SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
   SELECT @bytes=SUM(ps.used_page_count)*CONVERT(bigint,8192)
   FROM sys.dm_db_partition_stats ps JOIN sys.indexes ix ON ix.object_id=ps.object_id AND ix.index_id=ps.index_id
   WHERE ps.object_id=OBJECT_ID(N'dbo.'+@read) AND ix.name=CASE WHEN @config='B' THEN N'IX_UC3_Key' ELSE N'IX_UC3_Cover' END;
   INSERT @build VALUES(@scale,@config,@ms,@bytes);
  END;
  SELECT N'INDEX_INVENTORY' section,@scale scale,@config config,ix.name index_name,ix.type_desc,
    SUM(ps.used_page_count)*CONVERT(bigint,8192) used_bytes
  FROM sys.indexes ix JOIN sys.dm_db_partition_stats ps ON ps.object_id=ix.object_id AND ps.index_id=ix.index_id
  WHERE ix.object_id=OBJECT_ID(N'dbo.'+@read)
  GROUP BY ix.name,ix.type_desc;

  DECLARE queries CURSOR LOCAL FAST_FORWARD FOR SELECT v.q FROM (VALUES('POINT'),('SMALL'),('MEDIUM'))v(q);
  OPEN queries;FETCH NEXT FROM queries INTO @query;
  WHILE @@FETCH_STATUS=0
  BEGIN
   SET @lo=1;
   SET @hi=CASE WHEN @query='SMALL' THEN CASE WHEN @scale='100K' THEN 50 ELSE 5 END
                WHEN @query='MEDIUM' THEN CASE WHEN @scale='100K' THEN 1000 ELSE 200 END ELSE 16 END;
   SET @sql=N'SELECT @cnt=COUNT_BIG(*),@hash=CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_NAME,OBJECT_TYPE)) FROM '+@source+
    CASE WHEN @query='POINT' THEN N' WHERE OBJECT_ID=16 AND ID=1'
         ELSE N' WHERE OBJECT_ID BETWEEN 1 AND '+CONVERT(nvarchar(20),@hi) END;
   EXEC sys.sp_executesql @sql,N'@cnt bigint OUTPUT,@hash int OUTPUT',@cnt=@expected OUTPUT,@hash=@expected_fp OUTPUT;
   IF @expected=0 THROW 53003,'UC3 workload empty.',1;
   SELECT N'QUERY_SELECTIVITY' section,@scale scale,@config config,@query query_id,@hi upper_bound,
    @expected matched_rows,CONVERT(decimal(12,8),@expected*1.0/@rows) selectivity;
   /* The fixed projected columns are fully consumed inside each timed query.
      OPENJSON is outside the index access and identical in all configurations. */
   SET @sql=N'DECLARE @payload nvarchar(max); SELECT @payload=(SELECT ID,OWNER,OBJECT_NAME,OBJECT_TYPE FROM dbo.'+
    QUOTENAME(@read)+CASE WHEN @query='POINT' THEN N' WHERE OBJECT_ID=16 AND ID=1'
         ELSE N' WHERE OBJECT_ID BETWEEN 1 AND '+CONVERT(nvarchar(20),@hi) END+
    N' FOR JSON PATH); SELECT @cnt=COUNT_BIG(*),@hash=CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_NAME,OBJECT_TYPE))
       FROM OPENJSON(@payload) WITH (ID bigint ''$.ID'',OWNER nvarchar(128) ''$.OWNER'',
       OBJECT_NAME nvarchar(256) ''$.OBJECT_NAME'',OBJECT_TYPE nvarchar(64) ''$.OBJECT_TYPE'')';
   SET @i=1;
   WHILE @i<=27
   BEGIN
    SET @start=SYSUTCDATETIME();
    EXEC sys.sp_executesql @sql,N'@cnt bigint OUTPUT,@hash int OUTPUT',@cnt=@n OUTPUT,@hash=@fp OUTPUT;
    SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
    IF @n<>@expected OR ISNULL(@fp,0)<>ISNULL(@expected_fp,0) THROW 53004,'UC3 result parity failed.',1;
    IF @i>2 INSERT @raw VALUES(@scale,@config,@query,@i-2,@ms,@n,@fp);
    SET @i+=1;
   END;
   FETCH NEXT FROM queries INTO @query;
  END;
  CLOSE queries;DEALLOCATE queries;
  FETCH NEXT FROM configs INTO @config;
 END;
 CLOSE configs;DEALLOCATE configs;

 /* Preselect write payload and target IDs before any timed write. */
 TRUNCATE TABLE #uc3_insert;TRUNCATE TABLE #uc3_update;
 SET @sql=N'INSERT #uc3_insert SELECT TOP(20) ID,OWNER,OBJECT_NAME,OBJECT_TYPE,OBJECT_ID FROM '+@source+N' ORDER BY ID;
 WITH picked AS (SELECT TOP(200) ID FROM '+@source+N' ORDER BY ID DESC)
 INSERT #uc3_update SELECT ID,CONVERT(int,(ROW_NUMBER() OVER(ORDER BY ID)-1)/20+1) FROM picked;';
 EXEC sys.sp_executesql @sql;
 IF (SELECT COUNT(*) FROM #uc3_insert)<>20 OR (SELECT COUNT(*) FROM #uc3_update)<>200
  THROW 53005,'UC3 write sample preparation failed.',1;
 DECLARE configs CURSOR LOCAL FAST_FORWARD FOR SELECT v.c FROM (VALUES('A'),('B'),('C'))v(c);
 OPEN configs;FETCH NEXT FROM configs INTO @config;
 WHILE @@FETCH_STATUS=0
 BEGIN
  SET @write=N'UC3_Write_'+@config+'_'+@scale;
  SET @sql=N'SELECT * INTO dbo.'+QUOTENAME(@write)+N' FROM '+@source;
  EXEC sys.sp_executesql @sql;
  IF @config<>'A'
  BEGIN
   SET @sql=CASE WHEN @config='B' THEN N'CREATE INDEX IX_UC3_Key ON dbo.'+QUOTENAME(@write)+N' (OBJECT_ID)'
     ELSE N'CREATE INDEX IX_UC3_Cover ON dbo.'+QUOTENAME(@write)+N' (OBJECT_ID) INCLUDE (ID,OWNER,OBJECT_NAME,OBJECT_TYPE)' END;
   EXEC sys.sp_executesql @sql;
  END;
  SET @i=1;
  WHILE @i<=10
  BEGIN
   SET @sql=N'INSERT dbo.'+QUOTENAME(@write)+N' (ID,OWNER,OBJECT_NAME,OBJECT_TYPE,OBJECT_ID)
      SELECT ID+'+CONVERT(nvarchar(20),10000000+@i*20)+N',OWNER,OBJECT_NAME,OBJECT_TYPE,OBJECT_ID FROM #uc3_insert;
      SELECT @cnt=@@ROWCOUNT';
   SET @start=SYSUTCDATETIME(); EXEC sys.sp_executesql @sql,N'@cnt bigint OUTPUT',@cnt=@n OUTPUT;
   SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
   IF @n<>20 THROW 53006,'UC3 INSERT affected unexpected rows.',1;
   INSERT @writes VALUES(@scale,@config,'INSERT',@i,@ms,@n);
   SET @sql=N'UPDATE t SET OBJECT_NAME=CONCAT(t.OBJECT_NAME,N''_UC3'') FROM dbo.'+QUOTENAME(@write)+
      N' t JOIN #uc3_update u ON u.ID=t.ID WHERE u.batch='+CONVERT(nvarchar(10),@i)+N';SELECT @cnt=@@ROWCOUNT';
   SET @start=SYSUTCDATETIME(); EXEC sys.sp_executesql @sql,N'@cnt bigint OUTPUT',@cnt=@n OUTPUT;
   SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
   IF @n<>20 THROW 53007,'UC3 UPDATE affected unexpected rows.',1;
   INSERT @writes VALUES(@scale,@config,'UPDATE',@i,@ms,@n);
   SET @i+=1;
  END;
  SET @sql=N'SELECT @cnt=COUNT_BIG(*) FROM dbo.'+QUOTENAME(@write);
  EXEC sys.sp_executesql @sql,N'@cnt bigint OUTPUT',@cnt=@n OUTPUT;
  IF @n<>@rows+200 THROW 53008,'UC3 write copy final count wrong.',1;
  SELECT N'WRITE_FINAL' section,@scale scale,@config config,@n rows;
  FETCH NEXT FROM configs INTO @config;
 END;
 CLOSE configs;DEALLOCATE configs;
 FETCH NEXT FROM scales INTO @scale;
END;
CLOSE scales;DEALLOCATE scales;
SELECT N'READ_RAW' section,* FROM @raw ORDER BY scale,config,query_id,iteration;
SELECT DISTINCT N'READ_SUMMARY' section,scale,config,query_id,
 COUNT(*) OVER(PARTITION BY scale,config,query_id) repetitions,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY scale,config,query_id) p50_ms,
 PERCENTILE_CONT(0.95) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY scale,config,query_id) p95_ms,
 MAX(matched_rows) OVER(PARTITION BY scale,config,query_id) matched_rows FROM @raw;
SELECT N'INDEX_BUILD' section,* FROM @build;
SELECT N'WRITE_RAW' section,* FROM @writes ORDER BY scale,config,kind,iteration;
SELECT DISTINCT N'WRITE_SUMMARY' section,scale,config,kind,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY scale,config,kind) p50_ms,
 PERCENTILE_CONT(0.95) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY scale,config,kind) p95_ms,
 SUM(affected) OVER(PARTITION BY scale,config,kind)*1000.0/
 NULLIF(SUM(elapsed_ms) OVER(PARTITION BY scale,config,kind),0) rows_per_second FROM @writes;
SELECT N'RUN_COMPLETE' section,@run run_id,N'PASS' status;
