
/* SSMS entry point for the UC1 benchmark.
   Enable Query > SQLCMD Mode. Run uc1_setup.sql once to create copies.
   Execute this ENTIRE file (F5, no selected text) in one query window.
   Run uc1_diagnostics.sql separately afterward and save its plans.

   :r expands uc1_benchmark.sql here; that file loads benchmark_core.sql
   itself. GO ends a batch but keeps the connection alive. Do not use :connect.
   To repeat after a completed run, clean up the copies and set up again.
*/
:on error exit

USE [DBMS_EW_Group02];
GO

SELECT N'UC1_SESSION_BEFORE_BENCHMARK' AS section, @@SPID AS session_id,
       DB_NAME() AS database_name;
GO

:r W:\MYSELF\HCMUT-university\Senior\HK_261\DBMS\BTL\DBMS_EW_Group2\sql\uc1_compound\uc1_benchmark.sql
