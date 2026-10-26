/* Run AFTER uc1_benchmark.sql, before cleanup. Dedicated, untimed plan/IO
   pass on the disposable read copy. It cycles A/B/C, leaving C installed.
   In SSMS use Results to Grid, with toolbar Actual Plan OFF, and save each
   XML result as A_U1a.sqlplan ... C_U1d.sqlplan. In sqlcmd use -y 0 to
   avoid the default 256-character XML truncation. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
IF OBJECT_ID(N'dbo.UC1_Bench_100K',N'U') IS NULL
    THROW 51200,'UC1 read copy missing.',1;
IF (SELECT COUNT_BIG(*) FROM dbo.UC1_Bench_100K)<>100000
    THROW 51201,'UC1 read copy row count changed.',1;
IF EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.UC1_Bench_100K')
          AND index_id>0 AND name NOT IN(N'IX_UC1_Owner',N'IX_UC1_OwnerTypeObjectId'))
    THROW 51202,'Unexpected index on UC1 read copy.',1;

DECLARE @config char(1),@query nvarchar(4),@predicate nvarchar(300),
        @order nvarchar(120),@sql nvarchar(max);
DECLARE @spec TABLE(query_id nvarchar(4),predicate_sql nvarchar(300),order_sql nvarchar(120));
INSERT @spec VALUES
 (N'U1a',N'[OWNER]=N''SYS'' AND [OBJECT_TYPE]=N''TABLE'' AND [OBJECT_ID]=16',N''),
 (N'U1b',N'[OWNER]=N''SYS'' AND [OBJECT_TYPE]=N''TABLE''',N''),
 (N'U1c',N'[OBJECT_TYPE]=N''TABLE'' AND [OBJECT_ID]=16',N''),
 (N'U1d',N'[OWNER]=N''CTXSYS''',N' ORDER BY [OBJECT_TYPE] ASC,[OBJECT_ID] ASC');

IF EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.UC1_Bench_100K')
          AND name=N'IX_UC1_OwnerTypeObjectId')
    DROP INDEX IX_UC1_OwnerTypeObjectId ON dbo.UC1_Bench_100K;
IF EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.UC1_Bench_100K')
          AND name=N'IX_UC1_Owner')
    DROP INDEX IX_UC1_Owner ON dbo.UC1_Bench_100K;

DECLARE config_cursor CURSOR LOCAL FAST_FORWARD FOR
 SELECT config FROM (VALUES('A'),('B'),('C')) AS v(config);
OPEN config_cursor;
FETCH NEXT FROM config_cursor INTO @config;
WHILE @@FETCH_STATUS=0
BEGIN
    IF @config='B'
        CREATE INDEX IX_UC1_Owner ON dbo.UC1_Bench_100K([OWNER]);
    IF @config='C'
    BEGIN
        DROP INDEX IX_UC1_Owner ON dbo.UC1_Bench_100K;
        CREATE INDEX IX_UC1_OwnerTypeObjectId
          ON dbo.UC1_Bench_100K([OWNER],[OBJECT_TYPE],[OBJECT_ID]);
    END;
    DECLARE query_cursor CURSOR LOCAL FAST_FORWARD FOR
      SELECT query_id,predicate_sql,order_sql FROM @spec ORDER BY query_id;
    OPEN query_cursor;
    FETCH NEXT FROM query_cursor INTO @query,@predicate,@order;
    WHILE @@FETCH_STATUS=0
    BEGIN
        SELECT N'PLAN_MARKER' AS section,@config AS configuration,@query AS query_id,
               N'Next XML result and IO/TIME messages belong to this marker.' AS note;
        SET @sql=N'DECLARE @payload nvarchar(max);
SELECT @payload=(SELECT [ID],[OWNER],[OBJECT_TYPE],[OBJECT_ID]
 FROM dbo.UC1_Bench_100K WHERE '+@predicate+@order+N' FOR JSON PATH);';
        SET STATISTICS IO ON;
        SET STATISTICS TIME ON;
        SET STATISTICS XML ON;
        EXEC sys.sp_executesql @sql;
        SET STATISTICS XML OFF;
        SET STATISTICS TIME OFF;
        SET STATISTICS IO OFF;
        FETCH NEXT FROM query_cursor INTO @query,@predicate,@order;
    END;
    CLOSE query_cursor;
    DEALLOCATE query_cursor;
    FETCH NEXT FROM config_cursor INTO @config;
END;
CLOSE config_cursor;
DEALLOCATE config_cursor;
SELECT N'DIAGNOSTICS_COMPLETE' AS section,N'12 plan markers emitted; copy left in C.' AS note;
