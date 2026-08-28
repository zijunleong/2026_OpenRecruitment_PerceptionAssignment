#!/usr/bin/env python3

import cv2
import rclpy

from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray


class YoloVisualizerNode(Node):
    def __init__(self):
        super().__init__('yolo_visualizer_node')

        self.bridge = CvBridge()
        self.latest_image = None
        self.latest_detections = None

        self.create_subscription(
            Image,
            '/data',
            self.image_callback,
            10
        )

        self.create_subscription(
            Detection2DArray,
            '/yolo/detections',
            self.detection_callback,
            10
        )

        self.pub_annotated = self.create_publisher(
            Image,
            '/yolo/annotated_image',
            10
        )

        self.get_logger().info(
            'YOLO Visualizer Node started. '
            'Subscribed to /data and /yolo/detections'
        )

    def image_callback(self, msg):
        self.latest_image = msg

        # After inference, publish the annotated image at 5 Hz.
        if self.latest_detections is not None:
            self.publish_annotated_image()

    def detection_callback(self, msg):
        self.latest_detections = msg

        if self.latest_image is None:
            self.get_logger().warning(
                'Detection received before the first image.'
            )
            return

        self.publish_annotated_image()

    def publish_annotated_image(self):
        if (
            self.latest_image is None
            or self.latest_detections is None
        ):
            return

        try:
            cv_img = self.bridge.imgmsg_to_cv2(
                self.latest_image,
                desired_encoding='bgr8'
            ).copy()

        except Exception as error:
            self.get_logger().error(
                f'Failed to convert image: {error}'
            )
            return

        for detection in self.latest_detections.detections:

            if hasattr(detection.bbox.center, 'position'):
                center_x = int(
                    detection.bbox.center.position.x
                )
                center_y = int(
                    detection.bbox.center.position.y
                )
            else:
                center_x = int(detection.bbox.center.x)
                center_y = int(detection.bbox.center.y)

            width = int(detection.bbox.size_x)
            height = int(detection.bbox.size_y)

            x1 = int(center_x - width / 2)
            y1 = int(center_y - height / 2)
            x2 = int(center_x + width / 2)
            y2 = int(center_y + height / 2)

            label = 'Object'

            if detection.results:
                hypothesis = detection.results[0].hypothesis
                label = (
                    f'{hypothesis.class_id} '
                    f'({hypothesis.score:.2f})'
                )

            cv2.rectangle(
                cv_img,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )

            cv2.putText(
                cv_img,
                label,
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )

        try:
            annotated_msg = self.bridge.cv2_to_imgmsg(
                cv_img,
                encoding='bgr8'
            )

            annotated_msg.header = self.latest_image.header
            self.pub_annotated.publish(annotated_msg)

        except Exception as error:
            self.get_logger().error(
                f'Failed to publish image: {error}'
            )


def main(args=None):
    rclpy.init(args=args)
    node = YoloVisualizerNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()