/* Drop only Phase 6 disposable copies after preserving evidence. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
DROP TABLE IF EXISTS dbo.UC5_Rowstore,dbo.UC5_Columnstore;
SELECT N'UC5_CLEANUP_COMPLETE' section;
