@echo off
setlocal
cd /d "%~dp0"
set NS_HDR=1
set NS_PHASE=1
runtime\python.exe main.py
