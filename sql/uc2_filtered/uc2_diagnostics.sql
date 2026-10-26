/* Untimed actual plans and IO. Run after uc2_run.sql, before cleanup.
   Use sqlcmd -y 0 for full XML, or save XML cells as .sqlplan in SSMS.
   Changes only UC2 read-copy indexes; leaves C on both scales. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
SET ANSI_NULLS ON; SET ANSI_PADDING ON; SET ANSI_WARNINGS ON;
SET ARITHABORT ON; SET CONCAT_NULL_YIELDS_NULL ON;
SET QUOTED_IDENTIFIER ON; SET NUMERIC_ROUNDABORT OFF;
DECLARE @scale varchar(5),@name sysname,@config char(1),@v nchar(1),@sql nvarchar(max);
DECLARE sc CURSOR LOCAL FAST_FORWARD FOR SELECT s FROM (VALUES('100K'),('1000K')) x(s);
OPEN sc;FETCH NEXT FROM sc INTO @scale;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @name=N'UC2_Bench_'+@scale;
 IF OBJECT_ID(N'dbo.'+@name,N'U') IS NULL THROW 52100,'UC2 read copy missing.',1;
 SET @sql=N'IF EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N''dbo.'+@name+N''') AND name=N''IX_UC2_Filtered'') DROP INDEX IX_UC2_Filtered ON dbo.'+QUOTENAME(@name);
 EXEC sys.sp_executesql @sql;
 DECLARE cc CURSOR LOCAL FAST_FORWARD FOR SELECT c FROM (VALUES('A'),('B'),('C')) x(c);
 OPEN cc;FETCH NEXT FROM cc INTO @config;
 WHILE @@FETCH_STATUS=0
 BEGIN
  IF @config='B'
  BEGIN
   SET @sql=N'CREATE INDEX IX_UC2_Full ON dbo.'+QUOTENAME(@name)+N' (OBJECT_TYPE,OBJECT_ID) INCLUDE (TEMPORARY)';EXEC sys.sp_executesql @sql;
  END;
  IF @config='C'
  BEGIN
   SET @sql=N'DROP INDEX IX_UC2_Full ON dbo.'+QUOTENAME(@name);EXEC sys.sp_executesql @sql;
   SET @sql=N'CREATE INDEX IX_UC2_Filtered ON dbo.'+QUOTENAME(@name)+N' (OBJECT_TYPE,OBJECT_ID) INCLUDE (TEMPORARY) WHERE TEMPORARY=N''Y''';EXEC sys.sp_executesql @sql;
  END;
  DECLARE vc CURSOR LOCAL FAST_FORWARD FOR SELECT v FROM (VALUES(N'Y'),(N'N')) x(v);
  OPEN vc;FETCH NEXT FROM vc INTO @v;
  WHILE @@FETCH_STATUS=0
  BEGIN
   SELECT N'PLAN_MARKER' section,@scale scale,@config config,@v temporary;
   SET @sql=N'DECLARE @payload nvarchar(max);SELECT @payload=(SELECT OBJECT_TYPE,OBJECT_ID,TEMPORARY FROM dbo.'+QUOTENAME(@name)+
    N' WHERE TEMPORARY=N'''+@v+N''' AND OBJECT_TYPE=N''TABLE'' AND OBJECT_ID BETWEEN 1 AND 10000 FOR JSON PATH)';
   SET STATISTICS IO ON; SET STATISTICS XML ON;
   EXEC sys.sp_executesql @sql;
   SET STATISTICS XML OFF; SET STATISTICS IO OFF;
   FETCH NEXT FROM vc INTO @v;
  END;
  CLOSE vc;DEALLOCATE vc;
  FETCH NEXT FROM cc INTO @config;
 END;
 CLOSE cc;DEALLOCATE cc;
 /* Parameterized and recompiled variants on C; record runtime parameter values. */
 DECLARE pc CURSOR LOCAL FAST_FORWARD FOR SELECT v FROM (VALUES(N'Y'),(N'N')) x(v);
 OPEN pc;FETCH NEXT FROM pc INTO @v;
 WHILE @@FETCH_STATUS=0
 BEGIN
  SELECT N'PARAM_PLAN_MARKER' section,@scale scale,@v temporary,N'CACHED' variant;
  SET @sql=N'DECLARE @payload nvarchar(max);SELECT @payload=(SELECT OBJECT_TYPE,OBJECT_ID,TEMPORARY FROM dbo.'+QUOTENAME(@name)+
   N' WHERE TEMPORARY=@p AND OBJECT_TYPE=N''TABLE'' AND OBJECT_ID BETWEEN 1 AND 10000 FOR JSON PATH)';
  SET STATISTICS IO ON;SET STATISTICS XML ON;
  EXEC sys.sp_executesql @sql,N'@p nchar(1)',@p=@v;
  SET STATISTICS XML OFF;SET STATISTICS IO OFF;
  SELECT N'PARAM_PLAN_MARKER' section,@scale scale,@v temporary,N'RECOMPILE' variant;
  SET @sql=@sql+N' OPTION (RECOMPILE)';
  SET STATISTICS IO ON;SET STATISTICS XML ON;
  EXEC sys.sp_executesql @sql,N'@p nchar(1)',@p=@v;
  SET STATISTICS XML OFF;SET STATISTICS IO OFF;
  FETCH NEXT FROM pc INTO @v;
 END;
 CLOSE pc;DEALLOCATE pc;
 FETCH NEXT FROM sc INTO @scale;
END;
CLOSE sc;DEALLOCATE sc;
SELECT N'DIAGNOSTICS_COMPLETE' section,N'12 literal and 8 parameter plans expected' note;
