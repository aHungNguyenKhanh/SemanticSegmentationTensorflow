from __future__ import division

import tensorflow as tf
import numpy as np
from abc import ABCMeta, abstractmethod



def data_augment(batch, methods):
    for method in methods:
        batch = method(batch)
    return batch


class Batch:


    def __init__(self, x , y):
        assert np.size(x, 0) == np.size(y, 0)
        self.x = x
        self.y = y
        self.size = np.size(x, 0)



class DataSet:

    __metaclass__ = ABCMeta

    def __init__(self, batch_size):
        self._current_index = 0
        self._batch_size = batch_size
        self.size = 0

    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def batch(self):
        pass

    @abstractmethod
    def shuffle(self):
        pass

    def reset(self):
        self._current_index = 0


# Data set structure
class LoadTimeDataSet(DataSet):

    __metaclass__ = ABCMeta


    def __init__(self, batch_size):
        super(LoadTimeDataSet, self).__init__(batch_size)
        self.images = []
        self.labels = []


    # load data contain images and labels
    @abstractmethod
    def load(self):
        pass


    def shuffle(self):
        dataset = zip(self.images, self.labels)
        np.random.shuffle(dataset)
        self.images, self.labels = zip(*dataset)


    def batch(self):

        if self._current_index >= self.size:
            return

        index_end = self._current_index + self._batch_size
        if index_end >= self.size:
            index_end = self.size
            batch = Batch(self.images[self._current_index : index_end], self.labels[self._current_index : index_end])
            return batch
        else:
            batch = Batch(self.images[self._current_index: index_end], self.labels[self._current_index : index_end])
            self._current_index = index_end
            return batch



class RunTimeDataSet(DataSet):

    __metaclass__ = ABCMeta

    def __init__(self, batch_size):
        super(RunTimeDataSet, self).__init__(batch_size)
        self._index_list = []

    @abstractmethod
    def load(self):
        pass

    def shuffle(self):
        np.random.shuffle(self._index_list)

    @abstractmethod
    def batch(self):
        pass



class TensorflowDataset:

    def __init__(self, path, batch_size, image_shape, truth_shape, epoch_size , numthread = 1):
        self.path = path
        self.__image_shape = image_shape
        self.__batch_size = batch_size
        self.__truth_shape = truth_shape
        self.__steps_per_epoch = epoch_size // batch_size + int(epoch_size % batch_size > 0)
        self.__index = 0
        self.size = epoch_size


        filename_queue = tf.train.string_input_producer([self.path])
        self.__batch = self.__read_and_decode(filename_queue, numthread)


    def __read_and_decode(self, filename_queue, numthread):
        reader = tf.TFRecordReader()

        _, serialized_example = reader.read(filename_queue)

        features = tf.parse_single_example(
            serialized_example,
            # Defaults are not specified since both keys are required.
            features={
                'height': tf.FixedLenFeature([], tf.int64),
                'width': tf.FixedLenFeature([], tf.int64),
                'image_raw': tf.FixedLenFeature([], tf.string),
                'mask_raw': tf.FixedLenFeature([], tf.string)
            })


        image = tf.decode_raw(features['image_raw'], tf.uint8)
        annotation = tf.decode_raw(features['mask_raw'], tf.uint8)

        image_shape = tf.stack(self.__image_shape)
        annotation_shape = tf.stack(self.__truth_shape)

        image = tf.reshape(image, image_shape)
        annotation = tf.reshape(annotation, annotation_shape)


        images, annotations = tf.train.shuffle_batch([image, annotation], batch_size=self.__batch_size, allow_smaller_final_batch=True, capacity=125, num_threads=numthread, min_after_dequeue=100)

        return images, annotations



    def batch(self, sess):
        assert sess._closed == False
        imgs, truths =sess.run(self.__batch)
        self.__index += 1

        if self.__index >= self.__steps_per_epoch:
            self.__index = 0
            return Batch(imgs, truths), True

        else:
            return Batch(imgs, truths), False


    def shuffle(self):
        pass



class NewTFDataset:


    def __init__(self, path, batch_size, image_shape, truth_shape, epoch_size, sess):
        assert sess._closed == False
        self.path = path
        self.__image_shape = image_shape
        self.__batch_size = batch_size
        self.__truth_shape = truth_shape
        self.__steps_per_epoch = epoch_size // batch_size + int(epoch_size % batch_size > 0)
        self.__step = 0
        self.__size = epoch_size

        self.__dataset = tf.data.TFRecordDataset([path])
        # filename_queue = tf.train.string_input_producer([self.path], num_epochs=1)

        self.__dataset = self.__dataset.map(self.__read_and_decode, num_parallel_calls=epoch_size)
        self.__dataset = self.__dataset.shuffle(buffer_size=self.__batch_size * 3 + self.__size // 4)
        data = self.__dataset.batch(self.__batch_size)
        self.__iterator = data.make_initializable_iterator()
        sess.run(self.__iterator.initializer)
        # sess.run(self.__iterator.make_initializer(self.__dataset))



    def __read_and_decode(self, example_proto):
        # reader = tf.TFRecordReader()

        # _, serialized_example = reader.read(filename_queue)

        features = tf.parse_single_example(
            example_proto,
            # Defaults are not specified since both keys are required.
            features={
                'height': tf.FixedLenFeature([], tf.int64),
                'width': tf.FixedLenFeature([], tf.int64),
                'image_raw': tf.FixedLenFeature([], tf.string),
                'mask_raw': tf.FixedLenFeature([], tf.string)
            })


        image = tf.decode_raw(features['image_raw'], tf.uint8)
        annotation = tf.decode_raw(features['mask_raw'], tf.uint8)

        image_shape = tf.stack(self.__image_shape)
        annotation_shape = tf.stack(self.__truth_shape)

        images = tf.reshape(image, image_shape)
        annotations = tf.reshape(annotation, annotation_shape)


        # images, annotations = tf.train.shuffle_batch([image, annotation], batch_size=self.__batch_size, allow_smaller_final_batch=True, capacity=125, num_threads=numthread, min_after_dequeue=100)

        return images, annotations



    def batch(self, sess):
        assert sess._closed == False
        try:
            self.__step += 1
            x, y = sess.run(self.__iterator.get_next())
            return Batch(x, y)

        except tf.errors.OutOfRangeError:
            self.__step = 0
            return None


    @property
    def step(self):
        return self.__step

    @property
    def size(self):
        return self.__size


    def reset(self, sess ):
        assert sess._closed == False
        sess.run(self.__iterator.initializer)






