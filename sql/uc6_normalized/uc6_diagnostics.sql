/* Separate actual plans, CPU and logical reads. Run after UC6 setup. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
IF OBJECT_ID(N'dbo.UC6_Read_A_Tag',N'U') IS NULL OR OBJECT_ID(N'dbo.UC6_Read_C_Tag',N'U') IS NULL
 THROW 56200,'UC6 read copies missing',1;
DECLARE @queries TABLE(query_id varchar(24),tag1 nvarchar(128),tag2 nvarchar(128),required int);
INSERT @queries VALUES('ONE_TABLE',N'type:TABLE',NULL,1),
 ('TWO_SYS_TABLE',N'owner:SYS',N'type:TABLE',2),
 ('ONE_TEMP_Y',N'temporary:Y',NULL,1),
 ('TWO_TABLE_TEMP_Y',N'type:TABLE',N'temporary:Y',2);
DECLARE @q varchar(24),@tag1 nvarchar(128),@tag2 nvarchar(128),@required int,@config char(1),@sql nvarchar(max);
DECLARE qcur CURSOR LOCAL FAST_FORWARD FOR SELECT query_id,tag1,tag2,required FROM @queries;
OPEN qcur;FETCH NEXT FROM qcur INTO @q,@tag1,@tag2,@required;
WHILE @@FETCH_STATUS=0
BEGIN
 DECLARE ccur CURSOR LOCAL FAST_FORWARD FOR SELECT c FROM (VALUES('A'),('C'))x(c);
 OPEN ccur;FETCH NEXT FROM ccur INTO @config;
 WHILE @@FETCH_STATUS=0
 BEGIN
  SET @sql=N'SELECT PARENT_ID FROM dbo.'+
    CASE WHEN @config='A' THEN N'UC6_Read_A_Tag' ELSE N'UC6_Read_C_Tag' END+
    N' WHERE TAG IN(@tag1,@tag2) GROUP BY PARENT_ID HAVING COUNT(DISTINCT TAG)=@required';
  SELECT N'PLAN_FOR' section,@q query_id,@config config,@sql query_template;
  SET STATISTICS IO ON;SET STATISTICS TIME ON;SET STATISTICS XML ON;
  EXEC sys.sp_executesql @sql,N'@tag1 nvarchar(128),@tag2 nvarchar(128),@required int',
    @tag1=@tag1,@tag2=@tag2,@required=@required;
  SET STATISTICS XML OFF;SET STATISTICS TIME OFF;SET STATISTICS IO OFF;
  FETCH NEXT FROM ccur INTO @config;
 END;
 CLOSE ccur;DEALLOCATE ccur;
 FETCH NEXT FROM qcur INTO @q,@tag1,@tag2,@required;
END;
CLOSE qcur;DEALLOCATE qcur;
SELECT N'DIAGNOSTICS_COMPLETE' section,N'PASS' status;
