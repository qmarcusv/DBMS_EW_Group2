/*
Phase 1 read-only inventory for SQL Server. Run in SSMS against the intended
local instance; save every result grid and any Messages separately.
No DDL, DML, transaction, statistics update, or reference-data change.
Exact scans cover 10K, 100K, and 1000K only. The 15000K row count is metadata
unless @Scan15000K is explicitly changed to 1 in a future approved audit.
*/
USE [DBMS_EW_Group02];
SET NOCOUNT ON;

SELECT N'SERVER' AS section,
       @@SERVERNAME AS server_name,
       CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion')) AS product_version,
       CONVERT(nvarchar(128), SERVERPROPERTY('ProductLevel')) AS product_level,
       CONVERT(nvarchar(256), SERVERPROPERTY('Edition')) AS edition,
       CONVERT(int, SERVERPROPERTY('EngineEdition')) AS engine_edition;

SELECT N'DATABASE' AS section, name, compatibility_level, collation_name,
       state_desc, is_read_only
FROM sys.databases WHERE name = N'DBMS_EW_Group02';

SELECT N'FULLTEXT_READINESS' AS section,
       FULLTEXTSERVICEPROPERTY('IsFullTextInstalled') AS is_fulltext_installed,
       CONVERT(int, SERVERPROPERTY('IsFullTextInstalled')) AS serverproperty_fulltext,
       HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CREATE TABLE') AS can_create_table,
       HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CREATE FULLTEXT CATALOG') AS can_create_fulltext_catalog;

SELECT N'FULLTEXT_CATALOG' AS section, name, is_default
FROM sys.fulltext_catalogs ORDER BY name;

SELECT N'TARGET_EXISTENCE' AS section, v.scale_label, v.expected_table,
       OBJECT_ID(N'dbo.' + v.expected_table, N'U') AS object_id,
       CASE WHEN OBJECT_ID(N'dbo.' + v.expected_table, N'U') IS NULL
            THEN N'MISSING_OR_NOT_VISIBLE' ELSE N'VISIBLE' END AS status
FROM (VALUES
    (N'10K', N'DEMO_BIG_TABLE_10K'),
    (N'100K', N'DEMO_BIG_TABLE_100K'),
    (N'1000K', N'DEMO_BIG_TABLE_1000K'),
    (N'15000K', N'DEMO_BIG_TABLE_15000K')
) AS v(scale_label, expected_table);

SELECT N'TABLE_LAYOUT' AS section, t.name AS table_name,
       CASE WHEN EXISTS (SELECT 1 FROM sys.indexes AS i
                         WHERE i.object_id = t.object_id AND i.index_id = 1)
            THEN N'CLUSTERED' ELSE N'HEAP' END AS base_layout,
       SUM(CASE WHEN p.index_id IN (0, 1) THEN p.rows ELSE 0 END) AS metadata_rows_approx,
       HAS_PERMS_BY_NAME(QUOTENAME(s.name) + N'.' + QUOTENAME(t.name),
                         'OBJECT', 'SELECT') AS can_select,
       HAS_PERMS_BY_NAME(QUOTENAME(s.name) + N'.' + QUOTENAME(t.name),
                         'OBJECT', 'ALTER') AS can_alter_reference_object
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
LEFT JOIN sys.partitions AS p ON p.object_id = t.object_id
WHERE s.name = N'dbo'
  AND t.name IN (N'DEMO_BIG_TABLE_10K', N'DEMO_BIG_TABLE_100K',
                 N'DEMO_BIG_TABLE_1000K', N'DEMO_BIG_TABLE_15000K')
GROUP BY s.name, t.name, t.object_id
ORDER BY t.name;

SELECT N'COLUMN' AS section, t.name AS table_name, c.column_id, c.name AS column_name,
       ty.name AS data_type, c.max_length, c.precision, c.scale,
       c.is_nullable, c.is_identity, c.is_computed, c.collation_name
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.columns AS c ON c.object_id = t.object_id
JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
WHERE s.name = N'dbo'
  AND t.name IN (N'DEMO_BIG_TABLE_10K', N'DEMO_BIG_TABLE_100K',
                 N'DEMO_BIG_TABLE_1000K', N'DEMO_BIG_TABLE_15000K')
ORDER BY t.name, c.column_id;

