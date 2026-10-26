/* Phase 4 UC2. Native T-SQL; run as one entire SSMS query or sqlcmd file.
   Creates eight disposable heap copies. Never changes source tables.
   Refuses existing UC2 copies; run uc2_cleanup.sql only after saving output.
   A=no optional index; B=full; C=same keys/INCLUDE, TEMPORARY=Y filter.
   Read timings materialize the complete projected result in server memory.
*/
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
SET ANSI_NULLS ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET QUOTED_IDENTIFIER ON;
SET NUMERIC_ROUNDABORT OFF;

DECLARE @scale varchar(5),@source sysname,@read sysname,@write sysname,
 @config char(1),@filter nchar(1),@sql nvarchar(max),@start datetime2(7),
 @elapsed decimal(19,3),@count bigint,@expected bigint,@scale_rows bigint,@fp int,@expected_fp int,
 @run uniqueidentifier=NEWID(),@i int,@kind varchar(12),@batch int;
DECLARE @samples TABLE(scale varchar(5),config char(1),query_id varchar(12),
 iteration int,elapsed_ms decimal(19,3),rows bigint,fingerprint int);
DECLARE @writes TABLE(scale varchar(5),config char(1),kind varchar(12),
 iteration int,elapsed_ms decimal(19,3),affected bigint);
DECLARE @build TABLE(scale varchar(5),config char(1),elapsed_ms decimal(19,3),index_bytes bigint);
SELECT TOP(0) * INTO #uc2_insert_n FROM dbo.DEMO_BIG_TABLE_100K;
SELECT TOP(0) * INTO #uc2_insert_y FROM dbo.DEMO_BIG_TABLE_100K;
CREATE TABLE #uc2_update_n(ID bigint NOT NULL PRIMARY KEY,batch int NOT NULL);
CREATE TABLE #uc2_update_y(ID bigint NOT NULL PRIMARY KEY,batch int NOT NULL);

IF (SELECT COUNT_BIG(*) FROM dbo.DEMO_BIG_TABLE_100K)<>100000 OR
   (SELECT COUNT_BIG(*) FROM dbo.DEMO_BIG_TABLE_1000K)<>1000000
 THROW 52000,'UC2 source counts changed.',1;
IF EXISTS(SELECT 1 FROM sys.tables WHERE schema_id=SCHEMA_ID(N'dbo') AND name LIKE N'UC2[_]%')
 THROW 52001,'UC2 copies already exist; preserve evidence, then cleanup.',1;
SELECT N'RUN_CONTEXT' section,@run run_id,@@SPID spid,DB_NAME() database_name;

