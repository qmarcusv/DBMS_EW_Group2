/* Destructive only to UC3 disposable tables; run after preserving raw evidence. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
DROP TABLE IF EXISTS dbo.UC3_Bench_100K,dbo.UC3_Bench_1000K,
 dbo.UC3_Write_A_100K,dbo.UC3_Write_B_100K,dbo.UC3_Write_C_100K,
 dbo.UC3_Write_A_1000K,dbo.UC3_Write_B_1000K,dbo.UC3_Write_C_1000K;
SELECT N'UC3_CLEANUP_COMPLETE' section;
