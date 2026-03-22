@echo off
cd /d d:\home\ruView\services\camera-service
set OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0
python camera_worker.py
pause
