#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 13 11:45:52 2018

@author: jason9075
ref: https://gist.github.com/khanhnamle1994/e2ff59ddca93c0205ac4e566d40b5e88
"""

from __future__ import print_function
import tensorflow as tf
import os
import random
import numpy as np
import scipy.misc
from glob import glob

#--------------------------
# USER-SPECIFIED DATA
#--------------------------

# Tune these parameters
DEBUG = False
SAVE_MODEL = True
SAVE_LOG = False
NUMBER_OF_CLASSES = 2
IMAGE_RESIZE_SHAPE = (640, 360)
IMAGE_SHAPE = (352, 352)
EPOCHS = 1 if DEBUG else 20
BATCH_SIZE = 16
DROPOUT = 0.7

# Specify these directory paths

runs_dir = '.'
training_dir ='data/'
mask_dir ='mask/'
vgg_path = 'vgg/'
model_output_dir = 'model_output/'

#--------------------------
# PLACEHOLDER TENSORS
#--------------------------

correct_label = tf.placeholder(tf.float32, [None, IMAGE_SHAPE[0], IMAGE_SHAPE[1], NUMBER_OF_CLASSES])
learning_rate = tf.placeholder(tf.float32)
keep_prob = tf.placeholder(tf.float32)

def load_vgg(sess, vgg_path):
  
  # load the model and weights
  model = tf.saved_model.loader.load(sess, ['vgg16'], vgg_path)

  # Get Tensors to be returned from graph
  graph = tf.get_default_graph()
  image_input = graph.get_tensor_by_name('image_input:0')
  keep_prob = graph.get_tensor_by_name('keep_prob:0')
  layer3 = graph.get_tensor_by_name('layer3_out:0')
  layer4 = graph.get_tensor_by_name('layer4_out:0')
  layer7 = graph.get_tensor_by_name('layer7_out:0')

  return image_input, keep_prob, layer3, layer4, layer7

def layers(vgg_layer3_out, vgg_layer4_out, vgg_layer7_out, num_classes):
   
  # Use a shorter variable name for simplicity
  layer3, layer4, layer7 = vgg_layer3_out, vgg_layer4_out, vgg_layer7_out

  # Apply 1x1 convolution in place of fully connected layer
  fcn8 = tf.layers.conv2d(layer7, filters=num_classes, kernel_size=1, name="fcn8")

  # Upsample fcn8 with size depth=(4096?) to match size of layer 4 so that we can add skip connection with 4th layer
  fcn9 = tf.layers.conv2d_transpose(fcn8, filters=layer4.get_shape().as_list()[-1],
                                    kernel_size=4, strides=(2, 2), padding='SAME', name="fcn9")

  # Add a skip connection between current final layer fcn8 and 4th layer
  fcn9_skip_connected = tf.add(fcn9, layer4, name="fcn9_plus_vgg_layer4")

  # Upsample again
  fcn10 = tf.layers.conv2d_transpose(fcn9_skip_connected, filters=layer3.get_shape().as_list()[-1],
                                     kernel_size=4, strides=(2, 2), padding='SAME', name="fcn10_conv2d")

  # Add skip connection
  fcn10_skip_connected = tf.add(fcn10, layer3, name="fcn10_plus_vgg_layer3")

  # Upsample again
  fcn11 = tf.layers.conv2d_transpose(fcn10_skip_connected, filters=num_classes,
                                     kernel_size=16, strides=(8, 8), padding='SAME', name="fcn11")

  return fcn11


def optimize(nn_last_layer, correct_label, learning_rate, num_classes):
  
  # Reshape 4D tensors to 2D, each row represents a pixel, each column a class
  logits = tf.reshape(nn_last_layer, (-1, num_classes), name="fcn_logits")
  correct_label_reshaped = tf.reshape(correct_label, (-1, num_classes))

  # Calculate distance from actual labels using cross entropy
  cross_entropy = tf.nn.softmax_cross_entropy_with_logits(logits=logits, labels=correct_label_reshaped[:])
  # Take mean for total loss
  loss_op = tf.reduce_mean(cross_entropy, name="fcn_loss")

  # The model implements this operation to find the weights/parameters that would yield correct pixel labels
  train_op = tf.train.AdamOptimizer(learning_rate=learning_rate).minimize(loss_op, name="fcn_train_op")

  return logits, train_op, loss_op

def centeredCrop(img, image_shape):

  width =  np.size(img,1)
  height =  np.size(img,0)

  left = np.ceil((width - image_shape[1])/2.)
  top = np.ceil((height - image_shape[0])/2.)
  right = np.floor((width + image_shape[1])/2.)
  bottom = np.floor((height + image_shape[0])/2.)
  cImg = img[int(top):int(bottom), int(left):int(right)]
  return cImg
   
def gen_batch_function(image_shape):
    
  def get_batches_fn(batch_size):
    image_paths = glob(os.path.join(training_dir, '*.png'))    
    label_paths = {
            os.path.basename(path):
            path for path in glob(os.path.join(mask_dir, '*.png'))}
    
    #背景為黑色
    background_color = np.array([0, 0, 0])

    random.shuffle(image_paths)
    if(DEBUG):
      image_paths = image_paths[0:batch_size*2]

    for batch_i in range(0, len(image_paths), batch_size):
      images = []
      gt_images = []
      for image_file in image_paths[batch_i:batch_i+batch_size]:
        gt_image_file = label_paths[os.path.basename(image_file)]

        image = scipy.misc.imresize(scipy.misc.imread(image_file), IMAGE_RESIZE_SHAPE)
        gt_image = scipy.misc.imresize(scipy.misc.imread(gt_image_file), IMAGE_RESIZE_SHAPE)

        image = centeredCrop(image, IMAGE_SHAPE)
        gt_image = centeredCrop(gt_image, IMAGE_SHAPE)

        gt_bg = np.all(gt_image == background_color, axis=2)
        gt_bg = gt_bg.reshape(*gt_bg.shape, 1)
        gt_image = np.concatenate((gt_bg, np.invert(gt_bg)), axis=2)

        images.append(image)
        gt_images.append(gt_image)

      yield np.array(images), np.array(gt_images)
  return get_batches_fn


def train_nn(sess, epochs, batch_size, train_op,
             cross_entropy_loss, input_image,
             correct_label, keep_prob, learning_rate):
  
  gen_function = gen_batch_function(IMAGE_SHAPE)

  keep_prob_value = 0.5
  learning_rate_value = 0.001
  for epoch in range(epochs):
    # Create function to get batches
    total_loss = 0
    
    for X_batch, gt_batch in gen_function(batch_size):
      
      loss, _ = sess.run([cross_entropy_loss, train_op],
                         feed_dict={input_image: X_batch, correct_label: gt_batch,
                                    keep_prob: keep_prob_value, learning_rate:learning_rate_value})

      total_loss += loss;

    print("EPOCH {} ...".format(epoch + 1))
    print("Loss = {:.3f}".format(total_loss))
    print()
  
  
def run():

  # A function to get batches    
  with tf.Session() as session:        
    # Returns the three layers, keep probability and input layer from the vgg architecture
    image_input, keep_prob, layer3, layer4, layer7 = load_vgg(session, vgg_path)

    # The resulting network architecture from adding a decoder on top of the given vgg model
    model_output = layers(layer3, layer4, layer7, NUMBER_OF_CLASSES)

    # Returns the output logits, training operation and cost operation to be used
    # - logits: each row represents a pixel, each column a class
    # - train_op: function used to get the right parameters to the model to correctly label the pixels
    # - cross_entropy_loss: function outputting the cost which we are minimizing, lower cost should yield higher accuracy
    logits, train_op, cross_entropy_loss = optimize(model_output, correct_label, learning_rate, NUMBER_OF_CLASSES)
    
    # Initialize all variables
    session.run(tf.global_variables_initializer())
    session.run(tf.local_variables_initializer())

    print("Model build successful, starting training")

    # Train the neural network
      
    train_nn(session, EPOCHS, BATCH_SIZE, train_op,
             cross_entropy_loss, image_input,
             correct_label, keep_prob, learning_rate)
    
    if(SAVE_LOG):
      writer = tf.summary.FileWriter("logs/", session.graph)

    
    print("All done!")
    if(SAVE_MODEL):
      saver = tf.train.Saver()
      save_path = saver.save(session, model_output_dir + "model.ckpt")
      
      
from PIL import Image

def predict():
  
  image = scipy.misc.imresize(scipy.misc.imread("data/frame-00155.png"), IMAGE_RESIZE_SHAPE)

  image = centeredCrop(image, IMAGE_SHAPE)
  image = np.expand_dims(image, axis=0)
  
  detect_frames = []
  with tf.Session() as sess:

    
# =============================================================================
#     image_input, keep_prob, layer3, layer4, layer7 = load_vgg(sess, vgg_path)
#     model_output = layers(layer3, layer4, layer7, NUMBER_OF_CLASSES)
#     logits, train_op, cross_entropy_loss = optimize(model_output, correct_label, learning_rate, NUMBER_OF_CLASSES)
#     
#     saver = tf.train.Saver()
# =============================================================================
    saver.restore(sess, model_output_dir + "model.ckpt")
    count=0
    for frame in frames:
      frame = np.expand_dims(frame, axis=0)
      result = sess.run(model_output, feed_dict={image_input: frame,
                                               keep_prob: 1})
      count = count+1
      print("index: %d"%count)
      detect_frames.append(result[0])
      
      
  result = detect_frames[710]
  result = np.argmax(result, axis=2)
  
  img_array = []
  for x in result.reshape(352*352):
      if x == 0:
          img_array.append((0,0,0,0))
      elif x == 1:
          img_array.append((0,255,0,90))
  
  img = Image.new('RGBA',(352,352))
  img.putdata(img_array)
  
  img.show()

    result_img=Image.fromarray(test)
    result_img.show()
    
import cv2

    
def video():
  vidcap = cv2.VideoCapture('video/room.mp4')  
  frames = []
  success, frame = vidcap.read()
  count=0
  while success:
    frame = scipy.misc.imresize(frame, IMAGE_RESIZE_SHAPE)
    frame = centeredCrop(frame, IMAGE_SHAPE)
    frames.append(frame)
    success, frame = vidcap.read()

    
  
  out = cv2.VideoWriter('outpy.avi',cv2.VideoWriter_fourcc('M','J','P','G'), 30, IMAGE_SHAPE)
  for i in range(0, len(frames)):
    frame = Image.fromarray(frames[i][...,::-1], 'RGB').convert("RGBA")  #BGR->RGB->RGBA
 
    detect_frame = np.argmax(detect_frames[i], axis=2)
    img_array = []
    for x in detect_frame.reshape(352*352):
        if x == 0:
            img_array.append((0,0,0,0))
        elif x == 1:
            img_array.append((0,255,0,180))
    
    overlay = Image.new('RGBA',(352,352))
    overlay.putdata(img_array)
    
    frame.paste(overlay, (0, 0), overlay)

    out.write(np.asarray(frame))
  out.release()
  

  
def realtime():
  cap = cv2.VideoCapture(0)
  cap.set(3, 352) #width
  cap.set(4, 352) #height
  while(True):
    ret, frame = cap.read()
  
    cv2.imshow('frame', frame)
  
    if cv2.waitKey(1) & 0xFF == ord('q'):
      break

  cap.release()
  cv2.destroyAllWindows()
    
if __name__ == '__main__':
  run()