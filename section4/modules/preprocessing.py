import tensorflow as tf
import tensorflow_transform as tft

def preprocessing_fn(inputs):
    """
    tf.transform preprocessing function.
    Taken exactly from section3.ipynb
    """
    # Identify columns by type (excluding label/outcome)
    num_cols = [key for key, value in inputs.items() 
                if value.dtype in (tf.float32, tf.int64) 
                and key not in ('outcome', 'labels', 'label')]

    cat_cols = [key for key, value in inputs.items() 
                if value.dtype == tf.string 
                and key not in ('outcome', 'labels', 'label')]

    # z-score normalization
    num_scaled = [tft.scale_to_z_score(tf.cast(inputs[k], tf.float32)) for k in num_cols]

    # One-hot encode
    cat_onehot = []
    for k in cat_cols:
        idx = tft.compute_and_apply_vocabulary(inputs[k], num_oov_buckets=1, vocab_filename=k + "_vocab")
        depth = tft.experimental.get_vocabulary_size_by_name(k + "_vocab") + 1
        depth = tf.cast(depth, tf.int32)
        onehot = tf.one_hot(idx, depth=depth, dtype=tf.float32)
        cat_onehot.append(tf.reshape(onehot, [-1, tf.shape(onehot)[-1]]))

    # Concatenate all features into a single dense vector
    features = tf.concat(num_scaled + cat_onehot, axis=-1)
    
    outputs = {"features": features}
    
    if "outcome" in inputs:
        # 1 if NOT 'normal.', 0 if 'normal.'
        is_attack = tf.not_equal(inputs["outcome"], "normal.")
        outputs["label"] = tf.cast(is_attack, tf.int64)
    elif "label" in inputs:
        outputs["label"] = tf.cast(inputs["label"], tf.int64)
    elif "labels" in inputs:
        outputs["label"] = tf.cast(inputs["labels"], tf.int64)
         
    return outputs