DECLARE scale_cursor CURSOR LOCAL FAST_FORWARD FOR SELECT scale FROM (VALUES('100K'),('1000K')) v(scale);
OPEN scale_cursor; FETCH NEXT FROM scale_cursor INTO @scale;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @source=CASE WHEN @scale='100K' THEN N'dbo.DEMO_BIG_TABLE_100K' ELSE N'dbo.DEMO_BIG_TABLE_1000K' END;
 SET @read=N'UC2_Bench_'+@scale;
 SET @scale_rows=CASE WHEN @scale='100K' THEN 100000 ELSE 1000000 END;
 SET @sql=N'SELECT * INTO dbo.'+QUOTENAME(@read)+N' FROM '+@source;
 EXEC sys.sp_executesql @sql;
 DECLARE config_cursor CURSOR LOCAL FAST_FORWARD FOR SELECT config FROM (VALUES('A'),('B'),('C')) v(config);
 OPEN config_cursor; FETCH NEXT FROM config_cursor INTO @config;
 WHILE @@FETCH_STATUS=0
 BEGIN
  SET @write=N'UC2_Write_'+@config+'_'+@scale;
  SET @sql=N'SELECT * INTO dbo.'+QUOTENAME(@write)+N' FROM '+@source;
  EXEC sys.sp_executesql @sql;
  SET @sql=N'SELECT @n=COUNT_BIG(*) FROM dbo.'+QUOTENAME(@write);
  EXEC sys.sp_executesql @sql,N'@n bigint OUTPUT',@n=@count OUTPUT;
  IF @count<>@scale_rows THROW 52002,'UC2 write copy parity failed.',1;
  SELECT N'COPY_READY' section,@scale scale,@config config,@count rows;
  FETCH NEXT FROM config_cursor INTO @config;
 END;
 CLOSE config_cursor; DEALLOCATE config_cursor;
 SET @sql=N'SELECT @n=COUNT_BIG(*) FROM dbo.'+QUOTENAME(@read);
 EXEC sys.sp_executesql @sql,N'@n bigint OUTPUT',@n=@count OUTPUT;
 IF @count<>@scale_rows THROW 52003,'UC2 read copy parity failed.',1;

 DECLARE config_cursor CURSOR LOCAL FAST_FORWARD FOR SELECT config FROM (VALUES('A'),('B'),('C')) v(config);
 OPEN config_cursor; FETCH NEXT FROM config_cursor INTO @config;
 WHILE @@FETCH_STATUS=0
 BEGIN
  IF @config='B'
  BEGIN
   SET @sql=N'CREATE INDEX IX_UC2_Full ON dbo.'+QUOTENAME(@read)+N' (OBJECT_TYPE,OBJECT_ID) INCLUDE (TEMPORARY)';
   SET @start=SYSUTCDATETIME(); EXEC sys.sp_executesql @sql;
   SET @elapsed=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
  END;
  IF @config='C'
  BEGIN
   SET @sql=N'DROP INDEX IX_UC2_Full ON dbo.'+QUOTENAME(@read);
   EXEC sys.sp_executesql @sql;
   SET @sql=N'CREATE INDEX IX_UC2_Filtered ON dbo.'+QUOTENAME(@read)+N' (OBJECT_TYPE,OBJECT_ID) INCLUDE (TEMPORARY) WHERE TEMPORARY=N''Y''';
   SET @start=SYSUTCDATETIME(); EXEC sys.sp_executesql @sql;
   SET @elapsed=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
  END;
  IF @config<>'A'
  BEGIN
   SELECT @count=SUM(p.used_page_count*8192)
   FROM sys.dm_db_partition_stats p JOIN sys.indexes ix ON ix.object_id=p.object_id AND ix.index_id=p.index_id
   WHERE p.object_id=OBJECT_ID(N'dbo.'+@read) AND ix.name=CASE WHEN @config='B' THEN N'IX_UC2_Full' ELSE N'IX_UC2_Filtered' END;
   INSERT @build VALUES(@scale,@config,@elapsed,@count);
  END;
  DECLARE filter_cursor CURSOR LOCAL FAST_FORWARD FOR SELECT filter FROM (VALUES(N'Y'),(N'N')) v(filter);
  OPEN filter_cursor; FETCH NEXT FROM filter_cursor INTO @filter;
  WHILE @@FETCH_STATUS=0
  BEGIN
   SET @sql=N'SELECT @n=COUNT_BIG(*),@f=CHECKSUM_AGG(BINARY_CHECKSUM(OBJECT_TYPE,OBJECT_ID,TEMPORARY)) FROM '+@source+
    N' WHERE TEMPORARY=@v AND OBJECT_TYPE=N''TABLE'' AND OBJECT_ID BETWEEN 1 AND 10000';
   EXEC sys.sp_executesql @sql,N'@v nchar(1),@n bigint OUTPUT,@f int OUTPUT',@v=@filter,@n=@expected OUTPUT,@f=@expected_fp OUTPUT;
   IF @expected=0 THROW 52004,'Empty UC2 workload.',1;
   SELECT N'QUERY_SELECTIVITY' section,@scale scale,@config config,@filter temporary,@expected matched_rows,
      CONVERT(decimal(12,8),@expected*1.0/CASE WHEN @scale='100K' THEN 100000 ELSE 1000000 END) selectivity;
   /* Literal value here tests filtered-index eligibility. Parameter variants
      are measured separately in uc2_diagnostics.sql. */
   SET @sql=N'DECLARE @payload nvarchar(max); SELECT @payload=(SELECT OBJECT_TYPE,OBJECT_ID,TEMPORARY FROM dbo.'+
      QUOTENAME(@read)+N' WHERE TEMPORARY=N'''+@filter+N''' AND OBJECT_TYPE=N''TABLE'' AND OBJECT_ID BETWEEN 1 AND 10000 FOR JSON PATH);
      SELECT @n=COUNT_BIG(*),@f=CHECKSUM_AGG(BINARY_CHECKSUM(OBJECT_TYPE,OBJECT_ID,TEMPORARY))
      FROM OPENJSON(@payload) WITH (OBJECT_TYPE nvarchar(128) ''$.OBJECT_TYPE'',OBJECT_ID bigint ''$.OBJECT_ID'',TEMPORARY nchar(1) ''$.TEMPORARY'')';
   SET @i=1;
   WHILE @i<=27
   BEGIN
    SET @start=SYSUTCDATETIME();
    EXEC sys.sp_executesql @sql,N'@n bigint OUTPUT,@f int OUTPUT',@n=@count OUTPUT,@f=@fp OUTPUT;
    SET @elapsed=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
    IF @count<>@expected OR @fp<>@expected_fp THROW 52005,'UC2 query result mismatch.',1;
    IF @i>2 INSERT @samples VALUES(@scale,@config,CASE WHEN @filter=N'Y' THEN 'INSIDE' ELSE 'OUTSIDE' END,@i-2,@elapsed,@count,@fp);
    SET @i+=1;
   END;
   FETCH NEXT FROM filter_cursor INTO @filter;
  END;
  CLOSE filter_cursor; DEALLOCATE filter_cursor;
  FETCH NEXT FROM config_cursor INTO @config;
 END;
 CLOSE config_cursor; DEALLOCATE config_cursor;

 /* Preselect identical insert rows and update IDs outside all timed writes. */
 TRUNCATE TABLE #uc2_insert_n; TRUNCATE TABLE #uc2_insert_y;
 TRUNCATE TABLE #uc2_update_n; TRUNCATE TABLE #uc2_update_y;
 SET @sql=N'INSERT #uc2_insert_n SELECT TOP(20) * FROM '+@source+N' WHERE TEMPORARY=N''N'' ORDER BY ID;
 INSERT #uc2_insert_y SELECT TOP(20) * FROM '+@source+N' WHERE TEMPORARY=N''Y'' ORDER BY ID;
 WITH ids AS (SELECT ID,ROW_NUMBER() OVER(ORDER BY ID DESC) rn FROM '+@source+N' WHERE TEMPORARY=N''N'')
 INSERT #uc2_update_n SELECT ID,CONVERT(int,(rn-1)/20+1) FROM ids WHERE rn<=200;
 WITH ids AS (SELECT ID,ROW_NUMBER() OVER(ORDER BY ID DESC) rn FROM '+@source+N' WHERE TEMPORARY=N''Y'')
 INSERT #uc2_update_y SELECT ID,CONVERT(int,(rn-1)/20+1) FROM ids WHERE rn<=200;';
 EXEC sys.sp_executesql @sql;
 IF (SELECT COUNT(*) FROM #uc2_insert_n)<>20 OR (SELECT COUNT(*) FROM #uc2_insert_y)<>20 OR
    (SELECT COUNT(*) FROM #uc2_update_n)<>200 OR (SELECT COUNT(*) FROM #uc2_update_y)<>200
  THROW 52008,'UC2 write sample preparation failed.',1;
 /* Independent same-size write copies. Index build is excluded from write timers. */
 DECLARE config_cursor CURSOR LOCAL FAST_FORWARD FOR SELECT config FROM (VALUES('A'),('B'),('C')) v(config);
 OPEN config_cursor; FETCH NEXT FROM config_cursor INTO @config;
 WHILE @@FETCH_STATUS=0
 BEGIN
  SET @write=N'UC2_Write_'+@config+'_'+@scale;
  IF @config='B'
  BEGIN
   SET @sql=N'CREATE INDEX IX_UC2_Full ON dbo.'+QUOTENAME(@write)+N' (OBJECT_TYPE,OBJECT_ID) INCLUDE (TEMPORARY)';EXEC sys.sp_executesql @sql;
  END;
  IF @config='C'
  BEGIN
   SET @sql=N'CREATE INDEX IX_UC2_Filtered ON dbo.'+QUOTENAME(@write)+N' (OBJECT_TYPE,OBJECT_ID) INCLUDE (TEMPORARY) WHERE TEMPORARY=N''Y''';EXEC sys.sp_executesql @sql;
  END;
  /* Each batch has 20 rows. Descending update IDs do not overlap the
     ascending insert sample, even for the 254-row Y subset at 100K. */
  DECLARE kind_cursor CURSOR LOCAL FAST_FORWARD FOR SELECT kind FROM (VALUES('INSERT_N'),('INSERT_Y'),('N_TO_Y'),('Y_TO_N')) v(kind);
  OPEN kind_cursor;FETCH NEXT FROM kind_cursor INTO @kind;
  WHILE @@FETCH_STATUS=0
  BEGIN
   SET @i=1;
   WHILE @i<=10
   BEGIN
    IF @kind LIKE 'INSERT%'
     SET @sql=N'INSERT dbo.'+QUOTENAME(@write)+N' SELECT * FROM #uc2_insert_'+LOWER(RIGHT(@kind,1))+N'; SELECT @n=@@ROWCOUNT';
    ELSE
     SET @sql=N'UPDATE t SET TEMPORARY=N'''+RIGHT(@kind,1)+N''' FROM dbo.'+QUOTENAME(@write)+
       N' t JOIN #uc2_update_'+LOWER(LEFT(@kind,1))+N' s ON s.ID=t.ID WHERE s.batch='+
       CONVERT(nvarchar(10),@i)+N' AND t.TEMPORARY=N'''+LEFT(@kind,1)+N'''; SELECT @n=@@ROWCOUNT';
    SET @start=SYSUTCDATETIME();
    EXEC sys.sp_executesql @sql,N'@n bigint OUTPUT',@n=@count OUTPUT;
    SET @elapsed=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
    IF @count<>20 THROW 52006,'UC2 write batch affected unexpected row count.',1;
    INSERT @writes VALUES(@scale,@config,@kind,@i,@elapsed,@count);
    SET @i+=1;
   END;
   FETCH NEXT FROM kind_cursor INTO @kind;
  END;
  CLOSE kind_cursor;DEALLOCATE kind_cursor;
  SET @sql=N'SELECT @n=COUNT_BIG(*) FROM dbo.'+QUOTENAME(@write);
  EXEC sys.sp_executesql @sql,N'@n bigint OUTPUT',@n=@count OUTPUT;
  IF @count<>@scale_rows+400 THROW 52007,'UC2 write copy final count wrong.',1;
  SELECT N'WRITE_FINAL' section,@scale scale,@config config,@count rows;
  FETCH NEXT FROM config_cursor INTO @config;
 END;
 CLOSE config_cursor;DEALLOCATE config_cursor;
 FETCH NEXT FROM scale_cursor INTO @scale;
END;
CLOSE scale_cursor;DEALLOCATE scale_cursor;

SELECT N'READ_RAW' section,* FROM @samples ORDER BY scale,config,query_id,iteration;
SELECT DISTINCT N'READ_SUMMARY' section,scale,config,query_id,
 COUNT(*) OVER(PARTITION BY scale,config,query_id) repetitions,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY scale,config,query_id) p50_ms,
 PERCENTILE_CONT(0.95) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY scale,config,query_id) p95_ms,
 MAX(rows) OVER(PARTITION BY scale,config,query_id) matched_rows FROM @samples;
SELECT N'INDEX_BUILD' section,* FROM @build;
SELECT N'WRITE_RAW' section,* FROM @writes ORDER BY scale,config,kind,iteration;
SELECT DISTINCT N'WRITE_SUMMARY' section,scale,config,kind,
 COUNT(*) OVER(PARTITION BY scale,config,kind) batches,
 SUM(affected) OVER(PARTITION BY scale,config,kind) rows,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY scale,config,kind) p50_ms,
 PERCENTILE_CONT(0.95) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY scale,config,kind) p95_ms,
 SUM(affected) OVER(PARTITION BY scale,config,kind)*1000.0/
 SUM(elapsed_ms) OVER(PARTITION BY scale,config,kind) rows_per_second FROM @writes;
SELECT N'RUN_COMPLETE' section,@run run_id,N'PASS' status;
