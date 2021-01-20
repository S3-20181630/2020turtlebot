#!/usr/bin/env python
# -*- coding: utf-8 -*- # 한글 주석쓰려면 이거 해야함

import cv2
import numpy as np
import sys
import math
import rospy
import time
import os

from std_msgs.msg import Float64, UInt8, String
from sensor_msgs.msg import CompressedImage
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
import tf
from SlidingWindow2 import Slidingwindow



class line_traceee:
	def __init__(self):
		#print('init')
		self.sub_select_ang = rospy.Subscriber('/usb_cam/image_raw/compressed',CompressedImage, self.move_turtlebot,  queue_size = 1)
		self.sub_detect_sigh = rospy.Subscriber('/detect/traffic_sign', UInt8, self.setting, queue_size=1)
		self.sub_obstacle = rospy.Subscriber('/scan', LaserScan, self.obstacle,queue_size=1)
		self.out2 = cv2.VideoWriter('0920_2.avi',cv2.VideoWriter_fourcc('M','J','P','G'), 30, (640,360))
		self.pub_cmd_vel = rospy.Publisher('/cmd_vel',Twist,queue_size=1)
		
		#self.trafficSign = Enum('trafficSign', 'left right dontgo construction stop parking tunnel')

		self.bridge = CvBridge()

		## left line
		self.lpt1 = (0,0)
		self.lpt2 = (0,0)

		## right line
		self.rpt1 = (0,0)
		self.rpt2 = (0,0)

		self.t1 = 0
		self.t2 = 0
		self.left_angle = 0.0
		self.right_angle = 0.0

		self.is_curve = False

		self.is_left = False
		self.is_right = False
		
		self.left_pos = 0
		self.right_pos = 0
		self.center = 0
		self.lastError = 0
		self.MAX_VEL = 0.2
		### sign
		self.is_leftsign = False ################################## 
		self.is_rightsign = False
		self.is_construction = False
		self.is_parking = False
		self.is_tunnel = False
		self.is_stopsign = False
		### mode
		self.is_mode = False
		self.is_leftMode = False
		self.is_rightMode = False
		self.is_constructionMode = False
		self.is_parkingMode = False
		self.is_tunnelMode = False

		## construction ##
		self.is_obstacle = False
		self.is_avoidMode = False
		self.phase = 1
		self.check = 0
		self.status = 0

		## stop ##
		self.stop_phase = 1
		self.is_stop = False
		self.stopchk =   False
		self.stop_flag = False
		###########		praking		###########
		self.parking_phase = 0
		self.is_left_turtlebot = False
		self.is_right_turtlebot = False
		self.found_turtlebot = False
		self.is_parking_sign = False

		self.praking_cnt = 0
		self.check_back_num_01 = 175
		self.check_back_num_02 = 185

		self.parkingchk = False
		#######################################
		self.HSL_YELLOW_LOWER = np.array([10,5,160])
		self.HSL_YELLOW_UPPER = np.array([40,255,255])

		self.HSL_YELLOW_LOWER2 = np.array([24,17,140])
		self.HSL_YELLOW_UPPER2 = np.array([38,255,255])

		self.HSL_WHITE_LOWER = np.array([0,0,200])
		self.HSL_WHITE_UPPER = np.array([180,255,255])

		self.speed = 0.1
		self.angular = 30 * np.pi/180 #0#35 * np.pi/180#0.0
		self.angular_temp = 0.0

		self.start = False
	def setting(self, mode_msg):
		# print 'setting'
		if self.is_mode == False:
			if mode_msg.data == 1: 												##		left
				print 'Read left'
				self.is_mode = True
				self.is_leftsign = True
				self.angular = 30 * np.pi/180
				self.start = True
				self.is_parking_sign = False
			elif mode_msg.data == 2:											##		right
				print 'Read right'
				self.is_mode = True
				self.is_rightsign = True
				self.angular = -28 * np.pi/180
				self.start = True
			elif mode_msg.data == 4:											##		construction
				print 'Read construction'
				self.is_construction = True
				self.is_leftsign = False
				self.is_rightsign = False
			elif mode_msg.data == 5 :#and self.start == True and self.parkingchk == True:											##		stop
				print 'Read stop'
				self.is_leftsign = False
				self.is_rightsign = False
				self.is_construction =False
				self.is_parking = False
				self.is_stopsign = True
			elif mode_msg.data == 6 :#and self.start == True:											##		parking
				self.is_mode = True
				print 'Read parking'
				self.is_parking_sign = True
				self.is_leftsign = False
				self.is_rightsign = False
				self.is_construction = False
				self.is_obstacle = False
				#self.parkingchk = True

			elif mode_msg.data == 7:											##		tunnel
				return
				# self.is_mode = True
				# print 'Read tunnel'

				# self.is_tunnel = True
			else:
				#print 'No Read'
				pass
		else:
			pass
			if mode_msg.data == 4:# and self.start == True:
				print 'Read Construction'
				# self.is_mode = True
				self.angular = 0
				self.is_construction = True
				self.is_leftsign = False
				self.is_rightsign = False
			elif mode_msg.data == 5 :#and self.start == True and self.parkingchk == True:
				print 'Read stop'
				self.is_leftsign = False
				self.is_rightsign = False
				self.is_construction =False
				self.is_parking = False
				self.is_stopsign = True
			
	def obstacle(self, obstacle_msg):
		msg = obstacle_msg
		#print 'is_confstruction', self.is_construction
		#####
		if self.is_parking_sign:
			if msg.ranges[130] < 0.5:
				self.is_parking = True
			else:
				return

		if self.is_stopsign:
			print msg.ranges[330]
			ragnes = msg.ranges[30:45]
			for i in ragnes:
				if i < 0.3:
					self.stop_flag = True
			if self.stop_flag == True :#0 < msg.ranges[330] < 0.6 :
				# print 'sighnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn'
				startTime = time.time()
				while (True):
					endTime = time.time() - startTime
					if endTime > 1.0:
						self.is_stop = True
						break

		if self.is_construction:
			self.is_leftsign = False
			self.is_rightsign = False	
			print msg.ranges[90]
			if msg.ranges[90] < 0.3 and msg.ranges[90] != 0:
				print 'construction'
				self.is_construction = False
				self.is_obstacle = True
	
		if self.is_obstacle:
			print 'Construction Mode'
			print 'aaaaa', self.phase, msg.ranges[90]
			# cons_left = msg[89 : 92]
			if self.phase == 1:
				# print 'Phase 1' , self.status
				if self.status == 0:
					self.speed = 0.1
					if msg.ranges[90] < 0.3 and msg.ranges[90] != 0 :
						self.status = 1
					else:
						self.angular = 0
				elif self.status == 1:
					self.angular = 0.37

				if msg.ranges[270] < 0.4 and msg.ranges[270] != 0:
					self.phase += 1
					self.status = 0
		
			elif self.phase == 2:
				# print 'Phase 2'
				# print '0 :',msg.ranges[0], '90 :', msg.ranges[90]
				self.angular = -0.4
				if msg.ranges[0] < 0.5 and msg.ranges[0] != 0:
					self.check += 1
				#print self.check
				if self.check != 0 and msg.ranges[70] < 0.5 and msg.ranges[70] != 0:
					self.phase += 1
		
			elif self.phase == 3:
				# self.is_mode = False
				# self.is_obstacle = False
				# print 'Phase 3'
				self.speed = 0.12
				self.angular = 0.36
				if msg.ranges[200] < 0.5 and msg.ranges[200] != 0 :
					self.phase += 1
		
			elif self.phase == 4:
				# print 'Phase 4'
				self.is_mode = False
				#rospy.sleep(rospy.Duration(2))
				self.is_mode = False
				self.is_obstacle = False


			self.move(self.speed, self.angular)
		
		elif self.is_parking:
			check_left = msg.ranges[80:87]
			check_right = msg.ranges[270:277]
			check_back = msg.ranges[self.check_back_num_01:self.check_back_num_02]
			# check_front = msg.ranges[0:5]

			if self.parking_phase == 1:# '''phase 1은 양쪽이 다 노란색인 경우'''
				if self.found_turtlebot == False:#'''터틀봇 찾을때까지'''
					for i in check_left:#'''왼쪽에 잇다'''
						# print check_left
						if 0 < i < 0.6:
							print '왼쪽에 있다.'
							self.is_left_turtlebot = True
							self.is_right_turtlebot = False
							break
					for i in check_right:#'''오른쪽에 잇다'''
						if 0 < i < 0.6:
							self.is_left_turtlebot = False
							self.is_right_turtlebot = True
							break
			elif self.parking_phase == 2:#'''2단계는 뒷통수에 터틀봇 인식 될때가지 제자리서 도는경우'''
				for i in check_back:
					if 0 < i < 0.6:
						self.parking_phase += 1
						break

		if self.stopchk == True and (0 < msg.ranges[270] < 0.2) and self.is_tunnel == False and self.is_left == False and self.is_right == False and (0 <msg.ranges[290] < 0.5):
			self.is_tunnel = True
			speed = 0 
			angular = 0
			self.move(speed,angular)
			os.system('roslaunch foscar_turtlebot3_autorace tunnel.launch')
			os.system('rosnode kill /detect_signs')
			os.system('rosnode kill /line_trace')

	def myhook(self):               # If Ctrl + c occured, the node ends by myhook function and turtlebot's velocity returns to 0.
		twist = Twist()
		twist.linear.x=0
		twist.angular.z=0
		self.pub_cmd_vel.publish(twist)			
		
	def move_turtlebot(self,img_data): ### left : -  ### right : +
		rospy.on_shutdown(self.myhook)
		# print('move_turtlebot')
		try:
			cv_image = self.bridge.compressed_imgmsg_to_cv2(img_data, "bgr8")
		except CvBridgeError as e:
			#print(e)
			pass
		self.line_trace(cv_image)
		
		if self.is_parking:																	##########		praking		###########
			if self.parking_phase == 0:#'''파킹 사인 보자마자 전부 노란 라인만 땀, 양쪽이 다 노란색 라인일때 1단계로 넘어감#'''
				# print(self.is_left, self.is_right)

				if self.is_left == True and self.is_right == False:
					self.center = self.left_pos + 273#'''300 이라고 한거 전부 273으로 바꿔줌 파킹 말고 다른곳도!!!!!!!!!!!!!!!!!!!!! 하하하하 하하하하 하하하하 하하하하 하하하하 하하하하'''
				elif self.is_left == False:# and self.is_right == False:
					self.center = 210
				elif self.is_right == True and self.is_right == True:
					self.parking_phase += 1
				else:
					pass
			
				error = self.center - 327

				Kp = 0.012
				Kd = 0.004

				angular_z = Kp * error + Kd * (error - self.lastError)
				self.lastError = error
				speed = min(self.MAX_VEL * ((1 - abs(error) / 320) ** 2.2), 0.2)
				angular = -max(angular_z, -2.0) if angular_z < 0 else -min(angular_z, 2.0)

			elif self.parking_phase == 1:#'''1단계는 양쪽 라인 다 잇는경우임'''
				if self.is_left == True and self.is_right == True:
					self.center = (self.left_pos + self.right_pos) // 2

				elif self.is_left == True and self.is_right == False:
					self.center = self.left_pos + 287

				elif self.is_left == False and self.is_right == True:
					self.center = self.right_pos - 289
				elif self.is_left == False and self.is_right == False:#'''양쪽라인 다 노랑색이 아닌경우 직진함#'''
					self.center = 327
				else:
					pass
				
				error = self.center - 327

				Kp = 0.012
				Kd = 0.004

				angular_z = Kp * error + Kd * (error - self.lastError)
				self.lastError = error
				speed = min(self.MAX_VEL * ((1 - abs(error) / 320) ** 2.2), 0.2)
				angular = -max(angular_z, -2.0) if angular_z < 0 else -min(angular_z, 2.0)

				if self.is_left_turtlebot == True:#'''1단계에서 터틀봇이 왼쪽 혹은 오릉쪽에 잇으면 2단계로 넘어감#'''
					self.found_turtlebot = True
					self.parking_phase += 1
				elif self.is_right_turtlebot == True:
					self.parking_phase += 1
					self.found_turtlebot = True
			elif self.parking_phase == 2:#'''왼쪽에잇으면 오른쪽으로 회전, 오른쪽에 잇으면 왼쪽으로 회전// 뒤통수에 터틀봇이 잡힐때까지 회전#'''
				if self.is_left_turtlebot == True:
					speed = 0
					angular = math.radians(-45)
				else:
					speed = 0
					angular = math.radians(45)

			elif self.parking_phase == 3:#'''3초동안 직진#'''
				speed = 0.1
				angular = 0
				self.move(speed, angular)
				rospy.sleep(rospy.Duration(3))
				self.parking_phase += 1

			elif self.parking_phase == 4: #'''뒤 돈다#'''
				speed = 0
				if self.is_left_turtlebot == True:
					angular = math.radians(-90)
					self.move(speed, angular)
					rospy.sleep(rospy.Duration(2))#'''2초동안#'''
					self.parking_phase += 1

				else:
					angular = math.radians(90)
					self.move(speed, angular)
					rospy.sleep(rospy.Duration(2))
					self.parking_phase += 1

				speed = 0
				angular = 0
				self.move(speed, angular)
				rospy.sleep(rospy.Duration(0.1))#'''이거는 주차하고 속도가 0인 순간이 필요해서 넣은 슬립 함수#'''

			elif self.parking_phase == 5:#'''여기서 탈출 한다 2.8초동안 하드 코딩함#'''
				speed = 0.2
				if self.is_left_turtlebot == True:
					angular = math.radians(55)
				else:
					angular = math.radians(-55)
				self.move(speed, angular)
				rospy.sleep(rospy.Duration(2.8))
				self.parking_phase += 1

			elif self.parking_phase == 6 : #'''여기서부터 양쪽 다 노랑색인 구간////// 여기 알고리즘 수정해서 그냥 self.is_leftsign True로 만들어 주면 될듯 주석달때 보니까 알고리즘 여기 엉망이네#'''
				speed = 0.12
				angular = 0
				self.is_mode = False
				self.is_parking = False			

			# print self.parking_phase
			self.move(speed, angular)#'''모든 스피트와 각도는 여기서 퍼블리싱함'''

		elif self.is_obstacle:
			return

		elif self.is_tunnel:
			return
			print 'tunneltunneltunneltunneltunneltunneltunneltunneltunneltunneltunnel'
			if self.is_left == True and self.is_right == True:
				self.is_tunnel = False
			else:
				return
			


		else:	 																					#############  line trace   ##############
			# print'line tracing'
			# print 'left line : ',self.is_left
			print 'right line : ',self.is_right
			#print self.is_left, self.is_right
			# center = self.center
			if self.is_stop and self.stopchk ==  False:																	###########		stop bar	############
				angular = 0
				speed = 0
				self.move(speed, angular)
				rospy.sleep(rospy.Duration(4.5))
				self.move(0,0)
				rospy.sleep(rospy.Duration(1.5))
				self.is_left = True
				self.is_right = True
				self.is_stop = False
				self.is_stopsign = False
				self.stopchk = True
				self.angular = 0
			elif self.is_left == False and self.is_right == False:
				angular = self.angular
				speed = 0.12
			else :
				if self.is_left == True and self.is_right == True:
					self.center = (self.left_pos + self.right_pos) // 2

				elif self.is_left == True and self.is_right == False:
					if self.is_rightsign:
						self.center = 420
					else:
						self.center = self.left_pos + 287 #40

				elif self.is_left == False and self.is_right == True:
					if self.is_leftsign:
						self.center = 200
					else:
						print 'elseeeeeeeeeeee'
						self.center = self.right_pos - 289 #616
				else:
					pass
				
				error = self.center - 327

				Kp = 0.016#0.0050 #0.0025
				Kd = 0.006#0.0018#0.014 #0.007

				angular_z = Kp * error + Kd * (error - self.lastError)
				print 'angular_z : ', angular_z
				print 'center : ',  self.center
				self.lastError = error
				speed = min(self.MAX_VEL * ((1 - abs(error) / 320) ** 2.2), 0.2)
				angular = -max(angular_z, -2.0) if angular_z < 0 else -min(angular_z, 2.0)
				
			angular = round(angular, 3)
			speed = round(speed, 3)
			self.move(speed, angular)
			# print speed,angular , self.center
		#self.rate.sleep()
		self.is_left = False
		self.is_right = False

	def line_trace(self, frame):
		##print('line_trace')
		frame = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
		ROI = frame[335:355, :]
		self.get_line(ROI)
		cv2.circle(frame, (int(self.center),355), 5,(0,0,255),3,-1)
		cv2.circle(frame, (int(self.right_pos),355), 5,(255,0,0),3,-1)
		cv2.circle(frame, (int(self.left_pos),355), 5,(0,255,0),3,-1)
		cv2.imshow('aa', frame)
		
		self.out2.write(frame)
		cv2.waitKey(1)


	def get_line(self, frame):
		hsl = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
		if self.is_parking_sign:
			yellow_binary = cv2.inRange(hsl, self.HSL_YELLOW_LOWER2, self.HSL_YELLOW_UPPER2)
			white_binary = cv2.inRange(hsl, self.HSL_YELLOW_LOWER2, self.HSL_YELLOW_UPPER2)	
		else:
			yellow_binary = cv2.inRange(hsl, self.HSL_YELLOW_LOWER, self.HSL_YELLOW_UPPER)
			white_binary = cv2.inRange(hsl, self.HSL_WHITE_LOWER, self.HSL_WHITE_UPPER)
		concat_binary = cv2.hconcat([yellow_binary, white_binary])
		cv2.imshow('concat_binary', concat_binary)
		gray_img = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		gaussianB = cv2.GaussianBlur(gray_img, (5,5), 0)
		canny = cv2.Canny(gaussianB, 50 , 150)
		cv2.imshow('ca', canny)
		lines = cv2.HoughLinesP(canny,1,np.pi/180,10,5,10)

		if lines is not None:
			lines = [l[0] for l in lines]
			left_arr = []
			right_arr = []
			for x1,y1,x2,y2 in lines:
				if x1 < 320 and self.is_left == False:
					
					# print x1,y1,x2,y2
					# print 'left degree' , degree
					if x1-20 < 0 :
						x = 0
					else :
						x = x1-20
					detect_area = yellow_binary[5 : 15, x : x1]
					# cv2.line(yellow_binary, (5,0), (5,x1),(255,0,0),2)
					nonzero = cv2.countNonZero(detect_area)
					# cv2.imshow('yb', yellow_binary)
					# cv2.imshow('de', detect_area)
					if nonzero > 30 :
						# print nonzero
						# self.left_pos = x1
						left_arr.append(x1)
			

				elif x2 > 320 and self.is_right == False:
					
					# print x1,y1,x2,y2
					# #print 'right degree', degree
					detect_area = white_binary[5 : 15, x2: x2+20]
					nonzero = cv2.countNonZero(detect_area)
					# print 'r_x2', x2, nonzero
					if nonzero > 30:
						# self.right_pos = x1
						right_arr.append(x2)
					
				else:
					continue
				
			# print self.left_pos, self.right_pos
			if len(left_arr) > 0 :
				self.is_left = True
				self.left_pos = left_arr[0]
				# if len(left_arr) > 1:
				# 	self.left_pos = np.mean(left_arr[len(left_arr)//5 : (4 * len(left_arr)//5)])

			if len(right_arr) > 0 :
				# print 'bbbbbbbbbbbbbbbbbb'
				self.is_right = True
				self.right_pos = right_arr[0]
				# if len(right_arr) > 1:
				# 	self.right_pos = np.mean(right_arr[len(right_arr)//5 : (4 * len(right_arr)//5)])


	
	def move(self, speed, angle):
		angular_z = angle
		twist = Twist()
		twist.linear.x = speed
		twist.angular.z= angular_z

		self.pub_cmd_vel.publish(twist)

		

	
	def main(self):
		rospy.spin()

if __name__ == '__main__':
	rospy.init_node('line_trace')#, anonymous=True)
	node = line_traceee()
	node.main()



