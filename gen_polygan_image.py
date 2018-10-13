#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 13 14:22:37 2018

@author: jason9075
"""

from PIL import Image, ImageDraw
import xml.etree.ElementTree as ET
import os


for imageFile in os.listdir('data/'):
  name = os.path.splitext(imageFile)[0]
  
  if(not name.startswith('frame')):
    continue

  im = Image.open('data/' + name + '.png')
  
  tree = ET.parse('label/' + name + '.xml')
  polygon = tree.find('object/polygon')
  
  mask = Image.new('RGB', im.size)
  #該圖有polygon
  if(polygon!=None):
    coord_list = []
    for i in range(1, int(len(polygon.getchildren())/2 + 1)):
      x = polygon.find('x%d' % i).text
      y = polygon.find('y%d' % i).text
      coord_list.append((int(x),int(y)))
    
    d = ImageDraw.Draw(mask)
    d.polygon(tuple(coord_list), outline='#000', fill='#0F0')

  mask.save('mask/'+name+'.png')
  print("save:"+name)
          
#out = Image.new('RGBA', im.size)
#out.paste(im, (0, 0), mask)
#out.show()