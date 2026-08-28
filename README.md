# On-Demand YOLO Perception Service

## Overview

This project implements an on-demand object-detection pipeline using ROS 2 and YOLOv8n. Unlike a continuous inference pipeline, the model runs only when the `/yolo_detector/trigger_inference` service is called.

For each trigger request, the node:

1. Reads one image from disk.
2. Runs YOLO inference.
3. Applies confidence and optional class filtering.
4. Converts the accepted results into `vision_msgs/msg/Detection2DArray`.
5. Publishes the detections to `/yolo/detections`.
6. Returns the detection count and inference latency to the service caller.

An additional visualizer overlays the published detections on the input image and displays the result in RViz.

## Language and Inference Engine

* Language: Python
* ROS client library: `rclpy`
* Inference engine: Ultralytics
* Model: YOLOv8n
* Development environment: ROS 2 Lyrical
* Inference device: CPU

Python was selected because Ultralytics provides a reliable Python interface for YOLO models and allows straightforward integration with ROS 2 messages and services.

YOLOv8n was selected because it is the smallest YOLOv8 model and provides a suitable balance between inference speed and object-detection performance for edge applications.

## ROS 2 Interfaces

| Interface              | Name                               | Type                               |
| ---------------------- | ---------------------------------- | ---------------------------------- |
| Main node              | `yolo_service_node`                | ROS 2 node                         |
| Image parameter        | `image_path`                       | String                             |
| Model parameter        | `model_path`                       | String                             |
| Confidence parameter   | `conf_thres`                       | Double                             |
| Class-filter parameter | `target_classes`                   | String array                       |
| Trigger service        | `/yolo_detector/trigger_inference` | `std_srvs/srv/Trigger`             |
| Detection output       | `/yolo/detections`                 | `vision_msgs/msg/Detection2DArray` |
| Input image topic      | `/data`                            | `sensor_msgs/msg/Image`            |
| Annotated image topic  | `/yolo/annotated_image`            | `sensor_msgs/msg/Image`            |

The `/data` topic and visualizer are used only for demonstration. YOLO inference is performed by reading the image specified by `image_path`.

## Detection and Filtering Logic

The YOLO output supplies:

* class index;
* confidence score;
* bounding-box corner coordinates.

Each bounding box is converted from YOLO corner coordinates `(x1, y1, x2, y2)` into the centre position, width, and height required by `vision_msgs/msg/Detection2D`.

Detections below `conf_thres` are removed. The default threshold is:

```text
0.5
```

The optional `target_classes` parameter can retain only selected YOLO classes. An empty class list accepts every detected class.

For example:

```bash
ros2 run perception_assignment yolo_service_node --ros-args \
  -p image_path:="/absolute/path/to/image.jpg" \
  -p target_classes:="['cup', 'bottle']" \
  -p conf_thres:=0.5
```

## Optimization Strategy

The following strategies were used:

1. The YOLO model is loaded once when the node starts instead of being loaded for every request.
2. Inference runs only when the Trigger service is called.
3. The lightweight YOLOv8n model is used.
4. Low-confidence detections are removed.
5. Optional class filtering avoids publishing unnecessary objects.
6. No continuous camera-inference loop is used.
7. Inference latency is measured using `time.perf_counter()` around the Ultralytics `model.predict()` call.

The image publisher runs at a low frequency only to support RViz visualization. It does not perform inference.

## Performance Results

Testing was performed on:

* CPU: Intel Core i9-14900HX
* CUDA available: No
* Inference device: CPU
* Model: YOLOv8n
* Confidence threshold: 0.5
* Measurements per image: 10
* Total measured calls: 50
* First model warm-up call: Excluded

| Test image    | Detected objects | Average latency |
| ------------- | ---------------: | --------------: |
| `image_1.jpg` |                6 |        36.33 ms |
| `image_2.jpg` |               15 |        32.68 ms |
| `image_3.jpg` |                7 |        37.74 ms |
| `image_4.jpg` |               10 |        34.77 ms |
| `image_5.jpg` |               10 |        35.34 ms |

The overall average inference latency across the 50 measured calls was:

```text
35.37 ms
```

The first call after loading the model took significantly longer because it included model warm-up. It was excluded from the average.

