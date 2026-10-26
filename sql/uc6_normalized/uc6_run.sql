/* Phase 7 UC6. Run after uc6_setup.sql, as a whole file in SSMS or sqlcmd -b.
   SQL A has child PK(PARENT_ID,TAG); C adds IX(TAG,PARENT_ID).
   Each timer materializes every matching parent ID to JSON server-side. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF (SELECT COUNT_BIG(*) FROM dbo.UC6_Read_A_Parent)<>10000 OR
   (SELECT COUNT_BIG(*) FROM dbo.UC6_Read_C_Parent)<>10000 OR
   (SELECT COUNT_BIG(*) FROM dbo.UC6_Read_A_Tag)<>30471 OR
   (SELECT COUNT_BIG(*) FROM dbo.UC6_Read_C_Tag)<>30471
 THROW 56100,'Run successful UC6 setup first',1;
DECLARE @run uniqueidentifier=NEWID(),@q varchar(24),@tag1 nvarchar(128),@tag2 nvarchar(128),
 @required int,@expected_count bigint,@config char(1),@table sysname,@sql nvarchar(max),
 @ids nvarchar(max),@payload nvarchar(max),@count bigint,@sum bigint,@expected_sum bigint,
 @start datetime2(7),@ms decimal(19,3),@i int,@affected int,@affected_tags int;
DECLARE @queries TABLE(query_id varchar(24),tag1 nvarchar(128),tag2 nvarchar(128),required int,expected_count bigint);
INSERT @queries VALUES
 ('ONE_TABLE',N'type:TABLE',NULL,1,1247),
 ('TWO_SYS_TABLE',N'owner:SYS',N'type:TABLE',2,1125),
 ('ONE_TEMP_Y',N'temporary:Y',NULL,1,51),
 ('TWO_TABLE_TEMP_Y',N'type:TABLE',N'temporary:Y',2,41);
DECLARE @reads TABLE(config char(1),query_id varchar(24),iteration int,elapsed_ms decimal(19,3),matched_parents bigint);
DECLARE @writes TABLE(config char(1),kind varchar(8),iteration int,elapsed_ms decimal(19,3),affected int,tag_rows int);
SELECT N'RUN_CONTEXT' section,@run run_id,@@SPID session_id,
 N'T-SQL server timer, complete parent ID JSON; 2 warmups, 25 samples' timing_boundary;
DECLARE qcur CURSOR LOCAL FAST_FORWARD FOR SELECT query_id,tag1,tag2,required,expected_count FROM @queries;
OPEN qcur;FETCH NEXT FROM qcur INTO @q,@tag1,@tag2,@required,@expected_count;
WHILE @@FETCH_STATUS=0
BEGIN
 DECLARE ccur CURSOR LOCAL FAST_FORWARD FOR SELECT c FROM (VALUES('A'),('C'))x(c);
 OPEN ccur;FETCH NEXT FROM ccur INTO @config;
 WHILE @@FETCH_STATUS=0
 BEGIN
  SET @table=CASE WHEN @config='A' THEN N'dbo.UC6_Read_A_Tag' ELSE N'dbo.UC6_Read_C_Tag' END;
  SET @sql=N'SELECT @ids=STRING_AGG(CONVERT(nvarchar(max),PARENT_ID),N'','') WITHIN GROUP(ORDER BY PARENT_ID),
    @cnt=COUNT_BIG(*),@sum=SUM(PARENT_ID) FROM
    (SELECT PARENT_ID FROM '+@table+N' WHERE TAG IN(@tag1,@tag2)
     GROUP BY PARENT_ID HAVING COUNT(DISTINCT TAG)=@required) hits';
  EXEC sys.sp_executesql @sql,N'@tag1 nvarchar(128),@tag2 nvarchar(128),@required int,
    @ids nvarchar(max) OUTPUT,@cnt bigint OUTPUT,@sum bigint OUTPUT',
    @tag1=@tag1,@tag2=@tag2,@required=@required,@ids=@ids OUTPUT,
    @cnt=@count OUTPUT,@sum=@expected_sum OUTPUT;
  IF @count<>@expected_count THROW 56101,'UC6 source-defined count mismatch',1;
  SELECT N'READ_IDS' section,@q query_id,@config config,@count matched_parents,@ids parent_ids;
  SET @sql=N'SELECT @payload=(SELECT PARENT_ID FROM
    (SELECT PARENT_ID FROM '+@table+N' WHERE TAG IN(@tag1,@tag2)
     GROUP BY PARENT_ID HAVING COUNT(DISTINCT TAG)=@required) hits FOR JSON PATH)';
  SET @i=1;
  WHILE @i<=27
  BEGIN
   SET @start=SYSUTCDATETIME();
   EXEC sys.sp_executesql @sql,N'@tag1 nvarchar(128),@tag2 nvarchar(128),@required int,@payload nvarchar(max) OUTPUT',
     @tag1=@tag1,@tag2=@tag2,@required=@required,@payload=@payload OUTPUT;
   SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
   SELECT @count=COUNT_BIG(*),@sum=SUM(PARENT_ID) FROM OPENJSON(@payload) WITH(PARENT_ID bigint '$.PARENT_ID');
   IF @count<>@expected_count OR @sum<>@expected_sum THROW 56102,'Timed UC6 result changed',1;
   IF @i>2 INSERT @reads VALUES(@config,@q,@i-2,@ms,@count);
   SET @i+=1;
  END;
  FETCH NEXT FROM ccur INTO @config;
 END;
 CLOSE ccur;DEALLOCATE ccur;
 FETCH NEXT FROM qcur INTO @q,@tag1,@tag2,@required,@expected_count;
END;
CLOSE qcur;DEALLOCATE qcur;
SELECT N'READ_RAW' section,config,query_id,iteration,elapsed_ms,matched_parents FROM @reads ORDER BY query_id,config,iteration;
WITH s AS (SELECT DISTINCT config,query_id,matched_parents,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY config,query_id) median_ms,
 PERCENTILE_CONT(0.95) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY config,query_id) p95_ms FROM @reads)
SELECT N'READ_SUMMARY' section,config,query_id,matched_parents,median_ms,p95_ms FROM s ORDER BY query_id,config;

CREATE TABLE #uc6_targets(PARENT_ID bigint PRIMARY KEY,batch int NOT NULL);
WITH chosen AS (SELECT TOP(200) PARENT_ID FROM dbo.UC6_Seed_Parent ORDER BY PARENT_ID DESC),
 ranked AS (SELECT PARENT_ID,ROW_NUMBER() OVER(ORDER BY PARENT_ID DESC) rn FROM chosen)
INSERT #uc6_targets SELECT PARENT_ID,CONVERT(int,(rn-1)/20)+1 FROM ranked;
IF (SELECT COUNT(*) FROM #uc6_targets)<>200 THROW 56103,'UC6 write targets missing',1;
DECLARE ccur CURSOR LOCAL FAST_FORWARD FOR SELECT c FROM (VALUES('A'),('C'))x(c);
OPEN ccur;FETCH NEXT FROM ccur INTO @config;
WHILE @@FETCH_STATUS=0
BEGIN
 DECLARE @parent sysname=CASE WHEN @config='A' THEN N'dbo.UC6_Write_A_Parent' ELSE N'dbo.UC6_Write_C_Parent' END;
 SET @table=CASE WHEN @config='A' THEN N'dbo.UC6_Write_A_Tag' ELSE N'dbo.UC6_Write_C_Tag' END;
 SET @i=1;
 WHILE @i<=10
 BEGIN
  SET @sql=N'WITH picked AS (SELECT TOP(20) PARENT_ID,SOURCE_ROW,OWNER,OBJECT_TYPE,
    ROW_NUMBER() OVER(ORDER BY PARENT_ID) rn FROM dbo.UC6_Seed_Parent ORDER BY PARENT_ID)
    INSERT '+@parent+N'(PARENT_ID,SOURCE_ROW,OWNER,OBJECT_TYPE)
    SELECT 1000000+(@batch-1)*20+rn,SOURCE_ROW,OWNER,OBJECT_TYPE FROM picked;
    SET @affected=@@ROWCOUNT;
    WITH picked AS (SELECT TOP(20) PARENT_ID,ROW_NUMBER() OVER(ORDER BY PARENT_ID) rn
     FROM dbo.UC6_Seed_Parent ORDER BY PARENT_ID)
    INSERT '+@table+N'(PARENT_ID,TAG)
    SELECT 1000000+(@batch-1)*20+p.rn,t.TAG FROM picked p
     JOIN dbo.UC6_Seed_Tag t ON t.PARENT_ID=p.PARENT_ID;
    SET @affected_tags=@@ROWCOUNT;';
  SET @start=SYSUTCDATETIME();
  EXEC sys.sp_executesql @sql,N'@batch int,@affected int OUTPUT,@affected_tags int OUTPUT',
   @batch=@i,@affected=@affected OUTPUT,@affected_tags=@affected_tags OUTPUT;
  SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
  IF @affected<>20 OR @affected_tags<60 THROW 56104,'UC6 insert count mismatch',1;
  INSERT @writes VALUES(@config,'INSERT',@i,@ms,@affected,@affected_tags);
  SET @i+=1;
 END;
 SET @i=1;
 WHILE @i<=10
 BEGIN
  SET @sql=N'INSERT '+@table+N'(PARENT_ID,TAG)
    SELECT PARENT_ID,N''probe:added'' FROM #uc6_targets WHERE batch=@batch;
    SET @affected=@@ROWCOUNT;';
  SET @start=SYSUTCDATETIME();
  EXEC sys.sp_executesql @sql,N'@batch int,@affected int OUTPUT',@batch=@i,@affected=@affected OUTPUT;
  SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
  IF @affected<>20 THROW 56105,'UC6 membership update count mismatch',1;
  INSERT @writes VALUES(@config,'ADD_TAG',@i,@ms,@affected,@affected);
  SET @i+=1;
 END;
 FETCH NEXT FROM ccur INTO @config;
END;
CLOSE ccur;DEALLOCATE ccur;
SELECT N'WRITE_RAW' section,config,kind,iteration,elapsed_ms,affected,tag_rows FROM @writes ORDER BY kind,config,iteration;
WITH s AS (SELECT DISTINCT config,kind,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY config,kind) median_ms,
 PERCENTILE_CONT(0.95) WITHIN GROUP(ORDER BY elapsed_ms) OVER(PARTITION BY config,kind) p95_ms,
 SUM(elapsed_ms) OVER(PARTITION BY config,kind) total_ms FROM @writes)
SELECT N'WRITE_SUMMARY' section,config,kind,200 parents,median_ms,p95_ms,
 CASE WHEN kind='INSERT' AND total_ms>0 THEN 200000.0/total_ms ELSE NULL END parents_per_second
FROM s ORDER BY kind,config;
IF (SELECT COUNT_BIG(*) FROM dbo.UC6_Write_A_Parent)<>10200 OR
   (SELECT COUNT_BIG(*) FROM dbo.UC6_Write_C_Parent)<>10200 OR
   (SELECT COUNT_BIG(*) FROM dbo.UC6_Write_A_Tag WHERE TAG=N'probe:added')<>200 OR
   (SELECT COUNT_BIG(*) FROM dbo.UC6_Write_C_Tag WHERE TAG=N'probe:added')<>200
 THROW 56106,'UC6 final write state mismatch',1;
SELECT N'RUN_COMPLETE' section,N'PASS' status;
