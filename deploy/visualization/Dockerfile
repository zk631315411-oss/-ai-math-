FROM manimcommunity/manim:v0.19.0

USER root
WORKDIR /workspace
COPY requirements-visualization.txt /workspace/requirements-visualization.txt
RUN pip install --no-cache-dir -r /workspace/requirements-visualization.txt
COPY app /workspace/app
COPY scripts/run_visualization_worker.py /workspace/scripts/run_visualization_worker.py
RUN mkdir -p /workspace/data && chown -R manimuser:manimuser /workspace
USER manimuser
ENV PYTHONPATH=/workspace
CMD ["python", "scripts/run_visualization_worker.py"]
