from tfx.dsl.component.experimental.decorators import component
from tfx.dsl.component.experimental.annotations import InputArtifact
from tfx.types import standard_artifacts

@component
def AnomalyGatekeeper(
    anomalies: InputArtifact[standard_artifacts.ExampleAnomalies]
):
    # Imports specific to TFDV internals
    from tensorflow_metadata.proto.v0 import anomalies_pb2
    import tensorflow as tf
    import os

    print(f"🔎 Inspecting Artifact URI: {anomalies.uri}")
    
    # 1. Recursively find all SchemaDiff.pb files
    diff_files = []
    for root, dirs, files in tf.io.gfile.walk(anomalies.uri):
        for f in files:
            if "SchemaDiff" in f:
                diff_files.append(os.path.join(root, f))

    if not diff_files:
        print("⚠️ No SchemaDiff files found. Assuming Clean Run (Pipeline Blessed).")
        return

    failure_triggered = False

    for diff_path in diff_files:
        print(f"Parsing: {diff_path}")
        try:
            anomalies_proto = anomalies_pb2.Anomalies()
            with tf.io.gfile.GFile(diff_path, 'rb') as f:
                anomalies_proto.ParseFromString(f.read())

            if anomalies_proto.anomaly_info:
                failure_triggered = True
                print(f"🚨 BLOCKING ANOMALY in {os.path.basename(diff_path)}!")
                for feature, info in anomalies_proto.anomaly_info.items():
                    print(f"   Feature: '{feature}'")
                    print(f"   Reason:  {info.short_description}")
                    print(f"   Detail:  {info.description}")
            else:
                print(f"   ✅ Valid (No anomalies)")

        except Exception as e:
            raise RuntimeError(f"CRITICAL: Failed to parse {diff_path}. File might be corrupt. Error: {e}")

    if failure_triggered:
        raise RuntimeError("Pipeline Blocked: Data Drift or Schema Drift Detected.")
    
    print("SUCCESS: All splits validated successfully.")
