FROM gcr.io/tfx-oss-public/tfx:1.16.0
RUN pip install scikit-learn pandas

WORKDIR /pipeline
COPY modules ./modules
ENV PYTHONPATH="/pipeline:${PYTHONPATH}"