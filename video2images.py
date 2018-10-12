#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 28 12:43:29 2018

@author: jason9075
"""

import cv2

vidcap = cv2.VideoCapture('video/room.mp4')
success,image = vidcap.read()
count = 0
while success:
  if(count % 5 == 0):
    cv2.imwrite("data/lego1-%d.jpg" % count, image)     # save frame as JPEG file      

  success,image = vidcap.read()
  print('Read a new frame: ', success)
  count += 1
  
  
  
vidcap = cv2.VideoCapture('video/lego2.mp4')
success,image = vidcap.read()
count = 0
while success:
  if(count % 5 == 0):
    cv2.imwrite("data/lego2-%d.jpg" % count, image)     # save frame as JPEG file      

  success,image = vidcap.read()
  print('Read a new frame: ', success)
  count += 1