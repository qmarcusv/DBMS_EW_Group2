/* Run after uc3_run.sql, before cleanup. Captures A/B/C actual plans separately
   from timed samples. Save with sqlcmd -y 0 (complete XML) or SSMS .sqlplan. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
IF OBJECT_ID(N'dbo.UC3_Bench_100K') IS NULL OR OBJECT_ID(N'dbo.UC3_Bench_1000K') IS NULL
 THROW 53100,'Run uc3_run.sql first.',1;
DECLARE @scale varchar(5),@table sysname,@config char(1),@sql nvarchar(max),@query varchar(8),@hi int;
DECLARE scales CURSOR LOCAL FAST_FORWARD FOR SELECT v.scale FROM (VALUES('100K'),('1000K'))v(scale);
OPEN scales;FETCH NEXT FROM scales INTO @scale;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @table=N'UC3_Bench_'+@scale;
 /* Run script ends in C; rotate to A and B, then restore C. */
 SET @sql=N'DROP INDEX IX_UC3_Cover ON dbo.'+QUOTENAME(@table);
 EXEC sys.sp_executesql @sql;
 DECLARE configs CURSOR LOCAL FAST_FORWARD FOR SELECT v.c FROM (VALUES('A'),('B'),('C'))v(c);
 OPEN configs;FETCH NEXT FROM configs INTO @config;
 WHILE @@FETCH_STATUS=0
 BEGIN
  IF @config='B'
  BEGIN
   SET @sql=N'CREATE INDEX IX_UC3_Key ON dbo.'+QUOTENAME(@table)+N' (OBJECT_ID)';
   EXEC sys.sp_executesql @sql;
  END;
  IF @config='C'
  BEGIN
   SET @sql=N'DROP INDEX IX_UC3_Key ON dbo.'+QUOTENAME(@table);
   EXEC sys.sp_executesql @sql;
   SET @sql=N'CREATE INDEX IX_UC3_Cover ON dbo.'+QUOTENAME(@table)+
     N' (OBJECT_ID) INCLUDE (ID,OWNER,OBJECT_NAME,OBJECT_TYPE)';
   EXEC sys.sp_executesql @sql;
  END;
  DECLARE queries CURSOR LOCAL FAST_FORWARD FOR SELECT v.q FROM (VALUES('POINT'),('SMALL'),('MEDIUM'))v(q);
  OPEN queries;FETCH NEXT FROM queries INTO @query;
  WHILE @@FETCH_STATUS=0
  BEGIN
   SET @hi=CASE WHEN @query='SMALL' THEN CASE WHEN @scale='100K' THEN 50 ELSE 5 END
                 WHEN @query='MEDIUM' THEN CASE WHEN @scale='100K' THEN 1000 ELSE 200 END ELSE 16 END;
   SELECT N'DIAGNOSTIC' section,@scale scale,@config config,@query query_id;
   SET @sql=N'SELECT ID,OWNER,OBJECT_NAME,OBJECT_TYPE FROM dbo.'+QUOTENAME(@table)+
    CASE WHEN @query='POINT' THEN N' WHERE OBJECT_ID=16 AND ID=1'
         ELSE N' WHERE OBJECT_ID BETWEEN 1 AND '+CONVERT(nvarchar(20),@hi) END;
   SET STATISTICS IO ON;SET STATISTICS TIME ON;SET STATISTICS XML ON;
   EXEC sys.sp_executesql @sql;
   SET STATISTICS XML OFF;SET STATISTICS IO OFF;SET STATISTICS TIME OFF;
   FETCH NEXT FROM queries INTO @query;
  END;
  CLOSE queries;DEALLOCATE queries;
  FETCH NEXT FROM configs INTO @config;
 END;
 CLOSE configs;DEALLOCATE configs;
 FETCH NEXT FROM scales INTO @scale;
END;
CLOSE scales;DEALLOCATE scales;
SELECT N'UC3_DIAGNOSTICS_COMPLETE' section;
