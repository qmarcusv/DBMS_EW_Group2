/* Explicit cleanup only after UC6 results have been saved and verified. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
IF OBJECT_ID(N'dbo.UC6_Read_A_Tag',N'U') IS NOT NULL DROP TABLE dbo.UC6_Read_A_Tag;
IF OBJECT_ID(N'dbo.UC6_Read_C_Tag',N'U') IS NOT NULL DROP TABLE dbo.UC6_Read_C_Tag;
IF OBJECT_ID(N'dbo.UC6_Write_A_Tag',N'U') IS NOT NULL DROP TABLE dbo.UC6_Write_A_Tag;
IF OBJECT_ID(N'dbo.UC6_Write_C_Tag',N'U') IS NOT NULL DROP TABLE dbo.UC6_Write_C_Tag;
IF OBJECT_ID(N'dbo.UC6_Read_A_Parent',N'U') IS NOT NULL DROP TABLE dbo.UC6_Read_A_Parent;
IF OBJECT_ID(N'dbo.UC6_Read_C_Parent',N'U') IS NOT NULL DROP TABLE dbo.UC6_Read_C_Parent;
IF OBJECT_ID(N'dbo.UC6_Write_A_Parent',N'U') IS NOT NULL DROP TABLE dbo.UC6_Write_A_Parent;
IF OBJECT_ID(N'dbo.UC6_Write_C_Parent',N'U') IS NOT NULL DROP TABLE dbo.UC6_Write_C_Parent;
IF OBJECT_ID(N'dbo.UC6_Seed_Tag',N'U') IS NOT NULL DROP TABLE dbo.UC6_Seed_Tag;
IF OBJECT_ID(N'dbo.UC6_Seed_Parent',N'U') IS NOT NULL DROP TABLE dbo.UC6_Seed_Parent;
SELECT N'UC6_CLEANUP_COMPLETE' section;