The reported latency measures the complete Ultralytics `model.predict()` call, including its preprocessing, model inference, and postprocessing. Reading the image from disk is not included.

## Detection Visualization

The following result shows the bounding boxes and class labels published by the ROS 2 detection pipeline.

![YOLO detection result in RViz](rviz_detection.png)

## Performance Test Results

![Inference latency results](performance_results.png)
## Error Handling

The service checks the following conditions before running inference:

* whether the image path exists;
* whether OpenCV can read the image;
* whether the YOLO model loaded successfully;
* whether an exception occurs during inference.

If an invalid image path is supplied, the node returns:

```text
success: false
message: "Image not found at ..."
```

The node therefore reports the failure without crashing.

## Dependencies

### ROS dependencies

* `rclpy`
* `rcl_interfaces`
* `sensor_msgs`
* `vision_msgs`
* `std_srvs`
* `cv_bridge`
* `ament_index_python`
* `rviz2`

### Python dependencies

* Ultralytics
* PyTorch
* OpenCV
* NumPy

## Installation

Source the ROS 2 environment:

```bash
source /opt/ros/$ROS_DISTRO/setup.bash
```

Install the required ROS packages:

```bash
sudo apt update

sudo apt install \
  ros-$ROS_DISTRO-vision-msgs \
  ros-$ROS_DISTRO-cv-bridge \
  ros-$ROS_DISTRO-rviz2 \
  python3-opencv
```

Create a Python virtual environment with access to the ROS system packages:

```bash
python3 -m venv --system-site-packages ~/team_robo_venv

source ~/team_robo_venv/bin/activate

python -m pip install --upgrade pip
python -m pip install ultralytics
```

## OpenCV and `cv_bridge` Compatibility

During development on ROS 2 Lyrical, the pip version of OpenCV conflicted with the ROS `cv_bridge` package and produced a `KeyError` during image conversion.

The compatible Ubuntu OpenCV package was used instead:

```bash
python -m pip uninstall -y \
  opencv-python \
  opencv-python-headless \
  opencv-contrib-python \
  opencv-contrib-python-headless

sudo apt install --reinstall \
  python3-opencv \
  ros-$ROS_DISTRO-cv-bridge
```

The virtual environment must be created using `--system-site-packages` so that it can access the ROS-compatible OpenCV installation.

## Build Instructions

Place the repository inside a ROS 2 workspace:

```bash
cd ~/ros2_ws
```

Source ROS and activate the Python environment:

```bash
source /opt/ros/$ROS_DISTRO/setup.bash
source ~/team_robo_venv/bin/activate
```

Build the package:

```bash
colcon build \
  --packages-select perception_assignment \
  --symlink-install
```

Source the completed workspace:

```bash
source ~/ros2_ws/install/setup.bash
```

## Running the Complete Demo

Go to the repository directory:

```bash
cd ~/ros2_ws/src/2026_OpenRecruitment_PerceptionAssignment
```

Launch the detector, image publisher, visualizer, and RViz:

```bash
ros2 launch perception_assignment demo.launch.py
```

To select another image:

```bash
ros2 launch perception_assignment demo.launch.py \
  image_path:="$PWD/data/image_2.jpg"
```

The RViz display remains empty until the first inference request is made.

In another sourced terminal, trigger inference:

```bash
ros2 service call /yolo_detector/trigger_inference \
  std_srvs/srv/Trigger "{}"
```

A successful response has the following form:

```text
success: true
message: "Detected 6 objects in 36.47 ms"
```

After the first trigger, the visualizer publishes the latest annotated image to `/yolo/annotated_image`.

## Running Without RViz

For a headless system:

```bash
ros2 launch perception_assignment demo.launch.py \
  rviz:=false
```

Detections can be inspected using:

```bash
ros2 topic echo /yolo/detections
```

## Design Notes

The detector remains strictly on-demand. The visualizer republishes the most recent annotated result when new `/data` image messages arrive, but this does not rerun YOLO.

The bounding-box implementation supports the `vision_msgs` centre-field formats used by different ROS 2 distributions.

## Limitations

* Testing was performed using CPU inference only.
* The provided YOLOv8n model is trained on the standard COCO classes.
* The service processes one disk image per trigger rather than a live camera stream.
* Detection accuracy depends on the provided model and confidence threshold.
