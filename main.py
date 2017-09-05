import os.path
import tensorflow as tf
import helper
import warnings
from distutils.version import LooseVersion
import project_tests as tests
import time

# Check TensorFlow Version
assert LooseVersion(tf.__version__) >= LooseVersion('1.0'), 'Please use TensorFlow version 1.0 or newer.  You are using {}'.format(tf.__version__)
print('TensorFlow Version: {}'.format(tf.__version__))

# Check for a GPU
if not tf.test.gpu_device_name():
    warnings.warn('No GPU found. Please use a GPU to train your neural network.')
else:
    print('Default GPU Device: {}'.format(tf.test.gpu_device_name()))


def load_vgg(sess, vgg_path):
    """
    Load Pretrained VGG Model into TensorFlow.
    :param sess: TensorFlow Session
    :param vgg_path: Path to vgg folder, containing "variables/" and "saved_model.pb"
    :return: Tuple of Tensors from VGG model (image_input, keep_prob, layer3_out, layer4_out, layer7_out)
    """
    # Saved VGG16 graph layer names
    vgg_tag = 'vgg16'
    vgg_input_tensor_name = 'image_input:0'
    vgg_keep_prob_tensor_name = 'keep_prob:0'
    vgg_layer3_out_tensor_name = 'layer3_out:0'
    vgg_layer4_out_tensor_name = 'layer4_out:0'
    vgg_layer7_out_tensor_name = 'layer7_out:0'

    # Load saved graph
    tf.saved_model.loader.load(sess, [vgg_tag], vgg_path)
    graph = tf.get_default_graph()

    # Extract specific layers by name
    image_input = graph.get_tensor_by_name(vgg_input_tensor_name)
    keep_prob = graph.get_tensor_by_name(vgg_keep_prob_tensor_name)
    layer3_out = graph.get_tensor_by_name(vgg_layer3_out_tensor_name)
    layer4_out = graph.get_tensor_by_name(vgg_layer4_out_tensor_name)
    layer7_out = graph.get_tensor_by_name(vgg_layer7_out_tensor_name)

    return image_input, keep_prob, layer3_out, layer4_out, layer7_out
tests.test_load_vgg(load_vgg, tf)


def layers(vgg_layer3_out, vgg_layer4_out, vgg_layer7_out, num_classes):
    """
    Create the layers for a fully convolutional network.  Build skip-layers using the vgg layers.
    :param vgg_layer7_out: TF Tensor for VGG Layer 3 output
    :param vgg_layer4_out: TF Tensor for VGG Layer 4 output
    :param vgg_layer3_out: TF Tensor for VGG Layer 7 output
    :param num_classes: Number of classes to classify
    :return: The Tensor for the last layer of output
    """
    # Layer regularizer
    l2_reg = tf.contrib.layers.l2_regularizer(1e-3)
    # l2_reg = None

    # 1x1 Convolution after last VGG layer to reshape depth
    flow = tf.layers.conv2d(vgg_layer7_out, num_classes, 1, strides=1,
                            padding='same',
                            kernel_regularizer=l2_reg)

    # First transpose convolution
    flow = tf.layers.conv2d_transpose(flow, num_classes, 4, strides=2,
                                      padding='same',
                                      kernel_regularizer=l2_reg)

    # Reshape depth with 1x1 convolution before skip connection
    layer4_1x1 = tf.layers.conv2d(vgg_layer4_out, num_classes, 1, strides=1,
                                  padding='same',
                                  kernel_regularizer=l2_reg)

    # Skip connection to layer 4
    flow = tf.add(flow, layer4_1x1)


    # Second transpose convolution
    flow = tf.layers.conv2d_transpose(flow, num_classes, 4, strides=2,
                                      padding='same',
                                      kernel_regularizer=l2_reg)

    # Reshape depth with 1x1 convolution before skip connection
    layer3_1x1 = tf.layers.conv2d(vgg_layer3_out, num_classes, 1, strides=1,
                                  padding='same',
                                  kernel_regularizer=l2_reg)

    # Skip connection to layer 3
    flow = tf.add(flow, layer3_1x1)

    # Final upsample, typical fcn8 output
    fcn8 = tf.layers.conv2d_transpose(flow, num_classes, 16, strides=8,
                                      padding='same',
                                      kernel_regularizer=l2_reg)

    # Add a few convolutional layers to help fill in and remove the noise
    flow = tf.layers.conv2d(fcn8, 2*num_classes, 3, 1,
                            padding='same',
                            activation=tf.nn.elu,
                            # activation=tf.nn.tanh,
                            kernel_regularizer=l2_reg)

    flow = tf.layers.conv2d(flow, num_classes, 5, 1,
                            padding='same',
                            activation=tf.nn.elu,
                            # activation=tf.nn.tanh,
                            kernel_regularizer=l2_reg)

    # Skip connector to the fcn8 output
    flow = tf.add(fcn8, flow)

    flow = tf.layers.conv2d(flow, num_classes, 7, strides=1,
                            padding='same',
                            activation=tf.nn.elu,
                            # activation=tf.nn.tanh,
                            kernel_regularizer=l2_reg)

    return flow
