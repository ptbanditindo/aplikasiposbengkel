@echo off
rem Mulai server relay PusatkuPOS memakai konfigurasi .env (PostgreSQL port 5433).
cd /d "%~dp0"
start "PusatkuPOS Relay" /min cmd /c "python run_relay.py --port 8120 >> data\relay_server.log 2>&1"
