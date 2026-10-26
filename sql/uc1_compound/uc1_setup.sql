/* Phase 3 UC1 setup. Run once in SSMS against the intended local instance.
   Creates four disposable HEAP copies; never changes the reference table.
   Existing copies cause a hard stop. Run uc1_cleanup.sql explicitly after
   exporting every raw result and plan. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
IF CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion')) NOT LIKE N'17.%'
    THROW 51000, 'Expected SQL Server 17.x; inspect environment.', 1;
IF OBJECT_ID(N'dbo.DEMO_BIG_TABLE_100K', N'U') IS NULL
    THROW 51001, 'Exact reference table missing.', 1;
IF EXISTS (SELECT 1 FROM sys.tables WHERE schema_id = SCHEMA_ID(N'dbo')
           AND name IN (N'UC1_Bench_100K',N'UC1_Write_A_100K',
                        N'UC1_Write_B_100K',N'UC1_Write_C_100K'))
    THROW 51002, 'One or more UC1 copies already exist; inspect before cleanup.', 1;
IF (SELECT COUNT_BIG(*) FROM dbo.DEMO_BIG_TABLE_100K) <> 100000
    THROW 51003, 'Reference row count is not 100000.', 1;

SELECT * INTO dbo.UC1_Bench_100K   FROM dbo.DEMO_BIG_TABLE_100K;
SELECT * INTO dbo.UC1_Write_A_100K FROM dbo.DEMO_BIG_TABLE_100K;
SELECT * INTO dbo.UC1_Write_B_100K FROM dbo.DEMO_BIG_TABLE_100K;
SELECT * INTO dbo.UC1_Write_C_100K FROM dbo.DEMO_BIG_TABLE_100K;

;WITH inventory AS (
    SELECT N'SOURCE' AS label, COUNT_BIG(*) AS rows,
           SUM(CONVERT(bigint,ID)) AS id_sum,
           CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_NAME,OBJECT_TYPE,OBJECT_ID,TEMPORARY)) AS fingerprint
    FROM dbo.DEMO_BIG_TABLE_100K
    UNION ALL SELECT N'READ_COPY',COUNT_BIG(*),SUM(CONVERT(bigint,ID)),
           CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_NAME,OBJECT_TYPE,OBJECT_ID,TEMPORARY))
    FROM dbo.UC1_Bench_100K
    UNION ALL SELECT N'WRITE_A',COUNT_BIG(*),SUM(CONVERT(bigint,ID)),
           CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_NAME,OBJECT_TYPE,OBJECT_ID,TEMPORARY))
    FROM dbo.UC1_Write_A_100K
    UNION ALL SELECT N'WRITE_B',COUNT_BIG(*),SUM(CONVERT(bigint,ID)),
           CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_NAME,OBJECT_TYPE,OBJECT_ID,TEMPORARY))
    FROM dbo.UC1_Write_B_100K
    UNION ALL SELECT N'WRITE_C',COUNT_BIG(*),SUM(CONVERT(bigint,ID)),
           CHECKSUM_AGG(BINARY_CHECKSUM(ID,OWNER,OBJECT_NAME,OBJECT_TYPE,OBJECT_ID,TEMPORARY))
    FROM dbo.UC1_Write_C_100K
)
SELECT N'COPY_PARITY' AS section, * FROM inventory;

IF EXISTS (SELECT 1 FROM sys.indexes WHERE object_id IN (
    OBJECT_ID(N'dbo.UC1_Bench_100K'), OBJECT_ID(N'dbo.UC1_Write_A_100K'),
    OBJECT_ID(N'dbo.UC1_Write_B_100K'), OBJECT_ID(N'dbo.UC1_Write_C_100K'))
    AND index_id > 0)
    THROW 51004, 'A new copy unexpectedly inherited an optional index.', 1;
SELECT N'COPY_READY' AS section, @@SPID AS session_id,
       N'Four 100K heap copies; no secondary indexes; reference untouched.' AS note;
