import tensorflow as tf
import tensorflow_transform as tft
import os
import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.cluster import KMeans
from tfx.components.trainer.fn_args_utils import FnArgs

def _parse_tf_examples(file_patterns, tf_transform_output, limit=None):
    """
    Parses TFRecords containing the EXACT output of your preprocessing_fn.
    Expected Schema:
      - 'features': FloatList (The concatenated z-scores + one-hots)
      - 'label': Int64List
    """
    feature_spec = tf_transform_output.transformed_feature_spec()
    
    def parse_proto(proto):
        parsed = tf.io.parse_single_example(proto, feature_spec)
        dense = {}
        for key, tensor in parsed.items():
            if isinstance(tensor, tf.SparseTensor):
                dense[key] = tf.sparse.to_dense(tensor)
            else:
                dense[key] = tensor
        return dense
    
    # Expand the file patterns (globs) into actual file paths
    expanded_files = []
    for pattern in file_patterns:
        expanded_files.extend(tf.io.gfile.glob(pattern))
        
    dataset = tf.data.TFRecordDataset(expanded_files, compression_type="GZIP")
    dataset = dataset.map(parse_proto)
    if limit is not None:
        dataset = dataset.take(limit)
    
    X_list = []
    y_list = []
    
    for ex in dataset:
        features_tensor = tf.reshape(ex['features'], [-1])
        label_tensor = tf.reshape(ex['label'], [])
        X_list.append(features_tensor.numpy()) 
        y_list.append(label_tensor.numpy().item()) # Label is usually a scalar
        
    return np.stack(X_list), np.array(y_list)

def run_fn(fn_args: FnArgs):
    tf_transform_output = tft.TFTransformOutput(fn_args.transform_output)
    
    print("Reading Transformed Data...")
    X_train, y_train = _parse_tf_examples(fn_args.train_files, tf_transform_output)
    
    print(f"Data Loaded. X shape: {X_train.shape}, y shape: {y_train.shape}")
    
    pipe = Pipeline([
        ('kmeans', KMeans(n_clusters=2, random_state=42))
    ])
    
    pipe.fit(X_train)
    
    # Save locally first to avoid GFile/joblib compatibility issues
    local_path = "/tmp/model.joblib"
    joblib.dump(pipe, local_path)

    tf.io.gfile.makedirs(fn_args.serving_model_dir)
    model_path = os.path.join(fn_args.serving_model_dir, 'model.joblib')
    tf.io.gfile.copy(local_path, model_path, overwrite=True)
    os.remove(local_path)
    print(f"Model saved to {model_path}")