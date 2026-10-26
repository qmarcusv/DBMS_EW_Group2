/* Run only after saving raw output and all plan evidence.
   Drops exactly four disposable UC1 tables; never touches reference data. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
SELECT N'BEFORE_CLEANUP' AS section,t.name AS copy_name
FROM sys.tables AS t WHERE t.schema_id=SCHEMA_ID(N'dbo')
 AND t.name IN(N'UC1_Bench_100K',N'UC1_Write_A_100K',
               N'UC1_Write_B_100K',N'UC1_Write_C_100K')
ORDER BY t.name;
DROP TABLE IF EXISTS dbo.UC1_Bench_100K;
DROP TABLE IF EXISTS dbo.UC1_Write_A_100K;
DROP TABLE IF EXISTS dbo.UC1_Write_B_100K;
DROP TABLE IF EXISTS dbo.UC1_Write_C_100K;
SELECT N'AFTER_CLEANUP' AS section,
       (SELECT COUNT_BIG(*) FROM dbo.DEMO_BIG_TABLE_100K) AS reference_rows,
       (SELECT COUNT(*) FROM sys.tables WHERE schema_id=SCHEMA_ID(N'dbo')
          AND name IN(N'UC1_Bench_100K',N'UC1_Write_A_100K',
                      N'UC1_Write_B_100K',N'UC1_Write_C_100K')) AS remaining_copies;