SELECT N'INDEX' AS section, t.name AS table_name, i.index_id, i.name AS index_name,
       i.type_desc, i.is_unique, i.is_primary_key, i.is_unique_constraint,
       i.has_filter, i.filter_definition, i.is_disabled
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.indexes AS i ON i.object_id = t.object_id
WHERE s.name = N'dbo'
  AND t.name IN (N'DEMO_BIG_TABLE_10K', N'DEMO_BIG_TABLE_100K',
                 N'DEMO_BIG_TABLE_1000K', N'DEMO_BIG_TABLE_15000K')
ORDER BY t.name, i.index_id;

SELECT N'INDEX_COLUMN' AS section, t.name AS table_name,
       i.name AS index_name, ic.index_id, ic.index_column_id,
       ic.key_ordinal, ic.is_included_column, ic.is_descending_key,
       c.name AS column_name
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.indexes AS i ON i.object_id = t.object_id
JOIN sys.index_columns AS ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
JOIN sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE s.name = N'dbo'
  AND t.name IN (N'DEMO_BIG_TABLE_10K', N'DEMO_BIG_TABLE_100K',
                 N'DEMO_BIG_TABLE_1000K', N'DEMO_BIG_TABLE_15000K')
ORDER BY t.name, ic.index_id, ic.index_column_id;

SELECT N'KEY_CONSTRAINT' AS section, t.name AS table_name,
       k.name AS constraint_name, k.type_desc,
       i.name AS supporting_index
FROM sys.key_constraints AS k
JOIN sys.tables AS t ON t.object_id = k.parent_object_id
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
LEFT JOIN sys.indexes AS i ON i.object_id = k.parent_object_id
                          AND i.index_id = k.unique_index_id
WHERE s.name = N'dbo'
  AND t.name IN (N'DEMO_BIG_TABLE_10K', N'DEMO_BIG_TABLE_100K',
                 N'DEMO_BIG_TABLE_1000K', N'DEMO_BIG_TABLE_15000K')
ORDER BY t.name, k.name;

SELECT N'FOREIGN_KEY' AS section, t.name AS table_name,
       fk.name AS constraint_name, fk.is_disabled, fk.is_not_trusted
FROM sys.foreign_keys AS fk
JOIN sys.tables AS t ON t.object_id = fk.parent_object_id
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE s.name = N'dbo'
  AND t.name IN (N'DEMO_BIG_TABLE_10K', N'DEMO_BIG_TABLE_100K',
                 N'DEMO_BIG_TABLE_1000K', N'DEMO_BIG_TABLE_15000K')
ORDER BY t.name, fk.name;

SELECT N'CHECK_CONSTRAINT' AS section, t.name AS table_name,
       ck.name AS constraint_name, ck.definition,
       ck.is_disabled, ck.is_not_trusted
FROM sys.check_constraints AS ck
JOIN sys.tables AS t ON t.object_id = ck.parent_object_id
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE s.name = N'dbo'
  AND t.name IN (N'DEMO_BIG_TABLE_10K', N'DEMO_BIG_TABLE_100K',
                 N'DEMO_BIG_TABLE_1000K', N'DEMO_BIG_TABLE_15000K')
ORDER BY t.name, ck.name;

SELECT N'DEFAULT_CONSTRAINT' AS section, t.name AS table_name,
       c.name AS column_name, dc.name AS constraint_name, dc.definition
FROM sys.default_constraints AS dc
JOIN sys.tables AS t ON t.object_id = dc.parent_object_id
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.columns AS c ON c.object_id = dc.parent_object_id
                     AND c.column_id = dc.parent_column_id
WHERE s.name = N'dbo'
  AND t.name IN (N'DEMO_BIG_TABLE_10K', N'DEMO_BIG_TABLE_100K',
                 N'DEMO_BIG_TABLE_1000K', N'DEMO_BIG_TABLE_15000K')
ORDER BY t.name, c.column_id;

DECLARE @Scan15000K bit = 0;
DECLARE @Scale nvarchar(12), @Table sysname, @RunScan bit;
DECLARE @ObjectId int, @Qualified nvarchar(300), @Sql nvarchar(max);
DECLARE target_cursor CURSOR LOCAL FAST_FORWARD FOR
    SELECT scale_label, table_name, run_scan
    FROM (VALUES
        (N'10K', N'DEMO_BIG_TABLE_10K', CONVERT(bit, 1)),
        (N'100K', N'DEMO_BIG_TABLE_100K', CONVERT(bit, 1)),
        (N'1000K', N'DEMO_BIG_TABLE_1000K', CONVERT(bit, 1)),
        (N'15000K', N'DEMO_BIG_TABLE_15000K', @Scan15000K)
    ) AS v(scale_label, table_name, run_scan);

