
import tensorflow as tf
import tensorflow_transform as tft
def preprocessing_fn(inputs):
    num_cols = [key for key, value in inputs.items() if value.dtype in (tf.float32, tf.int64) and key not in ('outcome', 'labels')]
    cat_cols = [key for key, value in inputs.items() if value.dtype == tf.string and key not in ('outcome', 'labels')]

    # z-score normalization, like sklearn's StandardScaler
    #    To match MinMaxScaler, use tft.scale_to_0_1 instead.
    num_scaled = [tft.scale_to_z_score(tf.cast(inputs[k], tf.float32)) for k in num_cols]

    # One-hot encode, like sklearn's OneHotEncoder
    cat_onehot = []
    for k in cat_cols:
        idx = tft.compute_and_apply_vocabulary(inputs[k], num_oov_buckets=1, vocab_filename=k + "_vocab")
        depth = tft.experimental.get_vocabulary_size_by_name(k + "_vocab") + 1
        depth = tf.cast(depth, tf.int32)
        onehot = tf.one_hot(idx, depth=depth, dtype=tf.float32)
        cat_onehot.append(tf.reshape(onehot, [-1, tf.shape(onehot)[-1]]))

    features = tf.concat(num_scaled + cat_onehot, axis=-1)
    return {"features": features}
