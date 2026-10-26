/* Phase 7 UC6. Run as a whole T-SQL file after uc6_load_sql.py. */
USE [DBMS_EW_Group02];
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF (SELECT COUNT_BIG(*) FROM dbo.UC6_Seed_Parent)<>10000 OR
   (SELECT COUNT_BIG(*) FROM dbo.UC6_Seed_Tag)<>30471
 THROW 56000,'UC6 seed missing or count changed',1;
IF EXISTS(SELECT 1 FROM sys.tables WHERE schema_id=SCHEMA_ID(N'dbo') AND name LIKE N'UC6[_]Read[_]%') OR
   EXISTS(SELECT 1 FROM sys.tables WHERE schema_id=SCHEMA_ID(N'dbo') AND name LIKE N'UC6[_]Write[_]%')
 THROW 56001,'UC6 disposable copies already exist',1;
DECLARE @run uniqueidentifier=NEWID(),@c char(1),@role varchar(5),@parent sysname,@tag sysname,
 @sql nvarchar(max),@start datetime2(7),@ms decimal(19,3),@bytes bigint;
SELECT N'RUN_CONTEXT' section,@run run_id,@@VERSION sql_version,DB_NAME() database_name;
DECLARE roles CURSOR LOCAL FAST_FORWARD FOR SELECT role,c FROM
 (VALUES('Read','A'),('Read','C'),('Write','A'),('Write','C'))x(role,c);
OPEN roles;FETCH NEXT FROM roles INTO @role,@c;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @parent=N'UC6_'+@role+N'_'+@c+N'_Parent';
 SET @tag=N'UC6_'+@role+N'_'+@c+N'_Tag';
 SET @sql=N'SELECT * INTO dbo.'+QUOTENAME(@parent)+N' FROM dbo.UC6_Seed_Parent;
 SELECT * INTO dbo.'+QUOTENAME(@tag)+N' FROM dbo.UC6_Seed_Tag;
 ALTER TABLE dbo.'+QUOTENAME(@parent)+N' ADD CONSTRAINT '+QUOTENAME(N'PK_'+@parent)+N' PRIMARY KEY CLUSTERED(PARENT_ID);
 ALTER TABLE dbo.'+QUOTENAME(@tag)+N' ADD CONSTRAINT '+QUOTENAME(N'PK_'+@tag)+N' PRIMARY KEY CLUSTERED(PARENT_ID,TAG);
 ALTER TABLE dbo.'+QUOTENAME(@tag)+N' ADD CONSTRAINT '+QUOTENAME(N'FK_'+@tag)+N' FOREIGN KEY(PARENT_ID) REFERENCES dbo.'+QUOTENAME(@parent)+N'(PARENT_ID);';
 EXEC sys.sp_executesql @sql;
 SELECT N'COPY_READY' section,@role role,@c config,@parent parent_table,@tag tag_table,
  10000 parent_rows,30471 tag_rows;
 FETCH NEXT FROM roles INTO @role,@c;
END;
CLOSE roles;DEALLOCATE roles;
DECLARE roles CURSOR LOCAL FAST_FORWARD FOR SELECT role FROM (VALUES('Read'),('Write'))x(role);
OPEN roles;FETCH NEXT FROM roles INTO @role;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @tag=N'UC6_'+@role+N'_C_Tag';
 SET @sql=N'CREATE INDEX IX_UC6_Tag_Parent ON dbo.'+QUOTENAME(@tag)+N' (TAG,PARENT_ID)';
 SET @start=SYSUTCDATETIME(); EXEC sys.sp_executesql @sql;
 SET @ms=DATEDIFF_BIG(MICROSECOND,@start,SYSUTCDATETIME())/1000.0;
 SELECT @bytes=SUM(used_page_count)*CONVERT(bigint,8192)
 FROM sys.dm_db_partition_stats
 WHERE object_id=OBJECT_ID(N'dbo.'+@tag) AND index_id=(SELECT index_id FROM sys.indexes
   WHERE object_id=OBJECT_ID(N'dbo.'+@tag) AND name=N'IX_UC6_Tag_Parent');
 SELECT N'INDEX_BUILD' section,@role role,N'C' config,@ms elapsed_ms,@bytes index_used_bytes;
 FETCH NEXT FROM roles INTO @role;
END;
CLOSE roles;DEALLOCATE roles;
SELECT N'SETUP_COMPLETE' section,N'PASS' status;
