@echo off
rem Mulai instance PostgreSQL khusus relay PusatkuPOS (port 5433).
set "PGBIN=C:\Program Files\PostgreSQL\18\bin"
"%PGBIN%\pg_ctl.exe" -D "%~dp0data\pg_relay" -l "%~dp0data\pg_relay\server.log" -o "-p 5433" start
if errorlevel 1 (
  echo PostgreSQL relay mungkin sudah berjalan. Periksa port 5433.
)
