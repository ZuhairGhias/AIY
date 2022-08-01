#!/bin/bash

cp face_cap.service /lib/systemd/system/face_cap.service
systemctl daemon-reload
systemctl enable face_cap.service
systemctl start face_cap.service
systemctl status face_cap.service