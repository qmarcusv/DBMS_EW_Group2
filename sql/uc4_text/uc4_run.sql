/* Run after uc4_setup.sql, as one file in SSMS or sqlcmd -b.
   Read timer covers server-side materialization of every DOC_ID to JSON.
   2 warmups and 25 measured executions per query/config. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF (SELECT COUNT_BIG(*) FROM dbo.UC4_Read_A)<>10000 OR
   (SELECT COUNT_BIG(*) FROM dbo.UC4_Read_C)<>10000 OR
   (SELECT COUNT_BIG(*) FROM dbo.UC4_Write_A)<>10000 OR
   (SELECT COUNT_BIG(*) FROM dbo.UC4_Write_C)<>10000 OR
   CONVERT(bigint,OBJECTPROPERTYEX(OBJECT_ID(N'dbo.UC4_Read_C'),N'TableFulltextItemCount'))<>10000
 THROW 54100,'Run successful UC4 setup first',1;
DECLARE @run uniqueidentifier=NEWID(),@q varchar(8),@term nvarchar(40),@search nvarchar(100),@config char(1),
 @table sysname,@where nvarchar(200),@sql nvarchar(max),@ids nvarchar(max),@payload nvarchar(max),
 @start datetime2(7),@ms decimal(19,3),@i int,@count bigint,@expected bigint,@sum bigint,
 @expected_sum bigint,@affected int,@replacement nvarchar(max),@target bigint,@visible bit=0,
 @polls int=0;
DECLARE @queries TABLE(query_id varchar(8),term nvarchar(40));
INSERT @queries VALUES('K_HIGH',N'election'),('K_MED',N'climate'),('K_LOW',N'bitcoin'),
 ('P_HIGH',N'white house'),('P_MED',N'climate change'),('P_LOW',N'stock market');
DECLARE @reads TABLE(config char(1),query_id varchar(8),iteration int,elapsed_ms decimal(19,3),matched_rows bigint);
DECLARE @writes TABLE(config char(1),kind varchar(8),iteration int,elapsed_ms decimal(19,3),affected int);
SELECT N'RUN_CONTEXT' section,@run run_id,@@SPID session_id,
 N'T-SQL server timer around complete DOC_ID JSON materialization; 2 warmups; 25 samples' timing_boundary;

DECLARE query_cursor CURSOR LOCAL FAST_FORWARD FOR SELECT query_id,term FROM @queries;
OPEN query_cursor; FETCH NEXT FROM query_cursor INTO @q,@term;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @search=N'"'+@term+N'"';
 DECLARE config_cursor CURSOR LOCAL FAST_FORWARD FOR SELECT config FROM (VALUES('A'),('C'))x(config);
 OPEN config_cursor; FETCH NEXT FROM config_cursor INTO @config;
 WHILE @@FETCH_STATUS=0
 BEGIN
  SET @table=CASE WHEN @config='A' THEN N'dbo.UC4_Read_A' ELSE N'dbo.UC4_Read_C' END;
  SET @where=CASE WHEN @config='A' THEN N'BODY LIKE N''%''+@term+N''%'''
    ELSE N'CONTAINS(BODY,@search,LANGUAGE 1033)' END;
  SET @sql=N'SELECT @ids=STRING_AGG(CONVERT(nvarchar(max),DOC_ID),N'','') WITHIN GROUP(ORDER BY DOC_ID),
     @cnt=COUNT_BIG(*),@sum=SUM(DOC_ID) FROM '+@table+N' WHERE '+@where;
  EXEC sys.sp_executesql @sql,N'@term nvarchar(40),@search nvarchar(100),@ids nvarchar(max) OUTPUT,@cnt bigint OUTPUT,@sum bigint OUTPUT',
   @term=@term,@search=@search,@ids=@ids OUTPUT,@cnt=@expected OUTPUT,@sum=@expected_sum OUTPUT;
  IF @expected=0 THROW 54101,'Empty UC4 query result',1;
  SELECT N'READ_IDS' section,@q query_id,@config config,@expected matched_rows,@ids doc_ids;
  SET @sql=N'SELECT @payload=(SELECT DOC_ID FROM '+@table+N' WHERE '+@where+N' FOR JSON PATH)';
  SET @i=1;
  WHILE @i<=27
  BEGIN
   SET @start=SYSUTCDATETIME();
   EXEC sys.sp_executesql @sql,N'@term nvarchar(40),@search nvarchar(100),@payload nvarchar(max) OUTPUT',
    @term=@term,@search=@search,@payload=@payload OUTPUT;
   SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
   SELECT @count=COUNT_BIG(*),@sum=SUM(DOC_ID) FROM OPENJSON(@payload) WITH(DOC_ID bigint '$.DOC_ID');
   IF @count<>@expected OR @sum<>@expected_sum THROW 54102,'Timed query result changed',1;
   IF @i>2 INSERT @reads VALUES(@config,@q,@i-2,@ms,@count);
   SET @i+=1;
  END;
  FETCH NEXT FROM config_cursor INTO @config;
 END;
 CLOSE config_cursor;DEALLOCATE config_cursor;
 FETCH NEXT FROM query_cursor INTO @q,@term;
END;
CLOSE query_cursor;DEALLOCATE query_cursor;
SELECT N'READ_RAW' section,config,query_id,iteration,elapsed_ms,matched_rows FROM @reads ORDER BY query_id,config,iteration;
WITH s AS (SELECT DISTINCT config,query_id,matched_rows,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY config,query_id) median_ms,
 PERCENTILE_CONT(0.95) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY config,query_id) p95_ms
 FROM @reads)
SELECT N'READ_SUMMARY' section,config,query_id,matched_rows,median_ms,p95_ms FROM s ORDER BY query_id,config;

SELECT TOP(1) @replacement=BODY FROM dbo.UC4_Seed_10K ORDER BY DOC_ID;
CREATE TABLE #uc4_update(DOC_ID bigint PRIMARY KEY,batch int NOT NULL);
WITH chosen AS (SELECT TOP(200) DOC_ID FROM dbo.UC4_Seed_10K ORDER BY DOC_ID DESC),
 ranked AS (SELECT DOC_ID,ROW_NUMBER() OVER(ORDER BY DOC_ID DESC) n FROM chosen)
INSERT #uc4_update SELECT DOC_ID,CONVERT(int,(n-1)/20)+1 FROM ranked;
IF (SELECT COUNT(*) FROM #uc4_update)<>200 THROW 54103,'Write targets missing',1;
DECLARE config_cursor CURSOR LOCAL FAST_FORWARD FOR SELECT config FROM (VALUES('A'),('C'))x(config);
OPEN config_cursor; FETCH NEXT FROM config_cursor INTO @config;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @table=CASE WHEN @config='A' THEN N'dbo.UC4_Write_A' ELSE N'dbo.UC4_Write_C' END;
 SET @i=1;
 WHILE @i<=10
 BEGIN
  SET @sql=N'WITH picked AS (SELECT TOP(20) DOC_ID,TITLE,BODY,SUBJECT,RAW_DATE,SOURCE_FILE,SOURCE_ROW,
    ROW_NUMBER() OVER(ORDER BY DOC_ID) rn FROM dbo.UC4_Seed_10K ORDER BY DOC_ID)
    INSERT '+@table+N' (DOC_ID,TITLE,BODY,SUBJECT,RAW_DATE,SOURCE_FILE,SOURCE_ROW)
    SELECT 1000000+(@batch-1)*20+rn,TITLE,BODY,SUBJECT,RAW_DATE,SOURCE_FILE,SOURCE_ROW FROM picked;
    SET @affected=@@ROWCOUNT;';
  SET @start=SYSUTCDATETIME();
  EXEC sys.sp_executesql @sql,N'@batch int,@affected int OUTPUT',@batch=@i,@affected=@affected OUTPUT;
  SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
  IF @affected<>20 THROW 54104,'Insert count mismatch',1;
  INSERT @writes VALUES(@config,'INSERT',@i,@ms,@affected);
  SET @i+=1;
 END;
 SET @i=1;
 WHILE @i<=10
 BEGIN
  SET @sql=N'UPDATE w SET BODY=@body FROM '+@table+N' w JOIN #uc4_update u ON u.DOC_ID=w.DOC_ID
    WHERE u.batch=@batch; SET @affected=@@ROWCOUNT;';
  SET @start=SYSUTCDATETIME();
  EXEC sys.sp_executesql @sql,N'@body nvarchar(max),@batch int,@affected int OUTPUT',
   @body=@replacement,@batch=@i,@affected=@affected OUTPUT;
  SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
  IF @affected<>20 THROW 54105,'Update count mismatch',1;
  INSERT @writes VALUES(@config,'UPDATE',@i,@ms,@affected);
  SET @i+=1;
 END;
 FETCH NEXT FROM config_cursor INTO @config;
END;
CLOSE config_cursor;DEALLOCATE config_cursor;
SELECT N'WRITE_RAW' section,config,kind,iteration,elapsed_ms,affected FROM @writes ORDER BY kind,config,iteration;
WITH s AS (SELECT DISTINCT config,kind,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY config,kind) median_ms,
 PERCENTILE_CONT(0.95) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY config,kind) p95_ms,
 SUM(elapsed_ms) OVER(PARTITION BY config,kind) total_ms FROM @writes)
SELECT N'WRITE_SUMMARY' section,config,kind,200 rows,median_ms,p95_ms,
 CASE WHEN kind='INSERT' AND total_ms>0 THEN 200000.0/total_ms ELSE NULL END rows_per_second FROM s ORDER BY kind,config;
IF (SELECT COUNT_BIG(*) FROM dbo.UC4_Write_A)<>10200 OR (SELECT COUNT_BIG(*) FROM dbo.UC4_Write_C)<>10200
 THROW 54106,'Write copy final count mismatch',1;

SELECT TOP(1) @replacement=BODY FROM dbo.UC4_Seed_10K WHERE BODY LIKE N'%bitcoin%' ORDER BY DOC_ID;
SELECT TOP(1) @target=DOC_ID FROM dbo.UC4_Write_C WHERE BODY NOT LIKE N'%bitcoin%' ORDER BY DOC_ID;
IF @replacement IS NULL OR @target IS NULL THROW 54107,'Freshness payload missing',1;
SET @start=SYSUTCDATETIME();
UPDATE dbo.UC4_Write_C SET BODY=@replacement WHERE DOC_ID=@target;
IF @@ROWCOUNT<>1 THROW 54108,'Freshness update failed',1;
WHILE @polls<1200
BEGIN
 IF EXISTS(SELECT 1 FROM dbo.UC4_Write_C WHERE DOC_ID=@target AND CONTAINS(BODY,N'"bitcoin"',LANGUAGE 1033))
 BEGIN SET @visible=1; BREAK; END;
 WAITFOR DELAY '00:00:00.050'; SET @polls+=1;
END;
SELECT N'FRESHNESS' section,@target doc_id,@visible visible,@polls polls,
 CONVERT(decimal(19,3),DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0) elapsed_ms;
IF @visible<>1 THROW 54109,'SQL full-text freshness timeout',1;
SELECT N'STORAGE' section,N'C' config,FULLTEXTCATALOGPROPERTY(N'UC4_FT_Read',N'IndexSize') read_catalog_logical_mb,
 FULLTEXTCATALOGPROPERTY(N'UC4_FT_Write',N'IndexSize') write_catalog_logical_mb;
SELECT N'RUN_COMPLETE' section,N'PASS' status;
