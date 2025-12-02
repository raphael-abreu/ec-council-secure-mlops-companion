import joblib
import pandas as pd
import os
import tensorflow as tf
import numpy as np
from sklearn.metrics import accuracy_score
from tfx.dsl.component.experimental.decorators import component
from tfx.dsl.component.experimental.annotations import InputArtifact, OutputArtifact
from tfx.types import standard_artifacts
import tensorflow_transform as tft

@component
def SklearnEvaluator(
    model: InputArtifact[standard_artifacts.Model],
    transformed_examples: InputArtifact[standard_artifacts.Examples],
    transform_graph: InputArtifact[standard_artifacts.TransformGraph],
    blessing: OutputArtifact[standard_artifacts.ModelBlessing]
):

    # 1. Load Model
    model_gcs_path = os.path.join(model.uri, "Format-Serving", "model.joblib")
    if not tf.io.gfile.exists(model_gcs_path):
        raise FileNotFoundError(f"Expected model at {model_gcs_path}")

    local_model_path = "/tmp/model.joblib"
    tf.io.gfile.copy(model_gcs_path, local_model_path, overwrite=True)
    pipe = joblib.load(local_model_path)
    os.remove(local_model_path)
    print(f"[Evaluator] Loaded model from {model_gcs_path}")

    # 2. Load transform metadata to parse TFRecords safely
    tf_transform_output = tft.TFTransformOutput(transform_graph.uri)
    feature_spec = tf_transform_output.transformed_feature_spec()

    eval_dir = os.path.join(transformed_examples.uri, 'Split-eval')
    file_patterns = tf.io.gfile.glob(os.path.join(eval_dir, '*.gz'))
    print(f"[Evaluator] Eval files: {file_patterns}")
    def _dense_parse(serialized_proto):
        parsed = tf.io.parse_single_example(serialized_proto, feature_spec)
        dense = {}
        for key, tensor in parsed.items():
            if isinstance(tensor, tf.SparseTensor):
                dense[key] = tf.sparse.to_dense(tensor)
            else:
                dense[key] = tensor
        return dense

    dataset = tf.data.TFRecordDataset(file_patterns, compression_type="GZIP")
    dataset = dataset.map(_dense_parse)

    X_list, y_list = [], []
    for record in dataset:
        features_tensor = tf.reshape(record['features'], [-1])
        label_tensor = tf.reshape(record['label'], [])
        X_list.append(features_tensor.numpy())
        y_list.append(label_tensor.numpy().item())

    X_test = np.stack(X_list)
    y_test = np.array(y_list)
    print(f"[Evaluator] Eval set size: {X_test.shape[0]} rows, feature dim: {X_test.shape[1]}")

    clusters = pipe.named_steps['kmeans'].predict(X_test)

    counts = (
        pd.DataFrame({'cluster': clusters, 'label': y_test})
        .groupby(['cluster', 'label'])
        .size()
        .unstack(fill_value=0)
    )
    cluster_to_label = {cluster: counts.loc[cluster].idxmax() for cluster in counts.index}
    predicted_labels = pd.Series(clusters).map(cluster_to_label).values
    acc = accuracy_score(y_test, predicted_labels)
    metrics_pass = acc > 0.85
    marker = "BLESSED" if metrics_pass else "NOT_BLESSED"
    print(f"[Evaluator] Acc: {acc:.4f}, threshold: 0.85, status: {marker}")
    blessing_path = os.path.join(blessing.uri, marker)

    with tf.io.gfile.GFile(blessing_path, "w") as f:
        f.write(marker)

    blessing.set_int_custom_property('blessed', 1 if metrics_pass else 0)