OPEN target_cursor;
FETCH NEXT FROM target_cursor INTO @Scale, @Table, @RunScan;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @Qualified = QUOTENAME(N'dbo') + N'.' + QUOTENAME(@Table);
    SET @ObjectId = OBJECT_ID(@Qualified, N'U');
    IF @ObjectId IS NULL
        SELECT N'SCAN_STATUS' AS section, @Scale AS scale_label,
               N'NOT_EXECUTED: table missing or not visible' AS status;
    ELSE IF @RunScan = 0
        SELECT N'SCAN_STATUS' AS section, @Scale AS scale_label,
               N'NOT_EXECUTED: optional 15M exact scan disabled' AS status;
    ELSE IF (SELECT COUNT(DISTINCT c.name) FROM sys.columns AS c
             WHERE c.object_id = @ObjectId
               AND c.name IN (N'ID', N'OWNER', N'OBJECT_TYPE',
                              N'OBJECT_ID', N'TEMPORARY')) <> 5
        SELECT N'SCAN_STATUS' AS section, @Scale AS scale_label,
               N'NOT_EXECUTED: one or more required columns absent' AS status;
    ELSE
    BEGIN
        SET @Sql = N'
SELECT N''PREDICATE_COUNTS'' AS section, @Scale AS scale_label,
       COUNT_BIG(*) AS total_rows,
       COALESCE(SUM(CASE WHEN TRY_CONVERT(bigint, [OBJECT_ID]) BETWEEN 100 AND 500
                         THEN CONVERT(bigint,1) ELSE CONVERT(bigint,0) END),0) AS object_id_100_500,
       COALESCE(SUM(CASE WHEN [OWNER] = N''SYS'' AND [OBJECT_TYPE] = N''TABLE''
                         THEN CONVERT(bigint,1) ELSE CONVERT(bigint,0) END),0) AS sys_table,
       COALESCE(SUM(CASE WHEN [TEMPORARY] = N''Y''
                         THEN CONVERT(bigint,1) ELSE CONVERT(bigint,0) END),0) AS temporary_y,
       COALESCE(SUM(CASE WHEN [ID] IS NULL THEN CONVERT(bigint,1) ELSE CONVERT(bigint,0) END),0) AS id_null,
       COALESCE(SUM(CASE WHEN [OBJECT_ID] IS NULL THEN CONVERT(bigint,1) ELSE CONVERT(bigint,0) END),0) AS object_id_null,
       COALESCE(SUM(CASE WHEN [OBJECT_ID] IS NOT NULL AND TRY_CONVERT(bigint,[OBJECT_ID]) IS NULL
                         THEN CONVERT(bigint,1) ELSE CONVERT(bigint,0) END),0) AS object_id_not_bigint,
       COALESCE(SUM(CASE WHEN [OWNER] IS NULL THEN CONVERT(bigint,1) ELSE CONVERT(bigint,0) END),0) AS owner_null,
       COALESCE(SUM(CASE WHEN [OBJECT_TYPE] IS NULL THEN CONVERT(bigint,1) ELSE CONVERT(bigint,0) END),0) AS object_type_null,
       COALESCE(SUM(CASE WHEN [TEMPORARY] IS NULL THEN CONVERT(bigint,1) ELSE CONVERT(bigint,0) END),0) AS temporary_null
FROM ' + @Qualified + N';
SELECT N''SAMPLE_IDS'' AS section, @Scale AS scale_label,
       [ID], [OBJECT_ID], [OWNER], [OBJECT_TYPE], [TEMPORARY]
FROM ' + @Qualified + N'
WHERE [ID] IN (1, 5000, 10000, 100000, 1000000)
ORDER BY [ID];';
        BEGIN TRY
            EXEC sys.sp_executesql @Sql, N'@Scale nvarchar(12)', @Scale = @Scale;
        END TRY
        BEGIN CATCH
            SELECT N'SCAN_ERROR' AS section, @Scale AS scale_label,
                   ERROR_NUMBER() AS error_number, ERROR_MESSAGE() AS error_message;
        END CATCH;
    END;
    FETCH NEXT FROM target_cursor INTO @Scale, @Table, @RunScan;
END;
CLOSE target_cursor;
DEALLOCATE target_cursor;
