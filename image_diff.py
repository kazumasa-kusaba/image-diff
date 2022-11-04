import sys
import argparse
import pathlib
import math
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from utils.progress_bar import ProgressBar

def print_software_information():
  print("image-diff version 1.00")
  print("(https://github.com/kazumasa-kusaba/image-diff)\n")

class ThreadParams:
  def __init__(self, 
               start_x:int, end_x:int,
               start_y:int, end_y:int,
               delta_x:int, delta_y:int, 
               thresh:int,
               image1, image2, 
               diff_image):
    self.start_x = start_x
    self.end_x = end_x
    self.start_y = start_y
    self.end_y = end_y
    self.delta_x = delta_x
    self.delta_y = delta_y
    self.thresh = thresh
    self.image1 = image1
    self.image2 = image2
    self.diff_image = diff_image

class ThreadResult:
  def __init__(self, diff_cnt:int, progress:int):
    self.diff_cnt = diff_cnt
    self.progress = progress

def calcurate_distance(thread_params:ThreadParams) -> ThreadResult:
  diff_cnt = 0
  progress = 0

  for x in range(thread_params.start_x, thread_params.end_x):
    for y in range(thread_params.start_y, thread_params.end_y):
      new_x, new_y = thread_params.delta_x + x, thread_params.delta_y + y
      if new_x < 0:
        new_x = 0
      elif len(thread_params.diff_image) <= new_x:
        new_x = len(thread_params.diff_image) - 1
      if new_y < 0:
        new_y = 0
      elif len(thread_params.diff_image[0]) <= new_y:
        new_y = len(thread_params.diff_image[0]) - 1
      distance = math.sqrt(
        (int(thread_params.image1[new_x][new_y][0]) - int(thread_params.image2[x][y][0])) ** 2
        + (int(thread_params.image1[new_x][new_y][1]) - int(thread_params.image2[x][y][1])) ** 2
        + (int(thread_params.image1[new_x][new_y][2]) - int(thread_params.image2[x][y][2])) ** 2)
      if distance >= thread_params.thresh:
        thread_params.diff_image[x][y][2] = 255
        diff_cnt += 1
      progress += 1
  
  return ThreadResult(diff_cnt, progress)

if __name__ == "__main__":
  print_software_information()

  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument("FILE1", type=str, help="A first image file name to compare.")
  arg_parser.add_argument("FILE2", type=str, help="A second image file name to compare.")
  arg_parser.add_argument("-rx", "--range-x", type=int, default=0, help="Range of X coordinates to move the image.")
  arg_parser.add_argument("-ry", "--range-y", type=int, default=0, help="Range of Y coordinates to move the image.")
  arg_parser.add_argument("-th", "--thresh", type=int, default=30, help="Threshold to be considered different pixel if greater than.")
  arg_parser.add_argument("-j", "--jobs", type=int, default=4, help="Number of jobs to process.")
  args = arg_parser.parse_args()

  try:
    file1_path = pathlib.Path(args.FILE1)
    file2_path = pathlib.Path(args.FILE2)
  except Exception as e:
    print(e)
    sys.exit(1)
  
  try:
    image1 = cv2.imread(str(file1_path))
    image2 = cv2.imread(str(file2_path))
  except Exception as e:
    print(e)
    sys.exit(1)

  if image1.shape != image2.shape:
    print("They are not the same size...")
    print("(%d x %d != %d x %d)" % (len(image1[0]), len(image1), len(image2[0]), len(image2)))
    print("Do you want to adjust the size of the image of FILE2 to the size of image of FILE1 and continue?")
    print("[Y/n]:", end="")
    val = input()
    if val == "Y":
      image2 = cv2.resize(image2, dsize=(len(image1[0]), len(image1)))
    else:
      print("Error! Resize the images by yourself!")
      sys.exit(1)
  
  if args.jobs <= 0:
    print("Error! %d jobs is invalid!" % args.jobs)
    sys.exit(1)
  elif args.jobs == 1:
    partition = len(image1)
  elif args.jobs < len(image1):
    partition = args.jobs
  else:
    partition = len(image1)
  
  min_diff_cnt = float('inf')
  diff_image = np.zeros(image1.shape)

  progress, max_value = 0, (args.range_x * 2 + 1) * (args.range_y * 2 + 1) * len(diff_image) * len(diff_image[0]) - 1
  pb = ProgressBar(progress=0, max_value=max_value)
  pb.print_progress_bar()

  for delta_x in range(-args.range_x, args.range_x + 1):
    for delta_y in range(-args.range_y, args.range_y + 1):
      candidate_diff_image = np.zeros(image1.shape)
      candidate_diff_cnt = 0

      executor = ThreadPoolExecutor(max_workers=args.jobs)
      futures = []

      q, m = divmod(len(candidate_diff_image), partition)
      for x in range(0, q * partition, q):
        thread_params = ThreadParams(x, x + q,
                                     0, len(candidate_diff_image[0]),
                                     delta_x, delta_y, 
                                     args.thresh, 
                                     image1, image2,
                                     candidate_diff_image)
        future = executor.submit(calcurate_distance, thread_params)
        futures.append(future)
      if m > 0 or q == partition:
        thread_params = ThreadParams(q * partition, q * partition + m,
                                     0, len(candidate_diff_image[0]),
                                     delta_x, delta_y,
                                     args.thresh,
                                     image1, image2,
                                     candidate_diff_image)
        future = executor.submit(calcurate_distance, thread_params)
        futures.append(future)

      for future in futures:
        result = future.result()
        candidate_diff_cnt += result.diff_cnt
        progress += result.progress

      if candidate_diff_cnt < min_diff_cnt:
        diff_image = candidate_diff_image
        min_diff_cnt = candidate_diff_cnt

      pb.set_progress(progress)
      pb.print_progress_bar()

  pb.end()

  cv2.imshow("diff_image", diff_image)
  cv2.waitKey()

