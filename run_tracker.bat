@echo off
cd /d C:\claude\price-tracker
if not exist logs mkdir logs
python tracker.py >> logs\tracker.log 2>&1
