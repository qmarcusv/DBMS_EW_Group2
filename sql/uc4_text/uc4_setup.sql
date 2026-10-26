/* Run via sqlcmd -b or SSMS as a whole file. Creates only UC4 disposable objects. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF FULLTEXTSERVICEPROPERTY('IsFullTextInstalled')<>1 THROW 54000,'SQL Full-Text Search unavailable',1;
IF (SELECT COUNT_BIG(*) FROM dbo.UC4_Seed_10K)<>10000 THROW 54001,'UC4 seed must have 10000 rows',1;
IF OBJECT_ID(N'dbo.UC4_Read_A',N'U') IS NOT NULL OR OBJECT_ID(N'dbo.UC4_Read_C',N'U') IS NOT NULL OR
   OBJECT_ID(N'dbo.UC4_Write_A',N'U') IS NOT NULL OR OBJECT_ID(N'dbo.UC4_Write_C',N'U') IS NOT NULL OR
   EXISTS(SELECT 1 FROM sys.fulltext_catalogs WHERE name IN(N'UC4_FT_Read',N'UC4_FT_Write'))
 THROW 54002,'UC4 disposable objects already exist',1;

DECLARE @t datetime2(7)=SYSUTCDATETIME(),@create_ms decimal(19,3),@population_ms decimal(19,3),
 @status int,@items bigint,@attempt int=0;
SELECT N'ENVIRONMENT' section,@@VERSION version,DB_NAME() database_name,
 FULLTEXTSERVICEPROPERTY('IsFullTextInstalled') fulltext_installed;
SELECT * INTO dbo.UC4_Read_A FROM dbo.UC4_Seed_10K;
SELECT * INTO dbo.UC4_Read_C FROM dbo.UC4_Seed_10K;
SELECT * INTO dbo.UC4_Write_A FROM dbo.UC4_Seed_10K;
SELECT * INTO dbo.UC4_Write_C FROM dbo.UC4_Seed_10K;
ALTER TABLE dbo.UC4_Read_A ADD CONSTRAINT PK_UC4_Read_A PRIMARY KEY CLUSTERED(DOC_ID);
ALTER TABLE dbo.UC4_Read_C ADD CONSTRAINT PK_UC4_Read_C PRIMARY KEY CLUSTERED(DOC_ID);
ALTER TABLE dbo.UC4_Write_A ADD CONSTRAINT PK_UC4_Write_A PRIMARY KEY CLUSTERED(DOC_ID);
ALTER TABLE dbo.UC4_Write_C ADD CONSTRAINT PK_UC4_Write_C PRIMARY KEY CLUSTERED(DOC_ID);
SELECT N'COPY_READY' section, v.name table_name, v.rows rows,
 CONVERT(decimal(19,3),DATEDIFF_BIG(MICROSECOND,@t,SYSUTCDATETIME())/1000.0) copy_and_key_ms
FROM (VALUES(N'UC4_Read_A',(SELECT COUNT_BIG(*) FROM dbo.UC4_Read_A)),
 (N'UC4_Read_C',(SELECT COUNT_BIG(*) FROM dbo.UC4_Read_C)),
 (N'UC4_Write_A',(SELECT COUNT_BIG(*) FROM dbo.UC4_Write_A)),
 (N'UC4_Write_C',(SELECT COUNT_BIG(*) FROM dbo.UC4_Write_C)))v(name,rows);

CREATE FULLTEXT CATALOG UC4_FT_Read;
SET @t=SYSUTCDATETIME();
CREATE FULLTEXT INDEX ON dbo.UC4_Read_C (BODY LANGUAGE 1033)
 KEY INDEX PK_UC4_Read_C ON UC4_FT_Read WITH CHANGE_TRACKING = AUTO, STOPLIST = SYSTEM;
SET @create_ms=DATEDIFF_BIG(MICROSECOND,@t,SYSUTCDATETIME())/1000.0;
WHILE 1=1
BEGIN
 SET @status=CONVERT(int,OBJECTPROPERTYEX(OBJECT_ID(N'dbo.UC4_Read_C'),N'TableFulltextPopulateStatus'));
 SET @items=CONVERT(bigint,OBJECTPROPERTYEX(OBJECT_ID(N'dbo.UC4_Read_C'),N'TableFulltextItemCount'));
 IF @status=0 AND @items=10000 BREAK;
 IF @attempt>=600 THROW 54003,'UC4 read full-text population timeout',1;
 WAITFOR DELAY '00:00:01'; SET @attempt+=1;
END;
SET @population_ms=DATEDIFF_BIG(MICROSECOND,@t,SYSUTCDATETIME())/1000.0;
SELECT N'INDEX_BUILD' section,N'read' role,N'C' config,@create_ms create_index_ms,
 @population_ms population_complete_ms,@status population_status,@items fulltext_items,
 FULLTEXTCATALOGPROPERTY(N'UC4_FT_Read',N'IndexSize') catalog_logical_mb;

CREATE FULLTEXT CATALOG UC4_FT_Write;
SET @t=SYSUTCDATETIME();
CREATE FULLTEXT INDEX ON dbo.UC4_Write_C (BODY LANGUAGE 1033)
 KEY INDEX PK_UC4_Write_C ON UC4_FT_Write WITH CHANGE_TRACKING = AUTO, STOPLIST = SYSTEM;
SET @create_ms=DATEDIFF_BIG(MICROSECOND,@t,SYSUTCDATETIME())/1000.0;
SET @attempt=0;
WHILE 1=1
BEGIN
 SET @status=CONVERT(int,OBJECTPROPERTYEX(OBJECT_ID(N'dbo.UC4_Write_C'),N'TableFulltextPopulateStatus'));
 SET @items=CONVERT(bigint,OBJECTPROPERTYEX(OBJECT_ID(N'dbo.UC4_Write_C'),N'TableFulltextItemCount'));
 IF @status=0 AND @items=10000 BREAK;
 IF @attempt>=600 THROW 54004,'UC4 write full-text population timeout',1;
 WAITFOR DELAY '00:00:01'; SET @attempt+=1;
END;
SET @population_ms=DATEDIFF_BIG(MICROSECOND,@t,SYSUTCDATETIME())/1000.0;
SELECT N'INDEX_BUILD' section,N'write' role,N'C' config,@create_ms create_index_ms,
 @population_ms population_complete_ms,@status population_status,@items fulltext_items,
 FULLTEXTCATALOGPROPERTY(N'UC4_FT_Write',N'IndexSize') catalog_logical_mb;
SELECT N'SETUP_COMPLETE' section,N'PASS' status;
