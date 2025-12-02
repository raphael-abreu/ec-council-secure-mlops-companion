import os
from pathlib import Path

import tfx.v1 as tfx
from dotenv import load_dotenv
from google.cloud import aiplatform
from tfx.orchestration.kubeflow.v2 import kubeflow_v2_dag_runner
from tfx.extensions.google_cloud_ai_platform.pusher import executor as ai_platform_pusher_executor
from tfx.extensions.google_cloud_ai_platform import constants as ai_platform_constants
from tfx.dsl.components.base import executor_spec

from modules.gatekeeper import AnomalyGatekeeper
from modules.evaluator import SklearnEvaluator


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- CONFIG ---
PROJECT_ID = os.environ["PROJECT_ID"]
REGION = os.environ.get("REGION", "us-central1")
BUCKET = os.environ.get("BUCKET_NAME", f"secure-ml-data-{PROJECT_ID}")
PIPELINE_NAME = "secure-governance-pipeline-prod"
ROOT = f"gs://{BUCKET}/pipeline_root/{PIPELINE_NAME}"
DATA_GCS = f"gs://{BUCKET}/data/data"
SERVICE_ACCOUNT_NAME = os.environ.get("SERVICE_ACCOUNT_NAME", "secure-ml-pipeline-sa")
SERVICE_ACCOUNT = f"{SERVICE_ACCOUNT_NAME}@{PROJECT_ID}.iam.gserviceaccount.com"

# Image Configuration
default_image_tag = f"gcr.io/{PROJECT_ID}/secure-tfx:latest"
IMAGE_URI = os.environ.get("IMAGE_URI", default_image_tag)

# CMEK Configuration
KMS_KEY_RING = os.environ.get("KMS_KEY_RING", "ml-keyring")
KMS_KEY = os.environ.get("KMS_KEY", "ml-cmek-key")
ENCRYPTION_KEY_NAME = f"projects/{PROJECT_ID}/locations/{REGION}/keyRings/{KMS_KEY_RING}/cryptoKeys/{KMS_KEY}"

def create_pipeline():
    # 1. Ingest
    example_gen = tfx.components.CsvExampleGen(input_base=DATA_GCS)
    
    # 2. Validate
    stats_gen = tfx.components.StatisticsGen(examples=example_gen.outputs['examples'])
    schema_gen = tfx.components.ImportSchemaGen(schema_file=f"gs://{BUCKET}/schema/schema.pbtxt")
    validator = tfx.components.ExampleValidator(
        statistics=stats_gen.outputs['statistics'],
        schema=schema_gen.outputs['schema']
    )
    
    # 3. Gatekeeper (Custom Component)
    gatekeeper = AnomalyGatekeeper(anomalies=validator.outputs['anomalies'])
    
    # 4. Transform (Standard Component - Reads from GCS)
    transform = tfx.components.Transform(
        examples=example_gen.outputs['examples'],
        schema=schema_gen.outputs['schema'],
        module_file=str(BASE_DIR / "modules/preprocessing.py")
    )
    transform.add_upstream_node(gatekeeper)

    # 5. Trainer (Standard Component - Reads from GCS)
    trainer = tfx.components.Trainer(
        module_file=str(BASE_DIR / "modules/training.py"),
        examples=transform.outputs['transformed_examples'],
        transform_graph=transform.outputs['transform_graph'],
        schema=schema_gen.outputs['schema'],
        train_args=tfx.proto.TrainArgs(num_steps=0),  # NOTE: num_steps is ignored by our custom Scikit-Learn trainer.
        eval_args=tfx.proto.EvalArgs(num_steps=0)
    )
    
    # 6. Evaluator (Custom Component)
    # NOTE: This is a CUSTOM component (defined in modules/evaluator.py), not the standard TFX Evaluator.
    # It uses Scikit-Learn for metrics instead of TFMA.
    # It has to be built inside the container image for TFX to find it.
    evaluator = SklearnEvaluator(
        model=trainer.outputs['model'],
        transformed_examples=transform.outputs['transformed_examples'],
        transform_graph=transform.outputs['transform_graph']
    )
    
    # 7. Pusher -> Vertex AI Model Registry
    # Use the specialized Vertex AI Pusher component
    pusher = tfx.extensions.google_cloud_ai_platform.Pusher(
        model=trainer.outputs['model'],
        model_blessing=evaluator.outputs['blessing'],
        custom_config={
            ai_platform_constants.SERVING_ARGS_KEY: {
                'project_id': PROJECT_ID,
                'region': REGION,
                'model_name': f"{PIPELINE_NAME}-registry",
                'encryption_spec_key_name': ENCRYPTION_KEY_NAME,
            },
            ai_platform_constants.ENABLE_VERTEX_KEY: True,
            ai_platform_constants.VERTEX_REGION_KEY: REGION,
            ai_platform_constants.VERTEX_CONTAINER_IMAGE_URI_KEY: IMAGE_URI
        }
    )

    return tfx.dsl.Pipeline(
        pipeline_name=PIPELINE_NAME,
        pipeline_root=ROOT,
        components=[example_gen, stats_gen, schema_gen, validator, gatekeeper, transform, trainer, evaluator, pusher]
    )

if __name__ == "__main__":
    runner = kubeflow_v2_dag_runner.KubeflowV2DagRunner(
        config=tfx.orchestration.experimental.KubeflowV2DagRunnerConfig(
            default_image=IMAGE_URI
        ),
        output_filename="governance_pipeline.json"
    )
    runner.run(create_pipeline())
    
    aiplatform.init(project=PROJECT_ID, location=REGION)
    job = aiplatform.PipelineJob(
        display_name=PIPELINE_NAME,
        template_path="governance_pipeline.json",
        pipeline_root=ROOT
    )
    job.submit(service_account=SERVICE_ACCOUNT)