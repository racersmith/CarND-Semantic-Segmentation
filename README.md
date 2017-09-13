# Semantic Segmentation
### Introduction
In this project, the road is identified at the pixel level using a Fully Convolutional Network, FCN.
The FCN used here is a modification of the FCN8 which takes the venerable VGG16 and replaces the fully connected layers
with a 1x1 convolution. The final fully connected layers are replaced with a single 1x1 convolution.
This represents the encoder portion of the network and is the driving force behind the classification.
However, the spatial information is lost during the size reduction of the convolutions and max pooling layers.
The spatial information of the classification is gained through transpose convolutions and skip connectors to earlier
layers of VGG16 to gain back spatial information of the classification.  To improve noise and generate a more distinct
boundary, two additional convolution layers were added.

### Setup
##### Frameworks and Packages
Make sure you have the following is installed:
 - [Python 3](https://www.python.org/)
 - [TensorFlow](https://www.tensorflow.org/)
 - [NumPy](http://www.numpy.org/)
 - [SciPy](https://www.scipy.org/)
##### Dataset
Download the [Kitti Road dataset](http://www.cvlibs.net/datasets/kitti/eval_road.php) from
[here](http://www.cvlibs.net/download.php?file=data_road.zip).  Extract the dataset in the `data` folder.
This will create the folder `data_road` with all the training a test images.