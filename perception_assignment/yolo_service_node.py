#!/usr/bin/env python3
"""
Single-image on-demand YOLO detection service.
"""

import os
import time

import cv2
import rclpy

from rcl_interfaces.msg import ParameterDescriptor
from rclpy.node import Node
from std_srvs.srv import Trigger
from ultralytics import YOLO
from vision_msgs.msg import (
    Detection2D,
    Detection2DArray,
    ObjectHypothesisWithPose,
)


class YoloServiceNode(Node):
    def __init__(self):
        super().__init__('yolo_service_node')

        # ROS parameters
        self.declare_parameter(
            'model_path',
            'models/yolov8n.pt'
        )

        self.declare_parameter(
            'image_path',
            'data/image_1.jpg'
        )

        self.declare_parameter(
            'target_classes',
            [],
            ParameterDescriptor(dynamic_typing=True)
        )

        self.declare_parameter(
            'conf_thres',
            0.5
        )

        self.target_classes = list(
            self.get_parameter('target_classes').value or []
        )

        self.conf_thres = float(
            self.get_parameter('conf_thres').value
        )

        self.model_path = str(
            self.get_parameter('model_path').value
        )

        # Load YOLO once when the node starts.
        self.model = None
        self.get_logger().info('Loading YOLO model...')

        try:
            self.model = YOLO(self.model_path)

            self.get_logger().info(
                f'YOLO model loaded from {self.model_path}'
            )

        except Exception as error:
            self.get_logger().error(
                f'Failed to load YOLO model from '
                f'{self.model_path}: {error}'
            )

        # Detection publisher
        self.pub_detections = self.create_publisher(
            Detection2DArray,
            '/yolo/detections',
            10
        )

        # Trigger service
        self.srv_trigger = self.create_service(
            Trigger,
            '/yolo_detector/trigger_inference',
            self.trigger_callback
        )

        self.get_logger().info(
            'YoloServiceNode is ready! '
            'Waiting for trigger service calls...'
        )

    def trigger_callback(self, request, response):
        image_path = str(
            self.get_parameter('image_path').value
        )

        self.get_logger().info(
            f'Trigger requested! Processing image: {image_path}'
        )

        if not os.path.exists(image_path):
            response.success = False
            response.message = (
                f'Image not found at {image_path}'
            )
            return response

        cv_img = cv2.imread(image_path)

        if cv_img is None:
            response.success = False
            response.message = (
                f'Failed to read image at {image_path}'
            )
            return response

        if self.model is None:
            response.success = False
            response.message = (
                "YOLO model is not loaded. "
                "Check the 'model_path' parameter."
            )
            return response

        # Run YOLO inference.
        try:
            start_time = time.perf_counter()

            results = self.model.predict(
                source=cv_img,
                conf=self.conf_thres,
                verbose=False
            )

            latency_ms = (
                time.perf_counter() - start_time
            ) * 1000.0

        except Exception as error:
            response.success = False
            response.message = (
                f'YOLO inference failed: {error}'
            )

            self.get_logger().error(response.message)
            return response

        detection_array = Detection2DArray()
        detection_array.header.stamp = (
            self.get_clock().now().to_msg()
        )
        detection_array.header.frame_id = 'camera'

        boxes = (
            results[0].boxes
            if results and results[0].boxes is not None
            else []
        )

        allowed_classes = {
            str(name).lower()
            for name in self.target_classes
        }

        for box in boxes:
            class_number = int(box.cls[0].item())
            confidence = float(box.conf[0].item())

            class_name = str(
                self.model.names[class_number]
            )

            if confidence < self.conf_thres:
                continue

            if (
                allowed_classes
                and class_name.lower() not in allowed_classes
            ):
                continue

            x1, y1, x2, y2 = box.xyxy[0].tolist()

            center_x = (x1 + x2) / 2.0
            center_y = (y1 + y2) / 2.0
            width = x2 - x1
            height = y2 - y1

            detection = Detection2D()
            detection.header = detection_array.header

            if hasattr(detection.bbox.center, 'position'):
                detection.bbox.center.position.x = float(
                    center_x
                )
                detection.bbox.center.position.y = float(
                    center_y
                )
            else:
                detection.bbox.center.x = float(center_x)
                detection.bbox.center.y = float(center_y)

            detection.bbox.center.theta = 0.0
            detection.bbox.size_x = float(width)
            detection.bbox.size_y = float(height)

            hypothesis = ObjectHypothesisWithPose()
            hypothesis.hypothesis.class_id = class_name
            hypothesis.hypothesis.score = confidence

            detection.results.append(hypothesis)
            detection_array.detections.append(detection)

        self.pub_detections.publish(detection_array)

        detection_count = len(
            detection_array.detections
        )

        self.get_logger().info(
            f'Published {detection_count} detections '
            f'in {latency_ms:.2f} ms'
        )

        response.success = True
        response.message = (
            f'Detected {detection_count} objects '
            f'in {latency_ms:.2f} ms'
        )

        return response


def main(args=None):
    rclpy.init(args=args)
    node = YoloServiceNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()