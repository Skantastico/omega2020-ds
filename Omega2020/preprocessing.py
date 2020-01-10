import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from IPython.display import Image
import cv2
import os
import torch
import pickle
from random import shuffle
import operator

class Preprocess:
    """
    Class based preprocessing functions to transform, resize, and
    change images to be passed on for predictions to the model
    """

    def __init__(self, img):

        self.img = img

    def pre_process_image(img, skip_dilate=False):
        """Uses a blurring function, adaptive thresholding and dilation to expose the main features of an image."""
         # Gaussian blur with a kernal size (height, width) of 9.
        # Note that kernal sizes must be positive and odd and the kernel must be square.
        proc = cv2.GaussianBlur(img.copy(), (9, 9), 0)
        # Adaptive threshold using 11 nearest neighbour pixels
        proc = cv2.adaptiveThreshold(proc, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)
        # Invert colours, so gridlines have non-zero pixel values.
        # Necessary to dilate the image, otherwise will look like erosion instead.
        proc = cv2.bitwise_not(proc, proc)
        #if not skip_dilate:
        #    # Dilate the image to increase the size of the grid lines.
        #    kernel = np.array([[0., 1., 0.], [1., 1., 1.], [0., 1., 0.]])
        #    proc = cv2.dilate(proc, kernel)
        return proc

    def find_corners_of_largest_polygon(img):
        """Finds the 4 extreme corners of the largest contour in the image."""
        contours, h = cv2.findContours(img.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)  # Find contours
        contours = sorted(contours, key=cv2.contourArea, reverse=True)  # Sort by area, descending
        polygon = contours[0]  # Largest image
        # Use of `operator.itemgetter` with `max` and `min` allows us to get the index of the point
        # Each point is an array of 1 coordinate, hence the [0] getter, then [0] or [1] used to get x and y respectively.
        # Bottom-right point has the largest (x + y) value
        # Top-left has point smallest (x + y) value
        # Bottom-left point has smallest (x - y) value
        # Top-right point has largest (x - y) value
        bottom_right, _ = max(enumerate([pt[0][0] + pt[0][1] for pt in polygon]), key=operator.itemgetter(1))
        top_left, _ = min(enumerate([pt[0][0] + pt[0][1] for pt in polygon]), key=operator.itemgetter(1))
        bottom_left, _ = min(enumerate([pt[0][0] - pt[0][1] for pt in polygon]), key=operator.itemgetter(1))
        top_right, _ = max(enumerate([pt[0][0] - pt[0][1] for pt in polygon]), key=operator.itemgetter(1))
        # Return an array of all 4 points using the indices
        # Each point is in its own array of one coordinate
        return [polygon[top_left][0], polygon[top_right][0], polygon[bottom_right][0], polygon[bottom_left][0]]
    def display_points(in_img, points, radius=5, colour=(0, 0, 255)):
        """Draws circular points on an image."""
        img = in_img.copy()
            # Dynamically change to a colour image if necessary
        if len(colour) == 3:
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            elif img.shape[2] == 1:
                img = find_corners_of_largest_polygon(img)
        """Finds the 4 extreme corners of the largest contour in the image."""
        contours, h = cv2.findContours(img.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)  # Find contours
        contours = sorted(contours, key=cv2.contourArea, reverse=True)  # Sort by area, descending
        polygon = contours[0]  # Largest image
        # Use of `operator.itemgetter` with `max` and `min` allows us to get the index of the point
        # Each point is an array of 1 coordinate, hence the [0] getter, then [0] or [1] used to get x and y respectively.
        # Bottom-right point has the largest (x + y) value
        # Top-left has point smallest (x + y) value
        # Bottom-left point has smallest (x - y) value
        # Top-right point has largest (x - y) value
        bottom_right, _ = max(enumerate([pt[0][0] + pt[0][1] for pt in polygon]), key=operator.itemgetter(1))
        top_left, _ = min(enumerate([pt[0][0] + pt[0][1] for pt in polygon]), key=operator.itemgetter(1))
        bottom_left, _ = min(enumerate([pt[0][0] - pt[0][1] for pt in polygon]), key=operator.itemgetter(1))
        top_right, _ = max(enumerate([pt[0][0] - pt[0][1] for pt in polygon]), key=operator.itemgetter(1))
        for point in points:
            img = cv2.circle(img, tuple(int(x) for x in point), radius, colour, -1)
        return img

    def show_image(img):
        """Shows an image until any key is pressed."""
        cv2.imshow('image', img)  # Display the image
        cv2.waitKey(0)  # Wait for any key to be pressed (with the image window active)
        cv2.destroyAllWindows()  # Close all windows


    def distance_between(p1, p2):
        """Returns the scalar distance between two points"""
        a = p2[0] - p1[0]
        b = p2[1] - p1[1]
        return np.sqrt((a ** 2) + (b ** 2))

    def crop_and_warp(img, crop_rect):
        """Crops and warps a rectangular section from an image into a square of similar size."""
        # Rectangle described by top left, top right, bottom right and bottom left points
        top_left, top_right, bottom_right, bottom_left = crop_rect[0], crop_rect[1], crop_rect[2], crop_rect[3]
        # Explicitly set the data type to float32 or `getPerspectiveTransform` will throw an error
        src = np.array([top_left, top_right, bottom_right, bottom_left], dtype='float32')
        # Get the longest side in the rectangle
        side = max([
            Preprocess.distance_between(bottom_right, top_right),
            Preprocess.distance_between(top_left, bottom_left),
            Preprocess.distance_between(bottom_right, bottom_left),
            Preprocess.distance_between(top_left, top_right)
        ])
        # Describe a square with side of the calculated length, this is the new perspective we want to warp to
        dst = np.array([[0, 0], [side - 1, 0], [side - 1, side - 1], [0, side - 1]], dtype='float32')
        # Gets the transformation matrix for skewing the image to fit a square by comparing the 4 before and after points
        m = cv2.getPerspectiveTransform(src, dst)
        # Performs the transformation on the original image
        return cv2.warpPerspective(img, m, (int(side), int(side)))


    def resize(img):
        W = 1000
        heigh, width, depth = img.shape
        imgScale = W/width
        newX, newY = img.shape[1]*imgScale, img.shape[0]*imgScale
        new_img = cv2.resize(img, (int(newX), int(newY)))
        #cv2.imshow("Show by CV2", new_img)
        #cv2.waitKey(0)
        return new_img

    def invert(new_img):
        #just_img, thresh1 = cv2.threshold(new_img, 200, 255, cv2.THRESH_BINARY)
        #nvert_img = cv2.bitwise_not(new_img)
        invert_gray = cv2.cvtColor(new_img, cv2.COLOR_BGR2GRAY)
        threshold = cv2.adaptiveThreshold(invert_gray,255,cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY,11,2)
        #kernel_sharpening = np.array([[-1,-1,-1],
        #                            [-1, 9,-1],
        #                            [-1,-1,-1]])
        # applying the sharpening kernel to the input image & displaying it.
        #sharpened = cv2.filter2D(th3, -1, kernel_sharpening)
        #sharpened = cv2.bitwise_not(sharpened)

        return ~threshold

    def boxes(sharpened):
        rows = [(15,125), (125,225), (235,335), (340,440), (455,555), (570,670), (680,780), (775,875), (890,990)]
        columns = [(30,130), (130,230), (240,340), (355,455), (455,555), (565,665), (670,770), (800,900),(890,990)]
        images_list = []
        for unit in rows:
            for units in columns:
                images_list.append(sharpened[unit[0]:unit[1], units[0]:units[1]])
                pass

        final_images = []
        for i in range(len(images_list)):
            resize_img = cv2.resize(images_list[i], (28,28))
            #resize_img = ~resize_img
            #new_img = cv2.threshold(resize_img, 115, 255, cv2.THRESH_BINARY)
            final_images.append(resize_img)

        cntr_img= []
        for i in range(len(final_images)):
            ret, thresh = cv2.threshold(final_images[i], 200, 255, 0)
            contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
            for c in contours:
                (x, y, w, h) = cv2.boundingRect(contours[0])
                crop = final_images[i][y:y+h, x:x+w]
                borderType = cv2.BORDER_CONSTANT
                top = int(0.35 * crop.shape[0])
                bottom = top
                left = int(0.35 * crop.shape[1])
                right = left
                border_img = cv2.copyMakeBorder(crop, top, bottom, left, right, borderType)
                border_img = cv2.resize(border_img, (28,28))
            cntr_img.append(border_img)

        return final_images