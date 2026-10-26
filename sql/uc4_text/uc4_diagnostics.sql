/* Run after a successful UC4 setup. Capture complete output with sqlcmd -y 0. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
IF OBJECT_ID(N'dbo.UC4_Read_A',N'U') IS NULL OR OBJECT_ID(N'dbo.UC4_Read_C',N'U') IS NULL
 THROW 54200,'UC4 read copies missing',1;
DECLARE @queries TABLE(query_id varchar(8),term nvarchar(40));
INSERT @queries VALUES('K_HIGH',N'election'),('K_MED',N'climate'),('K_LOW',N'bitcoin'),
 ('P_HIGH',N'white house'),('P_MED',N'climate change'),('P_LOW',N'stock market');
DECLARE @q varchar(8),@term nvarchar(40),@search nvarchar(100),@config char(1),@sql nvarchar(max);
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
SET STATISTICS XML ON;
DECLARE cur CURSOR LOCAL FAST_FORWARD FOR SELECT query_id,term FROM @queries;
OPEN cur;FETCH NEXT FROM cur INTO @q,@term;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @search=N'"'+@term+N'"';
 DECLARE config_cursor CURSOR LOCAL FAST_FORWARD FOR SELECT config FROM (VALUES('A'),('C'))x(config);
 OPEN config_cursor;FETCH NEXT FROM config_cursor INTO @config;
 WHILE @@FETCH_STATUS=0
 BEGIN
  SET @sql=CASE WHEN @config='A' THEN
   N'SELECT DOC_ID FROM dbo.UC4_Read_A WHERE BODY LIKE N''%''+@term+N''%'''
   ELSE N'SELECT DOC_ID FROM dbo.UC4_Read_C WHERE CONTAINS(BODY,@search,LANGUAGE 1033)' END;
  SELECT N'PLAN_FOR' section,@q query_id,@config config,@sql query_template;
  EXEC sys.sp_executesql @sql,N'@term nvarchar(40),@search nvarchar(100)',@term=@term,@search=@search;
  FETCH NEXT FROM config_cursor INTO @config;
 END;
 CLOSE config_cursor;DEALLOCATE config_cursor;
 FETCH NEXT FROM cur INTO @q,@term;
END;
CLOSE cur;DEALLOCATE cur;
SET STATISTICS XML OFF;
SET STATISTICS TIME OFF;
SET STATISTICS IO OFF;
SELECT N'DIAGNOSTICS_COMPLETE' section,N'PASS' status;
