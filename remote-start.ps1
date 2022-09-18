#host should be pi@raspberrypi
#add ssh key and config for MyPy before running this

scp face_cap.py services.py face_cap.service face_cap_install.sh pi:~/MyPy

ssh pi 'cd ~/MyPy/ ; sudo ./face_cap_install.sh'