tests.test_layers(layers)


def optimize(nn_last_layer, correct_label, learning_rate, num_classes):
    """
    Build the TensorFLow loss and optimizer operations.
    :param nn_last_layer: TF Tensor of the last layer in the neural network
    :param correct_label: TF Placeholder for the correct label image
    :param learning_rate: TF Placeholder for the learning rate
    :param num_classes: Number of classes to classify
    :return: Tuple of (logits, train_op, cross_entropy_loss)
    """

    # Reshape correct label
    correct_label = tf.reshape(correct_label, (-1, num_classes))

    # Flatten final layer
    logits = tf.reshape(nn_last_layer, (-1, num_classes))

    # Loss Function
    cross_entropy_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=logits, labels=correct_label))

    # Optimization Function
    train_op = tf.train.AdamOptimizer(learning_rate).minimize(cross_entropy_loss)

    return logits, train_op, cross_entropy_loss
tests.test_optimize(optimize)


def train_nn(sess, epochs, batch_size, get_batches_fn, train_op, cross_entropy_loss, input_image,
             correct_label, keep_prob, learning_rate):
    """
    Train neural network and print out the loss during training.
    :param sess: TF Session
    :param epochs: Number of epochs
    :param batch_size: Batch size
    :param get_batches_fn: Function to get batches of training data.  Call using get_batches_fn(batch_size)
    :param train_op: TF Operation to train the neural network
    :param cross_entropy_loss: TF Tensor for the amount of loss
    :param input_image: TF Placeholder for input images
    :param correct_label: TF Placeholder for label images
    :param keep_prob: TF Placeholder for dropout keep probability
    :param learning_rate: TF Placeholder for learning rate
    """

    # Start a timer
    batch_start = time.time()
    for epoch in range(epochs):
        for batch, (image, label) in enumerate(get_batches_fn(batch_size)):
            feed_dict = {input_image: image,
                         correct_label: label,
                         keep_prob: 1.0,
                         learning_rate: 0.0001}
            _, loss = sess.run([train_op, cross_entropy_loss], feed_dict=feed_dict)
            print("Epoch: {:<3} Batch: {:<5} Loss: {:<10.4f} Running Time: {:<.1f} seconds".format(epoch+1,
                                                                                                  batch+1,
                                                                                                  loss,
                                                                                                  time.time()-batch_start))
    pass
tests.test_train_nn(train_nn)


def run():
    num_classes = 2
    image_shape = (160, 576)
    data_dir = './data'
    runs_dir = './runs'
    tests.test_for_kitti_dataset(data_dir)

    # Download pretrained vgg model
    helper.maybe_download_pretrained_vgg(data_dir)

    # OPTIONAL: Train and Inference on the cityscapes dataset instead of the Kitti dataset.
    # You'll need a GPU with at least 10 teraFLOPS to train on.
    #  https://www.cityscapes-dataset.com/

    with tf.Session() as sess:
        # Hyperparameters
        epochs = 21
        batch_size = 40
        learning_rate = tf.placeholder(tf.float32)
        correct_label = tf.placeholder(tf.int32, [None, None, None, num_classes])

        # Path to vgg model
        vgg_path = os.path.join(data_dir, 'vgg')
        # Create function to get batches
        get_batches_fn = helper.gen_batch_function(os.path.join(data_dir, 'data_road/training'), image_shape)

        # OPTIONAL: Augment Images for better results
        # https://datascience.stackexchange.com/questions/5224/how-to-prepare-augment-images-for-neural-network

        # Build NN using load_vgg, layers, and optimize function
        input_image, keep_prob, layer3_out, layer4_out, layer7_out = load_vgg(sess, vgg_path)
        layer_output = layers(layer3_out, layer4_out, layer7_out, num_classes)
        logits, train_op, cross_entropy_loss = optimize(layer_output, correct_label, learning_rate, num_classes)

        # Initialize
        sess.run(tf.local_variables_initializer())
        sess.run(tf.global_variables_initializer())

        # Train NN using the train_nn function
        train_nn(sess,
                 epochs,
                 batch_size,
                 get_batches_fn,
                 train_op,
                 cross_entropy_loss,
                 input_image,
                 correct_label,
                 keep_prob,
                 learning_rate)

        # Save inference data using helper.save_inference_samples
        helper.save_inference_samples(runs_dir, data_dir, sess, image_shape, logits, keep_prob, input_image)

        # OPTIONAL: Apply the trained model to a video


if __name__ == '__main__':
    run()
